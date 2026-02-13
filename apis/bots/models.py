from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from assets.models import AssetCryptoCoin
from django.core.validators import MinValueValidator, MaxValueValidator

User = settings.AUTH_USER_MODEL


class MainBotSettings(models.Model):
    max_signals = models.IntegerField(default=50)
    signals_left = models.IntegerField(default=50)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bot_user_settings",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "bot_settings"

    def update_signals_left(self):

        cutoff = timezone.now() - timedelta(hours=24)

        user_bots = Bot.objects.filter(owner=self.user)

        recent_count = BotSignal.objects.filter(bot__in=user_bots, created_at__gte=cutoff).count()

        self.signals_left = max(self.max_signals - recent_count, 0)

        self.save(update_fields=["signals_left"])
        return self.signals_left


class Bot(models.Model):

    class VerificationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bots_owner", blank=True, null=True
    )
    published = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.DRAFT,
    )
    description = models.TextField(blank=True, null=True)
    roi = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    pnl = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    accuracy = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    frequency = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    risk = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    max_drawdown = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    runtime = models.BigIntegerField(default=0)
    last_activated = models.DateTimeField(null=True, blank=True)
    users = models.ManyToManyField(User, related_name="bots_users", blank=True, null=True)
    intersection = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    bot_assets = models.ManyToManyField("assets.AssetCryptoCoin", related_name="bots", blank=True)

    class Meta:
        db_table = "bot"

    def activate(self):
        now = timezone.now()
        self.is_active = True
        self.last_activated = now
        self.last_heartbeat = now
        self.save(update_fields=["is_active", "last_activated", "last_heartbeat"])
        return True

    def deactivate(self):
        if self.is_active and self.last_activated:
            now = timezone.now()
            session_runtime = int((now - self.last_activated).total_seconds())

            today = now.date().isoformat()

            self.runtime += session_runtime
            self.is_active = False
            self.last_activated = None
            self.save(
                update_fields=[
                    "runtime",
                    "is_active",
                    "last_activated",
                ]
            )

            return session_runtime
        return 0

    def __str__(self):
        return self.name


class RiskSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="risk_settings")
    take_profit = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)


class BotBalance(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="balances")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bot_balances")
    initial_balance = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    current_balance = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    take_profit = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    unrealised_pnl = models.DecimalField(max_digits=20, decimal_places=10, default=0)

    class Meta:
        unique_together = ("bot", "user")

    def __str__(self):
        return f"{self.bot.name}"


class BaseIndicator(models.Model):
    INTERVAL_CHOICES = [
        ("1MIN", "1 minute"),
        ("5MIN", "5 minutes"),
        ("15MIN", "15 minutes"),
        ("30MIN", "30 minutes"),
        ("1HRS", "1 hour"),
        ("1DAY", "1 day"),
    ]

    intervals = ArrayField(
        models.CharField(max_length=10, choices=INTERVAL_CHOICES),
        blank=True,
        default=list,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.__class__.__name__}: {self.intervals}"


class RsiIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="rsi_indicators", on_delete=models.CASCADE)
    min = models.IntegerField(default=30)
    max = models.IntegerField(default=70)
    period = models.IntegerField(default=14)

    class Meta:
        verbose_name = "RSI Indicator"
        verbose_name_plural = "RSI Indicators"


def default_sr_intervals():
    return ["5m", "15m", "1h"]


