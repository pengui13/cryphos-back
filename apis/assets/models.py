from django.db import models


class AssetCryptoCoin(models.Model):
    symbol = models.CharField(max_length=60)
    sector = models.CharField(max_length=200, default="", blank=True, null=True)
    name = models.CharField(max_length=200)
    rate = models.DecimalField(max_digits=15, decimal_places=8, blank=True, null=True)
    rank = models.IntegerField(default=0)
    icon_url = models.CharField(max_length=300, default="URL")
    pair = models.CharField(max_length=20, default="", blank=True, null=True)
    trading_pair = models.CharField(max_length=200, default="")
    volume = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    color = models.CharField(max_length=20, default="")

    class Meta:
        db_table = "asset_cryptocoin"
        indexes = [
            models.Index(fields=["symbol", "name"]),
        ]

    def __str__(self):
        return f"{self.symbol} {self.name} {self.rate}"

    def get_usdt_rate(self):
        return self.rate


class Quote(models.Model):
    id = models.BigAutoField(primary_key=True)
    symbol = models.ForeignKey(AssetCryptoCoin, on_delete=models.CASCADE)
    interval = models.CharField(max_length=10, null=True, blank=True)
    bid = models.DecimalField(max_digits=20, decimal_places=8)
    ask = models.DecimalField(max_digits=20, decimal_places=8)
    lp = models.DecimalField(max_digits=20, decimal_places=8, default=0, null=True, blank=True)
    volume = models.DecimalField(max_digits=20, decimal_places=8)

    open_price = models.DecimalField(max_digits=20, decimal_places=10)
    high_price = models.DecimalField(max_digits=20, decimal_places=10)
    low_price = models.DecimalField(max_digits=20, decimal_places=10)
    prev_close_price = models.DecimalField(max_digits=20, decimal_places=10, blank=True, null=True)
    max_24h = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    min_24h = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    time = models.DateTimeField(auto_now_add=True)
    perc_24 = models.FloatField(default=0)
    value_in_usd = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    class Meta:
        db_table = "quotes"
        unique_together = ("symbol", "interval")

    def __str__(self):
        return f"{self.symbol}"


class HistQuotes(models.Model):
    symbol = models.ForeignKey(
        AssetCryptoCoin, on_delete=models.CASCADE, related_name="hist_quotes"
    )
    interval = models.CharField(max_length=10, null=True, blank=True)
    volume = models.DecimalField(max_digits=30, decimal_places=15)
    time = models.BigIntegerField(default=1)
    open_price = models.DecimalField(max_digits=20, decimal_places=10)
    high_price = models.DecimalField(max_digits=20, decimal_places=10)
    low_price = models.DecimalField(max_digits=20, decimal_places=10)
    close_price = models.DecimalField(max_digits=20, decimal_places=10)
    trade_count = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)

    class Meta:
        db_table = "quotes_hist"
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "interval", "time"],
                name="unique_symbol_interval_time",
            )
        ]

    def __str__(self):
        return f"{self.symbol} - {self.interval} - {self.close_price}"
