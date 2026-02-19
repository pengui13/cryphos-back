from decimal import Decimal

import redis
from assets.models import HistQuotes, Quote
from django.db import transaction
from django.db.models import F, Max, Min, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bots.models import Bot, BotBalance, MainBotSettings, Signal, UserBalance

from .models import (
    AtrValue,
    BollingerBandsValue,
    BotSignal,
    FundingRate,
    MacdValue,
    MaValue,
    ObvValue,
    RiskSettings,
    RsiValue,
)
from .serializers import (
    BollingerBandsIndicatorSerializer,
    BotBalanceSerializer,
    BotSerializer,
    EmaIndicatorSerializer,
    FundingRateSerializer,
    MainBotSerializer,
    MaIndicatorSerializer,
    RiskSerializer,
    RsiIndicatorSerializer,
    SignalSerializer,
    SupportResistanceIndicatorSerializer,
    FiboSerializer
)

REDIS_URL = "redis://redis:6379/1"


DEFAULT_FREQUENCY = 50.0
DEFAULT_ACCURACY = 70.0
DEFAULT_RISK = 30.0

BOT_METADATA_FIELDS = [
    "name",
    "bot_assets",
    "description",
    "id",
    "user",
    "created_at",
    "updated_at",
    "user_id",
    "exchange",
    "interval",
    "status",
    "is_active",
    "is_paused",
]


