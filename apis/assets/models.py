from django.db import models


class AssetCryptoCoin(models.Model):
    symbol = models.CharField(max_length=60)
    sector = models.CharField(max_length=200, default="", blank=True,
                              null=True)
    name = models.CharField(max_length=200)
    rank = models.IntegerField(default=0)
    icon_url = models.CharField(max_length=300, default="URL")
    trading_pair = models.CharField(max_length=200, default="")
    color = models.CharField(max_length=20, default="")

    class Meta:
        indexes = [
            models.Index(fields=["symbol"]),
        ]

    def __str__(self):
        return f"{self.symbol} {self.name}"


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
    trade_count = models.DecimalField(max_digits=20, decimal_places=10,
                                      null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "interval", "time"],
                name="unique_symbol_interval_time",
            )
        ]

    def __str__(self):
        return f"{self.symbol} - {self.interval} - {self.close_price}"
