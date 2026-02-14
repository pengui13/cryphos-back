import logging
from typing import Dict, List, Optional
import requests

from bots.models import Signal, FundingRate, RiskSettings
from assets.models import AssetCryptoCoin, HistQuotes

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from bots.utils import IndicatorsCalc
from core.fetching_service import FetchingService
from django.utils import timezone
import redis
from decimal import Decimal

User = get_user_model()
logger = logging.getLogger(__name__)
CRYPHOS_URL = "https://cryphos.com"
CRYPHOS_LABEL = "Cryphos"

r = redis.from_url("redis://redis:6379/1", decode_responses=True)


@shared_task
def fetch_ohlcv_for_interval(interval: str):
    db_interval = settings.SUPPORTED_TIMEFRAMES.get(interval, interval)
    assets = AssetCryptoCoin.objects.all()

    for asset in assets:
        service = FetchingService(symbol=asset.symbol, interval=interval)
        klines = service.fetch_klines()

        if not klines:
            continue

        for kline in klines:
            if not isinstance(kline, list) or len(kline) < 6:
                continue

            HistQuotes.objects.update_or_create(
                symbol=asset,
                interval=db_interval,
                time=kline[0],
                defaults={
                    "open_price": kline[1],
                    "high_price": kline[2],
                    "low_price": kline[3],
                    "close_price": kline[4],
                    "volume": kline[5],
                },
            )


@shared_task()
def parse_fng():
    URL = "https://api.alternative.me/fng/"
    response = requests.get(URL)
    result = response.json()["data"][0]
    r.set("fng", int(result["value"]))
    r.set("fng_class", result["value_classification"])


@shared_task
def parse_funding_rate():
    assets = AssetCryptoCoin.objects.all()
    for asset in assets:
        symbol = asset.symbol.upper()
        URL = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}USDT&limit=1"
        try:
            response = requests.get(URL)
            result = response.json()[0]
            FundingRate.objects.update_or_create(
                asset=asset,
                exchange="binance",
                defaults={
                    "rate": Decimal(result["fundingRate"]),
                    "funding_time": result["fundingTime"],
                },
            )
        except Exception as e:
            print(e)


@shared_task()
def check_roi():
    open_signals = Signal.objects.filter(is_open=True).select_related("asset", "bot__owner")

    for signal in open_signals:
        try:
            risk = RiskSettings.objects.get(user=signal.bot.owner)
        except RiskSettings.DoesNotExist:
            continue

        if not risk.take_profit and not risk.stop_loss:
            continue

        latest_quote = signal.asset.hist_quotes.order_by("-time").first()
        if not latest_quote:
            continue

        open_price = float(signal.open_price)
        symbol = f"{signal.asset.symbol.upper()}USDT"
        current_price = float(r.hget("prices:last", symbol))

        if signal.is_long:
            roi = (current_price - open_price) / open_price * 100
        else:
            roi = (open_price - current_price) / open_price * 100

        should_close = False
        close_reason = None

        if risk.take_profit and roi >= float(risk.take_profit):
            should_close = True
            close_reason = "take_profit"
        if risk.stop_loss and roi <= -float(risk.stop_loss):
            should_close = True
            close_reason = "stop_loss"

        if should_close:
            signal.is_open = False
            signal.close_price = current_price
            signal.closed_at = timezone.now()
            signal.save()

            send_close_signal_telegram(
                user=signal.bot.owner,
                signal=signal,
                roi=roi,
                close_reason=close_reason,
            )