class GetPing(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({"ping": True})


class GetFundingRates(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FundingRateSerializer
    queryset = FundingRate.objects.all()


class GetFnGValue(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        r = redis.from_url(REDIS_URL, decode_responses=True)
        value = r.get("fng") or None
        classification = r.get("fng_class") or None

        return Response({"value": value, "class": classification})


class RiskSettingsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiskSerializer

    def get_object(self):
        obj, created = RiskSettings.objects.get_or_create(user=self.request.user)
        return obj


class AddTelegram(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        telegram_nickname = request.data.get("nickname", "")
        user.tg_nickname = telegram_nickname
        user.save()
        return Response({"resp": "all good"})


class GetTelegramInfo(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({"tg": user.tg_nickname, "chat_id": user.chat_id})


serializer_classes = {
    "rsi": RsiIndicatorSerializer,
    "bb": BollingerBandsIndicatorSerializer,
    "sr": SupportResistanceIndicatorSerializer,
    "ema": EmaIndicatorSerializer,
    "ma": MaIndicatorSerializer,
    "fibo": FiboSerializer,

}


class CreateBot(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        serializer = BotSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            return Response({"error": "Invalid bot data", "details": serializer.errors}, status=400)

        with transaction.atomic():
            bot = serializer.save()

            main_settings = MainBotSettings.objects.filter(user=user).first()
            if not main_settings:
                MainBotSettings.objects.create(user=user)

            for key, serializer_class in serializer_classes.items():
                if key in data and isinstance(data[key], dict):
                    ind_ser = serializer_class(
                        data=data[key], context={"bot": bot, "request": request}
                    )

                    if not ind_ser.is_valid():
                        return Response(
                            {"error": f"Invalid {key} data", "details": ind_ser.errors}, status=400
                        )

                    ind_ser.save()

            bot.activate()

        return Response(
            {"status": "ok", "message": "Bot created successfully", "id": bot.id}, status=201
        )


class GetSignals(ListAPIView):
    serializer_class = SignalSerializer

    def get_queryset(self):
        bot_id = self.kwargs.get("id")
        return Signal.objects.filter(bot=Bot.objects.get(id=bot_id))


class CloseBotPosition(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, id):
        user = request.user
        signal = BotSignal.objects.filter(bot__owner=user, id=id, status="Pending").first()
        if not signal:
            return Response(
                {"error": "There is no such position"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bot_balance = BotBalance.objects.filter(user=user, bot=signal.bot).first()
        if not bot_balance:
            return Response({"error": "User doesn't have active balance"})
        BotBalance.objects.filter(id=bot_balance.id, bot=signal.bot).update(
            current_balance=F("current_balance") + signal.pnl
        )
        signal.closed_at = timezone.now()
        signal.status = "Closed"
        rate = Quote.objects.filter(symbol=signal.asset, interval="1m").first().lp
        signal.exit_price = rate
        signal.save()
        bot_balance.save()
        return Response({"status": "ok"})


MAX_RETURNED_CANDLES = 500


def get_timeframe_minutes(timeframe: str) -> int:
    """Convert timeframe string to minutes."""
    mapping = {
        "1MIN": 1,
        "5MIN": 5,
        "15MIN": 15,
        "30MIN": 30,
        "1HRS": 60,
        "1DAY": 1440,
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "1d": 1440,
    }
    return mapping.get(timeframe, 1)


def _check_buy_intersection(timeframe_data, timeframes, candle_time, rsi_min):

    for timeframe in timeframes:
        candles = timeframe_data.get(timeframe, [])
        if not candles:
            return False

        tf_minutes = get_timeframe_minutes(timeframe)
        tf_seconds = tf_minutes * 60

        containing_candle = None
        for candle in candles:
            start = candle.get("time", 0)
            end = start + tf_seconds
            if start <= candle_time < end:
                containing_candle = candle
                break

        if not containing_candle or containing_candle.get("rsi") is None:
            return False

        rsi = containing_candle["rsi"]
        if rsi > rsi_min:
            return False

    return True


def calc_rsi_for_candles(candles, period: int = 14):

    n = len(candles)
    if n <= period:
        return candles

    closes = [Decimal(c["close_price"]) for c in candles]

    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, Decimal("0")))
        losses.append(max(-diff, Decimal("0")))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        rsi = Decimal("100")
    else:
        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    candles[period]["rsi"] = rsi
    candles[period]["avg_gain"] = avg_gain
    candles[period]["avg_loss"] = avg_loss

    for i in range(period + 1, n):
        diff = closes[i] - closes[i - 1]
        gain = max(diff, Decimal("0"))
        loss = max(-diff, Decimal("0"))

        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period

        if avg_loss == 0:
            rsi = Decimal("100")
        else:
            rs = avg_gain / avg_loss
            rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

        candles[i]["avg_gain"] = avg_gain
        candles[i]["avg_loss"] = avg_loss
        candles[i]["rsi"] = rsi

    return candles


# class Backtest(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, bot_id):
#         bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
#         data = request.data

#         rsi_obj = RsiIndicator.objects.filter(bot=bot).first()
#         if rsi_obj is None:
#             return Response({"detail": "RSI config not found for bot."}, status=400)

#         bot_assets = bot.bot_assets.all()
#         if not bot_assets.exists():
#             return Response({"detail": "No assets configured for this bot."}, status=400)

#         timeframes = list(rsi_obj.intervals or [])
#         if not timeframes:
#             return Response({"detail": "No timeframes configured for RSI indicator."}, status=400)

#         sorted_timeframes = sorted(timeframes, key=get_timeframe_minutes)
#         base_timeframe = sorted_timeframes[0]

#         since = timezone.now() - timezone.timedelta(days=90)
#         since_ts = int(since.timestamp())

#         usdt_value = Decimal(str(data.get("usdt_value", 1000)))
#         take_profit = Decimal(str(data.get("take_profit", 10)))  # %
#         stop_loss = Decimal(str(data.get("stop_loss", 5)))  # %

#         all_orders = []
#         results_by_asset = {}

#         for asset in bot_assets:
#             timeframe_data = {}

#             for timeframe in timeframes:
#                 candles_qs = HistQuotes.objects.filter(
#                     symbol__symbol=asset.symbol,
#                     interval=timeframe,
#                     time__gte=since_ts,
#                 ).order_by("time")

#                 candles_data = HistQuotesSerializer(candles_qs, many=True).data

#                 if not candles_data:
#                     timeframe_data[timeframe] = []
#                     continue

#                 candles_data = [
#                     {
#                         **c,
#                         "time": int(c["time"]),
#                         "open_price": str(c["open_price"]),
#                         "high_price": str(c["high_price"]),
#                         "low_price": str(c["low_price"]),
#                         "close_price": str(c["close_price"]),
#                     }
#                     for c in candles_data
#                 ]

#                 candles = calc_rsi_for_candles(candles_data, period=rsi_obj.period)

#                 for c in candles:
#                     c.pop("avg_gain", None)
#                     c.pop("avg_loss", None)

#                 timeframe_data[timeframe] = candles

#             base_candles = timeframe_data.get(base_timeframe, [])

#             if not base_candles:
#                 results_by_asset[asset.symbol] = {
#                     "asset": asset.symbol,
#                     "total_pnl": 0.0,
#                     "stats": self._get_empty_stats(),
#                     "orders": [],
#                     "candles": [],
#                     "candles_1MIN": [],
#                     "candles_5MIN": [],
#                 }
#                 continue

#             buy_orders = []
#             open_order = None
#             single_tf_mode = len(timeframes) == 1

#             for candle in base_candles:
#                 rsi = candle.get("rsi")
#                 if rsi is None:
#                     continue

#                 price = Decimal(candle["close_price"])
#                 candle_time = candle["time"]

#                 # ENTRY
#                 if open_order is None and rsi <= rsi_obj.min:
#                     if single_tf_mode:
#                         buy_signal_confirmed = True
#                     else:
#                         buy_signal_confirmed = _check_buy_intersection(
#                             timeframe_data, timeframes, candle_time, rsi_obj.min
#                         )

#                     if buy_signal_confirmed:
#                         amount_to_buy = usdt_value / price

#                         order = {
#                             "asset": asset.symbol,
#                             "value": amount_to_buy,
#                             "price": price,
#                             "total": amount_to_buy * price,
#                             "side": "BUY",
#                             "opened": True,
#                             "closed": False,
#                             "open_time": candle_time,
#                             "open_rsi": rsi,
#                             "close_time": None,
#                             "close_price": None,
#                             "close_rsi": None,
#                             "pnl": None,
#                             "close_reason": None,
#                         }
#                         buy_orders.append(order)
#                         open_order = order
#                         candle["order_open"] = order

#                     continue

#                 if open_order is not None:
#                     price_change_pct = (
#                         (price - open_order["price"]) / open_order["price"]
#                     ) * Decimal("100")

#                     if price_change_pct >= take_profit:
#                         open_order["opened"] = False
#                         open_order["closed"] = True
#                         open_order["close_time"] = candle_time
#                         open_order["close_price"] = price
#                         open_order["close_rsi"] = rsi
#                         open_order["pnl"] = (price - open_order["price"]) * open_order["value"]
#                         open_order["close_reason"] = "take_profit"
#                         candle["order_close"] = open_order
#                         open_order = None
#                         continue

#                     if price_change_pct <= -stop_loss:
#                         open_order["opened"] = False
#                         open_order["closed"] = True
#                         open_order["close_time"] = candle_time
#                         open_order["close_price"] = price
#                         open_order["close_rsi"] = rsi
#                         open_order["pnl"] = (price - open_order["price"]) * open_order["value"]
#                         open_order["close_reason"] = "stop_loss"
#                         candle["order_close"] = open_order
#                         open_order = None
#                         continue

#                     if rsi >= rsi_obj.max:
#                         open_order["opened"] = False
#                         open_order["closed"] = True
#                         open_order["close_time"] = candle_time
#                         open_order["close_price"] = price
#                         open_order["close_rsi"] = rsi
#                         open_order["pnl"] = (price - open_order["price"]) * open_order["value"]
#                         open_order["close_reason"] = "rsi_signal"
#                         candle["order_close"] = open_order
#                         open_order = None

#             asset_total_pnl = sum(o["pnl"] for o in buy_orders if o.get("pnl") is not None)
#             asset_stats = self._calculate_stats(buy_orders)

#             def last_window(candles_list):
#                 if not candles_list:
#                     return []
#                 if len(candles_list) <= MAX_RETURNED_CANDLES:
#                     return candles_list
#                 return candles_list[-MAX_RETURNED_CANDLES:]

#             candles_1m = last_window(timeframe_data.get("1MIN") or timeframe_data.get("1m") or [])
#             candles_5m = last_window(timeframe_data.get("5MIN") or timeframe_data.get("5m") or [])
#             base_window = last_window(base_candles)

#             results_by_asset[asset.symbol] = {
#                 "asset": asset.symbol,
#                 "total_pnl": float(asset_total_pnl),
#                 "stats": asset_stats,
#                 "orders": buy_orders,
#                 "candles": base_window,
#                 "candles_1MIN": candles_1m,
#                 "candles_5MIN": candles_5m,
#             }

#             all_orders.extend(buy_orders)

#         total_pnl = sum(o["pnl"] for o in all_orders if o.get("pnl") is not None)
#         total_stats = self._calculate_stats(all_orders)

#         closed_trades = [o for o in all_orders if o.get("closed")]
#         total_invested = usdt_value * len(closed_trades) if closed_trades else Decimal("0")
#         roi = (total_pnl / total_invested * Decimal("100")) if total_invested > 0 else Decimal("0")

#         result = {
#             "asset": "MULTI",
#             "assets_count": len(bot_assets),
#             "timeframes": sorted_timeframes,
#             "rsi_config": {
#                 "period": rsi_obj.period,
#                 "min": rsi_obj.min,
#                 "max": rsi_obj.max,
#             },
#             "parameters": {
#                 "usdt_value": float(usdt_value),
#                 "take_profit": float(take_profit),
#                 "stop_loss": float(stop_loss),
#             },
#             "total_pnl": float(total_pnl),
#             "roi": float(round(roi, 2)),
#             "stats": total_stats,
#             "orders": all_orders,
#             "by_asset": results_by_asset,
#         }

#         return Response(result)

#     def _get_empty_stats(self):
#         return {
#             "total_trades": 0,
#             "profitable_trades": 0,
#             "non_profitable_trades": 0,
#             "win_rate": 0.0,
#             "max_pnl": None,
#             "min_pnl": None,
#             "mean_pnl": 0.0,
#             "mean_duration_minutes": 0.0,
#         }

#     def _calculate_stats(self, orders):
#         closed_orders = [o for o in orders if o.get("closed") and o.get("pnl") is not None]

#         if not closed_orders:
#             return self._get_empty_stats()

#         pnl_values = [o["pnl"] for o in closed_orders]
#         profitable = [p for p in pnl_values if p > 0]
#         non_profitable = [p for p in pnl_values if p <= 0]

#         mean_pnl = sum(pnl_values) / len(pnl_values) if pnl_values else Decimal("0")

#         durations = []
#         for order in closed_orders:
#             if order.get("open_time") and order.get("close_time"):
#                 duration_seconds = order["close_time"] - order["open_time"]
#                 duration_minutes = duration_seconds / 60
#                 durations.append(duration_minutes)

#         mean_duration = sum(durations) / len(durations) if durations else 0
#         win_rate = (len(profitable) / len(closed_orders) * 100) if closed_orders else 0.0

#         return {
#             "total_trades": len(closed_orders),
#             "profitable_trades": len(profitable),
#             "non_profitable_trades": len(non_profitable),
#             "win_rate": float(round(Decimal(str(win_rate)), 2)),
#             "max_pnl": float(max(pnl_values)) if pnl_values else None,
#             "min_pnl": float(min(pnl_values)) if pnl_values else None,
#             "mean_pnl": float(round(mean_pnl, 2)),
#             "mean_duration_minutes": float(round(mean_duration, 2)),
#         }


# class LeaveBot(APIView):
#     permission_classes = [IsAuthenticated]

#     def close_all_tx(self, user, bot_balance):
#         signals = BotSignal.objects.filter(bot__owner=user, status="Pending", bot=bot_balance.bot)
#         for signal in signals:
#             signal.status = "Closed"
#             bot_balance.current_balance = F("current_balance") + signal.pnl
#             bot_balance.initial_balance = F("initial_balance") + signal.pnl
#             signal.save()
#             bot_balance.save()
#             bot_balance.refresh_from_db()

#     def post(self, request, id):
#         user = request.user
#         with transaction.atomic():
#             bot = Bot.objects.filter(id=id, owner=user).first()
#             bot_balance = (
#                 BotBalance.objects.select_for_update()
#                 .filter(bot__owner=user, bot=bot, initial_balance__gt=0)
#                 .first()
#             )

#             if not bot_balance:
#                 return Response({"error": "No bot balance found"}, status=status.HTTP_404_NOT_FOUND)
#             user_balance = UserBalance.objects.filter(user=user, asset__symbol="USDT").first()
#             self.close_all_tx(user, bot_balance)
#             bot.activate()
#             user_balance.quantity = F("quantity") + bot_balance.current_balance
#             bot_balance.initial_balance = 0
#             bot_balance.current_balance = 0
#             bot_balance.unrealised_pnl = 0
#             bot.save()
#             user_balance.save()
#             bot_balance.save()
#             return Response({"status": "ok"})


class GetBotSubscribers(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bot_id):
        try:
            bot = Bot.objects.get(id=bot_id)
        except Exception as e:
            print(e)
            return Response({"error": "There is no such bot"}, status=status.HTTP_404_NOT_FOUND)
        balances = BotBalance.objects.filter(bot=bot)
        serializer = GetBotSubscribers(balances, many=True)  # type: ignore[call-arg]
        return Response(serializer.data)


class ToggleVerification(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, bot_id):
        user = request.user
        bot = get_object_or_404(Bot, id=bot_id, owner=user)
        Bot.objects.filter(id=bot_id, owner=user).update(verification_status="pending")
        bot.verification_status = "pending"
        bot.save()
        return Response({"status": "ok"})


class GetBotsList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        bots = Bot.objects.filter(Q(owner=user) | Q(users=user)).distinct()
        data = BotSerializer(bots, many=True).data
        return Response({"data": data})


class DeleteMyBot(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, bot_id):
        user = request.user
        bot = get_object_or_404(Bot, id=bot_id, owner=user)
        bot.delete()
        return Response({"status": "deleted"})


class GetBotsDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bot_id):
        user = request.user

        bot = get_object_or_404(Bot, id=bot_id)

        if bot.owner != user and user not in bot.users.all() and not bot.published:
            return Response(
                {"detail": "You do not have permission to view this bot's data."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            bot_balance = BotBalance.objects.get(bot=bot, user=user)
        except Exception as e:
            print(e)
            bot_balance = None

        signals = BotSignal.objects.filter(bot=bot, balance=bot_balance).select_related("asset")

        rsi_indicators = bot.rsi_indicators.all()
        ma_indicators = bot.ma_indicators.all()
        macd_indicators = bot.macd_indicators.all()
        bb_indicators = bot.bollinger_bands_indicators.all()
        atr_indicators = bot.atr_indicators.all()
        obv_indicators = bot.obv_indicators.all()
        main_settings = user.bot_user_settings.first()
        main_settings_data = MainBotSerializer(main_settings).data

        successful_signals = signals.filter(status="Closed", pnl__gt=0).count()
        total_closed_signals = signals.filter(status="Closed").count()
        accuracy = (
            (successful_signals / total_closed_signals * 100) if total_closed_signals > 0 else 0
        )

        if signals.exists():
            first_signal_date = signals.aggregate(Min("created_at"))["created_at__min"]
            latest_signal_date = signals.aggregate(Max("created_at"))["created_at__max"]

            days_active = (latest_signal_date - first_signal_date).days or 1
            frequency = total_closed_signals / days_active
        else:
            frequency = 0

        bot_data = {
            "id": bot.id,
            "name": bot.name,
            "description": bot.description,
            "created_at": bot.created_at,
            "last_activated": bot.last_activated,
            "published": bot.published,
            "runtime": bot.runtime,
            "roi": float(bot.roi),
            "is_owner": bot.owner == user,
            "verification_status": bot.verification_status,
            "pnl": float(bot.pnl),
            "accuracy": float(bot.accuracy) or accuracy,
            "frequency": float(bot.frequency) or frequency,
            "risk": float(bot.risk),
            "intersection": bot.intersection,
            "assets": [
                {"id": asset.id, "symbol": asset.symbol, "name": asset.name}
                for asset in bot.bot_assets.all()
            ],
        }
        if bot_balance:
            balance_data = {
                "id": bot_balance.id,
                "initial_balance": float(bot_balance.initial_balance),
                "current_balance": float(bot_balance.current_balance),
                "take_profit": float(bot_balance.take_profit),
                "stop_loss": float(bot_balance.stop_loss),
                "unrealised_pnl": float(bot_balance.unrealised_pnl),
            }

        closed_signals = []
        opened_signals = []

        for signal in signals:
            signal_data = {
                "id": signal.id,
                "asset": {
                    "id": signal.asset.id,
                    "symbol": signal.asset.symbol,
                    "name": signal.asset.name,
                },
                "is_long": signal.is_long,
                "status": signal.status,
                "quantity": float(signal.quantity) if signal.quantity else None,
                "entry_price": (float(signal.entry_price) if signal.entry_price else None),
                "exit_price": float(signal.exit_price) if signal.exit_price else None,
                "created_at": signal.created_at,
                "closed_at": signal.closed_at,
                "pnl": float(signal.pnl),
                "roi": float(signal.roi),
            }

            if signal.created_at:
                try:
                    closest_quote = (
                        HistQuotes.objects.filter(asset=signal.asset, time__lte=signal.created_at)
                        .order_by("-time")
                        .first()
                    )

                    if closest_quote:
                        signal_indicators = {}

                        for indicator in rsi_indicators:
                            rsi_value = RsiValue.objects.filter(
                                indicator=indicator, quote=closest_quote
                            ).first()
                            if rsi_value:
                                signal_indicators[f"rsi_{indicator.id}"] = {
                                    "value": float(rsi_value.value),
                                    "min": indicator.min,
                                    "max": indicator.max,
                                    "period": indicator.period,
                                    "intervals": indicator.intervals,
                                }

                        for indicator in ma_indicators:
                            ma_value = MaValue.objects.filter(
                                indicator=indicator, quote=closest_quote
                            ).first()
                            if ma_value:
                                signal_indicators[f"ma_{indicator.id}"] = {
                                    "value": float(ma_value.value),
                                    "period": indicator.period,
                                    "intervals": indicator.intervals,
                                }

                        for indicator in macd_indicators:
                            macd_value = MacdValue.objects.filter(
                                indicator=indicator, quote=closest_quote
                            ).first()
                            if macd_value:
                                signal_indicators[f"macd_{indicator.id}"] = {
                                    "value": float(macd_value.value),
                                    "signal": float(macd_value.signal),
                                    "histogram": float(macd_value.histogram),
                                    "fast_period": indicator.fast_period,
                                    "slow_period": indicator.slow_period,
                                    "signal_period": indicator.signal_period,
                                    "intervals": indicator.intervals,
                                }

                        for indicator in bb_indicators:
                            bb_value = BollingerBandsValue.objects.filter(
                                indicator=indicator, quote=closest_quote
                            ).first()
                            if bb_value:
                                signal_indicators[f"bb_{indicator.id}"] = {
                                    "upper_band": float(bb_value.upper_band),
                                    "middle_band": float(bb_value.middle_band),
                                    "lower_band": float(bb_value.lower_band),
                                    "period": indicator.period,
                                    "std_dev": indicator.std_dev,
                                    "intervals": indicator.intervals,
                                }

                        for indicator in atr_indicators:
                            atr_value = AtrValue.objects.filter(
                                indicator=indicator, quote=closest_quote
                            ).first()
                            if atr_value:
                                signal_indicators[f"atr_{indicator.id}"] = {
                                    "value": float(atr_value.value),
                                    "period": indicator.period,
                                    "intervals": indicator.intervals,
                                }

                        for indicator in obv_indicators:
                            obv_value = ObvValue.objects.filter(
                                indicator=indicator, quote=closest_quote
                            ).first()
                            if obv_value:
                                signal_indicators[f"obv_{indicator.id}"] = {
                                    "value": float(obv_value.value),
                                    "intervals": indicator.intervals,
                                }

                        signal_data["indicators"] = signal_indicators
                except Exception as e:
                    signal_data["indicators"] = {"error": str(e)}

            if signal.status == "Closed":
                closed_signals.append(signal_data)
            else:
                opened_signals.append(signal_data)

        indicators_config = {
            "rsi": [
                {
                    "id": indicator.id,
                    "min": indicator.min,
                    "max": indicator.max,
                    "period": indicator.period,
                    "intervals": indicator.intervals,
                }
                for indicator in rsi_indicators
            ],
            "ma": [
                {
                    "id": indicator.id,
                    "period": indicator.period,
                    "intervals": indicator.intervals,
                }
                for indicator in ma_indicators
            ],
            "macd": [
                {
                    "id": indicator.id,
                    "fast_period": indicator.fast_period,
                    "slow_period": indicator.slow_period,
                    "signal_period": indicator.signal_period,
                    "intervals": indicator.intervals,
                }
                for indicator in macd_indicators
            ],
            "bollinger_bands": [
                {
                    "id": indicator.id,
                    "period": indicator.period,
                    "std_dev": indicator.std_dev,
                    "intervals": indicator.intervals,
                }
                for indicator in bb_indicators
            ],
            "atr": [
                {
                    "id": indicator.id,
                    "period": indicator.period,
                    "intervals": indicator.intervals,
                }
                for indicator in atr_indicators
            ],
            "obv": [
                {
                    "id": indicator.id,
                    "intervals": indicator.intervals,
                }
                for indicator in obv_indicators
            ],
        }

        signals_data = {"closed": closed_signals, "opened": opened_signals}

        response_data = {
            "bot": bot_data,
            "balance": balance_data if bot_balance else {},
            "main_settings": main_settings_data,
            "signals": signals_data,
            "indicators_config": indicators_config,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class GetAvailableBalance(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        balance = UserBalance.objects.get(user=request.user)
        return Response({"quantity": balance.quantity})


class GetAllBots(APIView):
    permission_classes = [IsAuthenticated]

    def get(self):
        bots = Bot.objects.filter(published=True)

        serializer = BotSerializer(bots, many=True)
        return Response(serializer.data)


def extract_indicator_config(cfg):
    indicator_cfg = {}

    for key, value in cfg.items():
        if key in BOT_METADATA_FIELDS or not isinstance(value, dict):
            continue
        indicator_cfg[key] = value

    return indicator_cfg


def calculate_signal_frequency(cfg):

    if not cfg:
        return DEFAULT_FREQUENCY

    enabled_indicators = []
    for _, ind in cfg.items():
        if isinstance(ind, dict) and ind.get("enabled", True):
            enabled_indicators.append(ind)

    if not enabled_indicators:
        return DEFAULT_FREQUENCY

    indicator_count = len(enabled_indicators)

    if indicator_count == 1:
        base_frequency = 60.0
    elif indicator_count == 2:
        base_frequency = 40.0
    elif indicator_count == 3:
        base_frequency = 27.0
    elif indicator_count == 4:
        base_frequency = 18.0
    elif indicator_count == 5:
        base_frequency = 12.0
    else:
        base_frequency = 8.3

    frequency_multiplier = 1.0

    for ind in enabled_indicators:
        if "min" in ind and "max" in ind:
            width = ind["max"] - ind["min"]
            if width < 20:
                frequency_multiplier *= 0.7
            elif width > 60:
                frequency_multiplier *= 1.3

        if "std" in ind:
            std = ind["std"]
            if std < 1.5:
                frequency_multiplier *= 0.8
            elif std > 2.5:
                frequency_multiplier *= 1.2

    final_frequency = base_frequency * frequency_multiplier

    return min(100.0, max(1.0, final_frequency))


def calculate_signal_accuracy(cfg):

    if not cfg:
        return DEFAULT_ACCURACY

    enabled_indicators = []
    for _, ind in cfg.items():
        if isinstance(ind, dict) and ind.get("enabled", True):
            enabled_indicators.append(ind)

    if not enabled_indicators:
        return DEFAULT_ACCURACY

    indicator_count = len(enabled_indicators)

    if indicator_count == 1:
        base_accuracy = 65.0
    elif indicator_count == 2:
        base_accuracy = 72.0
    elif indicator_count == 3:
        base_accuracy = 76.0
    elif indicator_count == 4:
        base_accuracy = 79.0
    elif indicator_count == 5:
        base_accuracy = 81.0
    else:
        base_accuracy = 82.0

    accuracy_bonus = 0

    for ind in enabled_indicators:
        if "period" in ind and ind["period"] > 20:
            accuracy_bonus += 1.0

        if "min" in ind and "max" in ind:
            width = ind["max"] - ind["min"]
            if width < 30:
                accuracy_bonus += 2.0

    final_accuracy = base_accuracy + accuracy_bonus

    return min(90.0, final_accuracy)


def calculate_risk_level(cfg, accuracy):

    base_risk = 100.0 - accuracy

    enabled_indicators = []
    for _, ind in cfg.items():
        if isinstance(ind, dict) and ind.get("enabled", True):
            enabled_indicators.append(ind)

    indicator_count = len(enabled_indicators)

    if indicator_count == 1:
        base_risk += 10.0
    elif indicator_count >= 5:
        base_risk -= 5.0

    for ind in enabled_indicators:
        if "period" in ind and ind["period"] < 10:
            base_risk += 5.0
            break

    return max(10.0, min(90.0, base_risk))


class BotMetrics(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        cfg = request.data or {}

        indicator_cfg = extract_indicator_config(cfg)

        if not indicator_cfg:
            return Response(
                {
                    "signal_frequency": DEFAULT_FREQUENCY,
                    "signal_accuracy": DEFAULT_ACCURACY,
                    "risk_level": DEFAULT_RISK,
                },
                status=status.HTTP_200_OK,
            )

        freq = calculate_signal_frequency(indicator_cfg)
        acc = calculate_signal_accuracy(indicator_cfg)
        risk = calculate_risk_level(indicator_cfg, acc)

        return Response(
            {
                "signal_frequency": round(freq, 2),
                "signal_accuracy": round(acc, 2),
                "risk_level": round(risk, 2),
            },
            status=status.HTTP_200_OK,
        )


class CreateBotBalance(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user
        id = data.get("bot", "")
        bot = Bot.objects.get(id=id)
        if not bot.published:
            if bot.owner == user:
                serializer = BotBalanceSerializer(data=data, context={"request": request})
            else:
                return Response({"error": "You are not the owner of this bot"}, status=403)
        else:
            serializer = BotBalanceSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response({"status": "ok"}, status=201)