class SupportResistanceIndicator(BaseIndicator):

    MODE_CHOICES = [
        ("rolling", "Rolling High/Low"),
        ("pivots", "Pivot Points"),
        ("both", "Rolling + Pivots"),
    ]
    ZONE_MODE_CHOICES = [
        ("atr", "ATR-based"),
        ("fixed", "Fixed percent of price"),
    ]
    PIVOT_TYPE_CHOICES = [
        ("classic", "Classic"),
        ("fibo", "Fibonacci"),
        ("woodie", "Woodie"),
        ("camarilla", "Camarilla"),
    ]
    PIVOT_TF_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    bot = models.ForeignKey(
        "bots.Bot",
        related_name="sr_indicators",
        on_delete=models.CASCADE,
    )

    mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default="both",
    )

    lookback = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(1)],
    )
    levels_count = models.PositiveIntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
    )

    zone_mode = models.CharField(
        max_length=5,
        choices=ZONE_MODE_CHOICES,
        default="atr",
    )

    atr_period = models.PositiveIntegerField(
        default=14,
        validators=[MinValueValidator(1)],
    )

    atr_mult = models.FloatField(
        default=0.75,
        validators=[MinValueValidator(0.0)],
    )

    fixed_width = models.FloatField(
        default=0.002,
        validators=[MinValueValidator(0.0), MaxValueValidator(0.5)],
    )

    merge_dist_atr = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0)],
    )

    pivot_type = models.CharField(
        max_length=10,
        choices=PIVOT_TYPE_CHOICES,
        default="classic",
    )

    pivot_tf = models.CharField(
        max_length=7,
        choices=PIVOT_TF_CHOICES,
        default="daily",
    )

    vwap_enabled = models.BooleanField(
        default=True,
    )

    vwap_bands = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
    )

    class Meta:
        verbose_name = "Support/Resistance Indicator"
        verbose_name_plural = "Support/Resistance Indicators"

    def __str__(self):
        return f"S/R for bot #{self.bot_id} ({self.mode}, n={self.lookback})"

    def uses_rolling(self) -> bool:
        return self.mode in ("rolling", "both")

    def uses_pivots(self) -> bool:
        return self.mode in ("pivots", "both")

    def clean(self):

        from django.core.exceptions import ValidationError

        if self.zone_mode == "atr" and self.atr_mult <= 0:
            raise ValidationError({"atr_mult": "For ATR > 0"})

        if self.zone_mode == "fixed" and self.fixed_width <= 0:
            raise ValidationError({"fixed_width": "For fixed > 0"})


class MaIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="ma_indicators", on_delete=models.CASCADE)
    period = models.IntegerField(default=20)

    class Meta:
        verbose_name = "Moving Average Indicator"
        verbose_name_plural = "Moving Average Indicators"

    def clean(self):
        if not (0 <= self.lower <= 100 and 0 <= self.upper <= 100):
            raise ValidationError("Bounds must be between 0 and 100.")
        if self.lower >= self.upper:
            raise ValidationError("Lower must be less than upper.")


class MacdIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="macd_indicators", on_delete=models.CASCADE)
    fast_period = models.IntegerField(default=12)
    slow_period = models.IntegerField(default=26)
    signal_period = models.IntegerField(default=9)

    class Meta:
        verbose_name = "MACD Indicator"
        verbose_name_plural = "MACD Indicators"


class FnGValue(models.Model):
    value = models.PositiveSmallIntegerField(default=0)
    classification = models.CharField(max_length=100)
    timestamp = models.PositiveBigIntegerField(default=0)
    time_until_update = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return f"{self.classification} - {self.value} - {self.timestamp}"

    class Meta:
        verbose_name = "Fear and Greed Value"
        verbose_name_plural = "Fear and Greed Values"
        ordering = ["-timestamp"]


class Signal(models.Model):
    asset = models.ForeignKey(AssetCryptoCoin, on_delete=models.CASCADE)
    open_price = models.DecimalField(max_digits=20, decimal_places=8)
    close_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    is_long = models.BooleanField(default=True)
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="bot_signals")
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "signal"
        verbose_name = "Signal"
        verbose_name_plural = "Signals"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["bot", "asset"],
                condition=models.Q(is_open=True),
                name="unique_open_signal_per_bot_asset",
            )
        ]

    def __str__(self):
        direction = "LONG" if self.is_long else "SHORT"
        status = "OPEN" if self.is_open else "CLOSED"
        return f"{self.bot.name} - {self.asset.symbol} - {direction} - {status}"


class BollingerBandsIndicator(BaseIndicator):
    bot = models.ForeignKey(
        Bot, related_name="bollinger_bands_indicators", on_delete=models.CASCADE
    )
    period = models.IntegerField(default=20)
    std_dev = models.FloatField(default=2.0)

    class Meta:
        verbose_name = "Bollinger Bands Indicator"
        verbose_name_plural = "Bollinger Bands Indicators"