@shared_task
def calculate_signals():
    """
    Calculate signals with CONFLUENCE logic:
    - If bot has 1 indicator: send signal when that indicator triggers
    - If bot has 2+ indicators: ONLY send signal when ALL indicators agree on same direction
    """

    calc = IndicatorsCalc()
    assets = AssetCryptoCoin.objects.prefetch_related("bots")

    logger.info("=" * 60)
    logger.info("STARTING CALCULATE_SIGNALS TASK")
    logger.info("=" * 60)

    total_bots_checked = 0
    total_signals_sent = 0

    for asset in assets:
        bots = list(asset.bots.all())
        if not bots:
            continue

        logger.info(f"\n Asset: {asset.symbol} ({len(bots)} bots)")

        for bot in bots:
            total_bots_checked += 1

            has_rsi = bot.rsi_indicators.exists()
            has_bb = bot.bollinger_bands_indicators.exists()
            has_sr = bot.sr_indicators.exists()

            enabled_count = sum([has_rsi, has_bb, has_sr])

            signals = []

            if has_rsi:
                rsi_signal = calculate_rsi_signal(asset, bot, calc)
                if rsi_signal:
                    signals.append(rsi_signal)
                    logger.info(f"RSI: {rsi_signal['direction']} (value={rsi_signal['value']:.2f})")
                else:
                    continue

            if has_bb:
                bb_signal = calculate_bollinger_signal(asset, bot, calc)
                if bb_signal:
                    signals.append(bb_signal)
                    logger.info("BB: {bb_signal['direction']}")
                else:
                    logger.info("BB: No signal")
                    continue

            if has_sr:
                sr_signal = calculate_sr_signal(asset, bot, calc)
                if sr_signal:
                    signals.append(sr_signal)
                    logger.info(f"    ✅ SR: {sr_signal['direction']}")
                else:
                    logger.info(f"SR: No signal")
                    continue

            if len(signals) != enabled_count:
                logger.info(f"    ⏭️  Only {len(signals)}/{enabled_count} indicators triggered")
                continue

            directions = [s["direction"] for s in signals]
            unique_directions = set(directions)

            if len(unique_directions) > 1:
                logger.info(f"    ❌ Indicators disagree: {directions}")
                continue

            logger.info(f"    🎯 ALL {enabled_count} INDICATORS AGREE ON {directions[0]}!")

            if enabled_count == 1:
                send_signal_to_owner(bot, signals[0])
            else:
                combined_signal = combine_signals(asset, bot, signals)
                send_signal_to_owner(bot, combined_signal)

            total_signals_sent += 1

    logger.info("=" * 60)
    logger.info(f"   Bots checked: {total_bots_checked}")
    logger.info(f"   Signals sent: {total_signals_sent}")
    logger.info("=" * 60)


