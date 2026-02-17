from __future__ import annotations

import logging

import requests
from assets.models import AssetCryptoCoin, HistQuotes, Quote
from bots.utils import IndicatorsCalc
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):

        self.stdout.write("Starting RSI scan...")
        self.calculate_signals()
        self.stdout.write(self.style.SUCCESS("Done."))

    def _build_telegram_message(self, data: dict) -> tuple[str, dict | None]:
        emoji = "🟢" if data["direction"] == "BUY" else "🔴"
        trend = "📈" if data["direction"] == "BUY" else "📉"

        msg = (
            f"<b>{emoji} {data['symbol']} · {data['direction']}</b> {trend}\n"
            f"💰 <b>{data['current_price']:.4f}</b> · RSI <b>{data['rsi_value']:.1f}</b>\n"
            f"🕒 {data['timestamp']} · 🤖 {data['bot_name']}\n"
            f"TF: {data['intervals']}\n\n"
        )

        if data["direction"] == "BUY":
            msg += "RSI &lt; 30 → oversold, bounce likely."
        else:
            msg += "RSI &gt; 70 → overbought, pullback likely."

        msg += "\n\n<i>Trading involves risk. Not financial advice.</i>"

        return msg, None

    def send_telegram_signal(self, user, signal_data: dict) -> bool:
        if not getattr(user, "chat_id", None) or not getattr(user, "tg_approved", False):
            logger.info(f"Skip Telegram: {user.username} not configured.")
            return False

        token = settings.TELEGRAM_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        text, reply_markup = self._build_telegram_message(signal_data)

        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": user.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                    **({"reply_markup": reply_markup} if reply_markup else {}),
                },
                timeout=10,
            )
            if resp.ok:
                logger.debug(f"Telegram sent → {user.username}")
                return True
            logger.error(f"Telegram {resp.status_code}: {resp.text}")
            return False
        except requests.RequestException as e:
            logger.error(f"Telegram network error: {e}")
            return False

    # ========== main logic ==========

    def calculate_signals(self):
        calc = IndicatorsCalc()
        assets = AssetCryptoCoin.objects.prefetch_related("bots")

        for asset in assets:
            for bot in asset.bots.all():
                rsi_indicator = bot.rsi_indicators.first()
                if not rsi_indicator:
                    continue

                rsi_values: list[float] = []
                latest_quote = None

                for interval in rsi_indicator.intervals:
                    q = (
                        HistQuotes.objects.filter(symbol=asset, interval=interval)
                        .order_by("-time")
                        .first()
                    )
                    if not q:
                        self.stdout.write(f"[{asset.symbol}] no quotes for {interval}, skip")
                        continue

                    val = calc.calculate_rsi_for_quote(q, rsi_indicator.period)
                    if val is None:
                        self.stdout.write(f"[{asset.symbol}] cannot calc RSI for {interval}")
                        continue

                    self.stdout.write(f"[{asset.symbol}] {interval} RSI={val:.2f}")

                    rsi_values.append(val)
                    if latest_quote is None:
                        latest_quote = q

                if not rsi_values:
                    continue

                direction = None
                if all(v <= rsi_indicator.min for v in rsi_values):
                    direction = "BUY"
                elif all(v >= rsi_indicator.max for v in rsi_values):
                    direction = "SELL"

                if not direction:
                    continue

                quote_now: Quote | None = (
                    Quote.objects.filter(symbol=asset).order_by("-time").first()
                )
                price = float(quote_now.lp) if quote_now and quote_now.lp else 0.0
                timestamp = quote_now.time.strftime("%Y-%m-%d %H:%M:%S UTC") if quote_now else "n/a"

                avg_rsi = sum(rsi_values) / len(rsi_values)

                data = {
                    "symbol": asset.symbol,
                    "direction": direction,
                    "current_price": price,
                    "rsi_value": avg_rsi,
                    "timestamp": timestamp,
                    "bot_name": getattr(bot, "name", f"Bot #{bot.id}"),
                    "intervals": ", ".join(rsi_indicator.intervals),
                }

                try:
                    owner = User.objects.get(id=bot.owner.id)
                    sent = self.send_telegram_signal(owner, data)
                    if sent:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"TG SENT → {asset.symbol} {direction} RSI={avg_rsi:.2f}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"TG SKIP → {asset.symbol} {direction} RSI={avg_rsi:.2f}"
                            )
                        )
                except Exception as e:
                    logger.error(f"Telegram send failed: {e}")
                    self.stdout.write(self.style.ERROR(str(e)))
