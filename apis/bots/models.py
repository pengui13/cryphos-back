from decimal import Decimal

from assets.models import AssetCryptoCoin
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = settings.AUTH_USER_MODEL

_RISK_VALIDATORS = [MinValueValidator(Decimal("0.01")),
                    MaxValueValidator(Decimal("100"))]

INTERVALS = [
        ("1MIN", "1 minute"),
        ("5MIN", "5 minutes"),
        ("15MIN", "15 minutes"),
        ("30MIN", "30 minutes"),
        ("1HRS", "1 hour"),
        ("1DAY", "1 day"),
    ]


class VerificationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class RiskSettings(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name="risk_settings")
    take_profit = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=_RISK_VALIDATORS,
    )
    stop_loss = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=_RISK_VALIDATORS,
    )

    def __str__(self):
        return f"{self.user.email} | {self.take_profit} | {self.stop_loss}"

    class Meta:
        verbose_name = verbose_name_plural = "Risk Settings"


class Bot(models.Model):

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bots_owner",
        blank=True, null=True
    )
    users = models.ManyToManyField(
                User,
                related_name="bots_users",
                blank=True,
                null=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.DRAFT,
    )
    description = models.TextField(blank=True, null=True)
    roi = models.DecimalField(max_digits=20,
                              decimal_places=10,
                              default=0)
    published = models.BooleanField(default=False)
    pnl = models.DecimalField(max_digits=20,
                              decimal_places=10,
                              default=0)
    last_activated = models.DateTimeField(null=True, blank=True)
    bot_assets = models.ManyToManyField("assets.AssetCryptoCoin",
                                        related_name="bots",
                                        blank=True)

    @property
    def fibo_indicator(self):
        return self.fibo_indicators.first()

    def __str__(self):
        return f"{self.owner.email}"


class BaseIndicator(models.Model):

    intervals = ArrayField(
        models.CharField(max_length=10, choices=INTERVALS),
        blank=True,
        default=list,
    )

    class Meta:
        abstract = True


class RsiIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot,
                            related_name="rsi_indicators",
                            on_delete=models.CASCADE)
    min = models.IntegerField(default=30)
    max = models.IntegerField(default=70)
    period = models.IntegerField(default=14)

    class Meta:
        verbose_name = "RSI Indicator"
        verbose_name_plural = "RSI Indicators"

    def __str__(self):
        return f"{self.bot.owner.email} | \
        min={self.min} | max={self.max} | \
        period={self.period} | \
        intervals={[f'| {interval} ' for interval in self.intervals]}|"


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
        return f"S/R for bot #{self.bot.owner.email}|{self.mode} | \
                n={self.lookback})"

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
    bot = models.ForeignKey(Bot, related_name="ma_indicators", 
                            on_delete=models.CASCADE)
    period = models.IntegerField(default=20)

    class Meta:
        verbose_name = "Moving Average Indicator"
        verbose_name_plural = "Moving Average Indicators"

    def __str__(self):
        return f"{self.bot.owner.email}|period={self.period}| \
                 intervals={[f'{interval}|' for interval in self.intervals]}"

    def clean(self):
        if not (0 <= self.lower <= 100 and 0 <= self.upper <= 100):
            raise ValidationError("Bounds must be between 0 and 100.")
        if self.lower >= self.upper:
            raise ValidationError("Lower must be less than upper.")


class MacdIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="macd_indicators", 
                            on_delete=models.CASCADE)
    fast_period = models.IntegerField(default=12)
    slow_period = models.IntegerField(default=26)
    signal_period = models.IntegerField(default=9)

    class Meta:
        verbose_name = "MACD Indicator"
        verbose_name_plural = "MACD Indicators"


class FiboIndicator(BaseIndicator):
    LEVEL_CHOICES = [
        ("0", "0%"),
        ("23.6", "23.6%"),
        ("38.2", "38.2%"),
        ("50", "50%"),
        ("61.8", "61.8%"),
        ("78.6", "78.6%"),
        ("100", "100%"),
    ]
    bot = models.ForeignKey(Bot, related_name="fibo_indicators",
                            on_delete=models.CASCADE)
    period = models.IntegerField(default=50)
    levels = ArrayField(
        models.DecimalField(max_digits=5, decimal_places=1),
        default=list,
    )

    def __str__(self):
        return f"{self.period}|{[f'{level}|' for level in self.levels]}"


class Signal(models.Model):
    asset = models.ForeignKey(AssetCryptoCoin,
                              related_name="signal_asset",
                              on_delete=models.CASCADE)
    bot = models.ForeignKey(Bot,
                            on_delete=models.CASCADE,
                            related_name="bot_signals")
    open_price = models.DecimalField(max_digits=20, decimal_places=8)
    close_price = models.DecimalField(max_digits=20, decimal_places=8,
                                      null=True, blank=True)
    is_long = models.BooleanField(default=True)
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
        return f"{self.bot.owner.email}|\
                {self.asset.symbol}|{direction}|{status}"


class BollingerBandsIndicator(BaseIndicator):
    bot = models.ForeignKey(
        Bot,
        related_name="bollinger_bands_indicators",
        on_delete=models.CASCADE
    )
    period = models.IntegerField(default=20)
    std_dev = models.FloatField(default=2.0)

    class Meta:
        verbose_name = "Bollinger Bands Indicator"
        verbose_name_plural = "Bollinger Bands Indicators"

    def __str__(self):
        return f"{self.bot.owner.email}|period={self.period}|\
                std_dev={self.std_dev}|\
                intervals={[f'{interval}|' for interval in self.intervals]}"


class FundingRate(models.Model):
    asset = models.ForeignKey(AssetCryptoCoin, related_name='assets_funding',
                              on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    funding_time = models.BigIntegerField()
    exchange = models.CharField(max_length=100)

    class Meta:
        unique_together = ["asset", "exchange"]


class AtrIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="atr_indicators",
                            on_delete=models.CASCADE)
    period = models.IntegerField(default=14)

    class Meta:
        verbose_name = "ATR Indicator"
        verbose_name_plural = "ATR Indicators"


class ObvIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="obv_indicators",
                            on_delete=models.CASCADE)

    class Meta:
        verbose_name = "OBV Indicator"
        verbose_name_plural = "OBV Indicators"


class EmaIndicator(BaseIndicator):
    bot = models.ForeignKey(Bot, related_name="ema_indicators",
                            on_delete=models.CASCADE)
    period = models.IntegerField(default=14)

    class Meta:
        verbose_name = "EMA Indicator"
        verbose_name_plural = "EMA Indicators"


class BaseIndicatorValue(models.Model):
    quote = models.OneToOneField("assets.HistQuotes", on_delete=models.CASCADE)

    class Meta:
        abstract = True