def send_close_signal_telegram(user, signal, roi: float, close_reason: str) -> bool:
    """Send signal close notification via Telegram."""
    if not getattr(user, "chat_id", None) or not getattr(user, "tg_approved", False):
        return False

    text = build_close_signal_message(signal, roi, close_reason)
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        resp = requests.post(
            url,
            json={
                "chat_id": user.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.ok:
            logger.info(f"✅ Close signal sent → {user.username} ({signal.asset.symbol})")
            return True
        logger.error(f"❌ Telegram API error {resp.status_code}: {resp.text}")
        return False
    except requests.RequestException as e:
        logger.error(f"❌ Telegram network error: {e}")
        return False


def build_close_signal_message(signal, roi: float, close_reason: str) -> str:
    """Build formatted Telegram message for closed signal."""
    is_profit = roi > 0
    emoji = "✅" if is_profit else "❌"
    reason_emoji = "🎯" if close_reason == "take_profit" else "🛑"
    reason_text = "Take Profit" if close_reason == "take_profit" else "Stop Loss"

    direction = "LONG" if signal.is_long else "SHORT"

    open_price = float(signal.open_price)
    close_price = float(signal.close_price)

    def format_price(price):
        if price >= 1000:
            return f"${price:,.0f}"
        elif price >= 1:
            return f"${price:,.2f}"
        return f"${price:.4f}"

    roi_str = f"+{roi:.2f}%" if roi > 0 else f"{roi:.2f}%"
    roi_color = "🟢" if roi > 0 else "🔴"

    bot_name = getattr(signal.bot, "name", None) or "Trading Bot"

    msg = f"""
{emoji} <b>SIGNAL CLOSED</b>

<b>{signal.asset.symbol}/USDT</b> · {direction}
{reason_emoji} {reason_text}

<b>Entry:</b> {format_price(open_price)}
<b>Exit:</b> {format_price(close_price)}
{roi_color} <b>P&L: {roi_str}</b>

<code>────────────────────</code>
🤖 {bot_name}
🔗 <a href="{CRYPHOS_URL}">{CRYPHOS_LABEL}</a>
""".strip()

    return msg


def interval_to_sec(period: str) -> int:
    INTERVAL_SEC = {"1MIN": 60, "5MIN": 300, "15MIN": 900, "30MIN": 1800, "1HRS": 3600}

    return INTERVAL_SEC[period] + 20


def calculate_rsi_signal(asset, bot, calc) -> Optional[Dict]:
    rsi_indicator = bot.rsi_indicators.first()
    if not rsi_indicator:
        return None

    period = rsi_indicator.period
    rsi_values: List[float] = []

    symbol = f"{asset.symbol.upper()}USDT"
    last = r.hget("prices:last", symbol)
    current_price = float(last) if last else None
    if not current_price:
        return None

    for interval in rsi_indicator.intervals:
        cache_key = f"rsi:{asset.symbol}:{period}:{interval}"
        value = cache.get(cache_key)

        if value is None:
            prices = list(
                HistQuotes.objects.filter(symbol=asset, interval=interval)
                .order_by("-time")[: period * 4]
                .values_list("close_price", flat=True)
            )
            if not prices:
                continue

            prices[0] = current_price
            value = calc.calculate_rsi(prices, period)
            if value is None:
                continue

            cache.set(cache_key, value, timeout=interval_to_sec(interval))

        rsi_values.append(float(value))

    if not rsi_values:
        return None

    direction = None
    if all(v <= rsi_indicator.min for v in rsi_values):
        direction = "BUY"
    elif all(v >= rsi_indicator.max for v in rsi_values):
        direction = "SELL"

    if not direction:
        logger.info(
            f"      [{asset.symbol}] RSI values don't trigger signal (min={rsi_indicator.min}, max={rsi_indicator.max})"
        )
        return None

    avg_rsi = sum(rsi_values) / len(rsi_values)
    tf_display = (
        ", ".join(rsi_indicator.intervals)
        .replace("MIN", "m")
        .replace("HRS", "h")
        .replace("DAY", "d")
    )

    return {
        "indicator": "RSI",
        "symbol": asset.symbol,
        "direction": direction,
        "current_price": current_price,
        "value": avg_rsi,
        "intervals": tf_display,
        "reason": (
            "Oversold · Bounce expected" if direction == "BUY" else "Overbought · Pullback expected"
        ),
        "emoji": "📊",
    }


def calculate_bollinger_signal(asset, bot, calc) -> Optional[Dict]:
    """Calculate Bollinger Bands signal for a bot."""
    bb_indicator = bot.bollinger_bands_indicators.first()
    if not bb_indicator:
        return None

    signals_found = []

    for interval in bb_indicator.intervals:
        prices = list(
            HistQuotes.objects.filter(symbol=asset, interval=interval)
            .order_by("-time")[: bb_indicator.period * 4]
            .values_list("close_price", flat=True)
        )

        symbol = f"{asset.symbol.upper()}USDT"
        current_price = float(r.hget("prices:last", symbol))
        prices[0] = current_price
        bb_data = calc.calculate_bollinger_bands(prices, bb_indicator.period, bb_indicator.std_dev)

        if not bb_data:
            continue

        upper_band = bb_data["upper"]
        lower_band = bb_data["lower"]

        logger.info(
            f"      [{asset.symbol}] {interval} BB: price={current_price:.2f}, upper={upper_band:.2f}, lower={lower_band:.2f}"
        )

        if current_price <= lower_band:
            signals_found.append(("BUY", "Price at lower band · Oversold"))
            logger.info(f"      [{asset.symbol}] {interval} BB signal: BUY (price <= lower band)")
        elif current_price >= upper_band:
            signals_found.append(("SELL", "Price at upper band · Overbought"))
            logger.info(f"      [{asset.symbol}] {interval} BB signal: SELL (price >= upper band)")

    if not signals_found:
        return None

    directions = [s[0] for s in signals_found]
    if len(set(directions)) != 1:
        logger.info(f"      [{asset.symbol}] BB timeframes disagree: {directions}")
        return None

    direction = directions[0]

    tf_display = (
        ", ".join(bb_indicator.intervals)
        .replace("MIN", "m")
        .replace("HRS", "h")
        .replace("DAY", "d")
    )

    return {
        "indicator": "Bollinger Bands",
        "symbol": asset.symbol,
        "direction": direction,
        "current_price": current_price,
        "value": None,
        "intervals": tf_display,
        "reason": signals_found[0][1],
        "emoji": "📉" if direction == "SELL" else "📈",
    }


def calculate_sr_signal(asset, bot, calc) -> Optional[Dict]:
    """Calculate Support/Resistance signal for a bot."""
    sr_indicator = bot.sr_indicators.first()
    if not sr_indicator:
        return None

    signals_found = []

    for interval in sr_indicator.intervals:
        quotes = HistQuotes.objects.filter(symbol=asset, interval=interval).order_by("-time")[
            : sr_indicator.lookback
        ]

        if len(quotes) < 20:
            logger.info(
                f"      [{asset.symbol}] Not enough quotes for S/R on {interval} (need 20, got {len(quotes)})"
            )
            continue

        # Calculate support/resistance levels
        levels = calc.calculate_support_resistance(
            list(quotes), sr_indicator.lookback, sr_indicator.levels_count
        )

        if not levels:
            logger.info(f"      [{asset.symbol}] No S/R levels calculated for {interval}")
            continue

        current_price = float(quotes[0].close_price)

        # Find closest support and resistance
        supports = [l for l in levels if l < current_price]
        resistances = [l for l in levels if l > current_price]

        if not supports or not resistances:
            logger.info(
                f"      [{asset.symbol}] No valid S/R levels (supports={len(supports)}, resistances={len(resistances)})"
            )
            continue

        closest_support = max(supports)
        closest_resistance = min(resistances)

        # Calculate distance to levels (as percentage)
        support_distance = abs((current_price - closest_support) / current_price) * 100
        resistance_distance = abs((closest_resistance - current_price) / current_price) * 100

        logger.info(
            f"      [{asset.symbol}] {interval} S/R: price={current_price:.2f}, support={closest_support:.2f} ({support_distance:.2f}%), resistance={closest_resistance:.2f} ({resistance_distance:.2f}%)"
        )

        # Signal if within 1% of a level
        if support_distance < 1.0:
            signals_found.append(
                ("BUY", f"Price near support ${closest_support:.2f} · Bounce expected")
            )
            logger.info(f"      [{asset.symbol}] {interval} S/R signal: BUY (near support)")
        elif resistance_distance < 1.0:
            signals_found.append(
                ("SELL", f"Price near resistance ${closest_resistance:.2f} · Rejection expected")
            )
            logger.info(f"      [{asset.symbol}] {interval} S/R signal: SELL (near resistance)")

    if not signals_found:
        return None

    # ALL timeframes must agree on direction
    directions = [s[0] for s in signals_found]
    if len(set(directions)) != 1:
        logger.info(f"      [{asset.symbol}] S/R timeframes disagree: {directions}")
        return None

    direction = directions[0]

    latest_hist = HistQuotes.objects.filter(symbol=asset).order_by("-time").first()
    price = float(latest_hist.close_price) if latest_hist and latest_hist.close_price else 0.0

    tf_display = (
        ", ".join(sr_indicator.intervals)
        .replace("MIN", "m")
        .replace("HRS", "h")
        .replace("DAY", "d")
    )

    return {
        "indicator": "Support/Resistance",
        "symbol": asset.symbol,
        "direction": direction,
        "current_price": price,
        "value": None,
        "intervals": tf_display,
        "reason": signals_found[0][1],
        "emoji": "🎯",
    }


def combine_signals(asset, bot, signals: List[Dict]) -> Dict:
    """Combine multiple signals into one message."""
    direction = signals[0]["direction"]
    price = signals[0]["current_price"]

    indicators = [s["indicator"] for s in signals]
    reasons = [s["reason"] for s in signals]

    return {
        "symbol": asset.symbol,
        "direction": direction,
        "current_price": price,
        "indicators": indicators,
        "reasons": reasons,
        "bot_name": getattr(bot, "name", None) or "Trading Bot",
        "is_combined": True,
    }


def send_signal_to_owner(bot, signal_data: Dict):
    """Send signal to bot owner via Telegram."""
    User = get_user_model()

    try:
        owner = User.objects.get(id=bot.owner.id)
        asset = AssetCryptoCoin.objects.filter(symbol=signal_data["symbol"].upper()).first()

        if not asset:
            logger.error(f"Asset not found: {signal_data['symbol']}")
            return

        is_long = signal_data["direction"] == "BUY"

        open_signal = Signal.objects.filter(bot=bot, asset=asset, is_open=True).first()

        if open_signal is None:
            Signal.objects.create(
                asset=asset, open_price=signal_data["current_price"], is_long=is_long, bot=bot
            )
            logger.info(f"    ✅ Created new {signal_data['direction']} signal")
        else:
            if open_signal.is_long != is_long:
                old_direction = "LONG" if open_signal.is_long else "SHORT"
                open_signal.is_open = False
                open_signal.close_price = signal_data["current_price"]
                open_signal.save()

                Signal.objects.create(
                    asset=asset, open_price=signal_data["current_price"], is_long=is_long, bot=bot
                )
                logger.info(f"    🔄 Reversed {old_direction} → {signal_data['direction']}")
            else:
                logger.info(
                    f"    ⏭️  Signal already open: {signal_data['symbol']} {signal_data['direction']}"
                )
                return

        sent = send_telegram_signal(owner, signal_data, bot)
        if sent:
            indicator = signal_data.get("indicator", "Combined")
            logger.info(
                f"    📨 TG SENT → {signal_data['symbol']} {signal_data['direction']} via {indicator}"
            )
        else:
            logger.warning(f"    ⏭️  TG SKIP → {signal_data['symbol']} {signal_data['direction']}")

    except Exception as e:
        logger.error(f"    ❌ Telegram send failed: {e}")


def send_telegram_signal(user, signal_data: Dict, bot=None) -> bool:
    """Send trading signal via Telegram."""
    if not getattr(user, "chat_id", None) or not getattr(user, "tg_approved", False):
        logger.info(
            f"      Skip Telegram: user {user.username} - chat_id={getattr(user, 'chat_id', None)}, approved={getattr(user, 'tg_approved', None)}"
        )
        return False

    text = build_telegram_message(signal_data, bot)
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        resp = requests.post(
            url,
            json={
                "chat_id": user.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.ok:
            logger.info(f"      ✅ Telegram API success → {user.username}")
            return True
        logger.error(f"      ❌ Telegram API error {resp.status_code}: {resp.text}")
        return False
    except requests.RequestException as e:
        logger.error(f"      ❌ Telegram network error: {e}")
        return False


def build_telegram_message(data: Dict, bot=None) -> str:
    """Build formatted Telegram message."""
    is_buy = data["direction"] == "BUY"

    emoji = "🟢" if is_buy else "🔴"
    action = "LONG" if is_buy else "SHORT"

    # Price formatting
    price = data["current_price"]
    if price >= 1000:
        price_str = f"${price:,.0f}"
    elif price >= 1:
        price_str = f"${price:,.2f}"
    else:
        price_str = f"${price:.4f}"

    # Footer bits
    bot_name = data.get("bot_name", "Trading Bot")
    cryphos_link = f'🔗 <a href="{CRYPHOS_URL}">{CRYPHOS_LABEL}</a>'

    # Build message based on signal type
    if data.get("is_combined"):
        indicators_str = " + ".join(data["indicators"])
        reasons_str = "\n".join([f"• {r}" for r in data["reasons"]])

        msg = f"""
{emoji} <b>{data['symbol']}/USDT</b> · {action}

<b>{price_str}</b>

<b>✅ All Indicators Agree:</b>
{indicators_str}

{reasons_str}

<code>────────────────────</code>
🤖 {bot_name}
{cryphos_link}
⚠️ <i>Not financial advice</i>
""".strip()
    else:
        indicator_emoji = data.get("emoji", "📊")
        indicator = data.get("indicator", "Signal")

        value_str = ""
        if data.get("value") is not None:
            value = data["value"]
            if indicator == "RSI":
                if value <= 30:
                    status = "Oversold"
                elif value >= 70:
                    status = "Overbought"
                else:
                    status = "Neutral"
                value_str = f"RSI {value:.1f} · {status}"

        intervals = data.get("intervals", "")

        msg = f"""
{emoji} <b>{data['symbol']}/USDT</b> · {action}

<b>{price_str}</b>
{value_str}
{f"TF: {intervals}" if intervals else ""}

{indicator_emoji} <b>{indicator}</b>
<i>{data['reason']}</i>

<code>────────────────────</code>
🤖 {bot_name}
{cryphos_link}
⚠️ <i>Not financial advice</i>
""".strip()

    return msg