class FundingRate(models.Model):
    asset = models.ForeignKey(AssetCryptoCoin, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    funding_time = models.BigIntegerField()
    exchange = models.CharField(max_length=100)


class AtrIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="atr_indicators", on_delete=models.CASCADE)
    period = models.IntegerField(default=14)

    class Meta:
        verbose_name = "ATR Indicator"
        verbose_name_plural = "ATR Indicators"


class ObvIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="obv_indicators", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "OBV Indicator"
        verbose_name_plural = "OBV Indicators"


class BaseIndicatorValue(models.Model):
    quote = models.OneToOneField("assets.HistQuotes", on_delete=models.CASCADE)

    class Meta:
        abstract = True


class RsiValue(BaseIndicatorValue):
    value = models.DecimalField(max_digits=20, decimal_places=10)
    indicator = models.ForeignKey(
        RsiIndicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rsi_values",
    )

    class Meta:
        verbose_name = "RSI Value"
        verbose_name_plural = "RSI Values"


class MaValue(BaseIndicatorValue):
    value = models.DecimalField(max_digits=20, decimal_places=10)
    indicator = models.ForeignKey(
        MaIndicator,
        on_delete=models.SET_NULL,
        related_name="ma_values",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "MA Value"
        verbose_name_plural = "MA Values"
        ordering = ["quote__time"]


class MacdValue(BaseIndicatorValue):
    value = models.DecimalField(max_digits=20, decimal_places=10)
    signal = models.DecimalField(max_digits=20, decimal_places=10)
    histogram = models.DecimalField(max_digits=20, decimal_places=10)
    indicator = models.ForeignKey(
        MacdIndicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="macd_values",
    )

    class Meta:
        verbose_name = "MACD Value"
        verbose_name_plural = "MACD Values"
        ordering = ["quote__time"]


class BollingerBandsValue(BaseIndicatorValue):
    upper_band = models.DecimalField(max_digits=20, decimal_places=10)
    lower_band = models.DecimalField(max_digits=20, decimal_places=10)
    middle_band = models.DecimalField(max_digits=20, decimal_places=10)
    indicator = models.ForeignKey(
        BollingerBandsIndicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bollinger_bands_values",
    )

    class Meta:
        verbose_name = "Bollinger Bands Value"
        verbose_name_plural = "Bollinger Bands Values"
        ordering = ["quote__time"]


class AtrValue(BaseIndicatorValue):
    value = models.DecimalField(max_digits=20, decimal_places=10)
    indicator = models.ForeignKey(
        AtrIndicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atr_values",
    )

    class Meta:
        verbose_name = "ATR Value"
        verbose_name_plural = "ATR Values"
        ordering = ["quote__time"]


class ObvValue(BaseIndicatorValue):
    value = models.DecimalField(max_digits=20, decimal_places=10)
    indicator = models.ForeignKey(
        ObvIndicator,
        related_name="obv_values",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.quote}"

    class Meta:
        verbose_name = "OBV Value"
        verbose_name_plural = "OBV Values"
        ordering = ["quote__time"]


class BotSignal(models.Model):

    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="signals")
    balance = models.ForeignKey(
        BotBalance,
        on_delete=models.CASCADE,
        related_name="signals",
        blank=True,
        null=True,
    )
    asset = models.ForeignKey(
        "assets.AssetCryptoCoin", on_delete=models.CASCADE, related_name="signals"
    )
    is_long = models.BooleanField(default=False)
    status = models.CharField(max_length=10, default="Pending")

    quantity = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    entry_price = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    exit_price = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    pnl = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Bot Signal"
        verbose_name_plural = "Bot Signals"
        ordering = ["-created_at"]

    def __str__(self):
        signal_direction = "BUY" if self.is_long else "SELL"
        return f"{self.bot.name} - {signal_direction} - {self.status}"


class BotStat(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="stats")
    pnl = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bot_stats"


class UserBalance(models.Model):
    quantity = models.DecimalField(max_digits=15, decimal_places=8, default=0)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_balance",
        blank=True,
        null=True,
    )
