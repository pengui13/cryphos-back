from collections.abc import Callable
from decimal import Decimal
from functools import partial

import pandas as pd
import redis
import ta.momentum
import ta.trend
import ta.volatility
from django.conf import settings


class RedisService:

    r = redis.from_url(settings.REDIS_URL,
                       decode_responses=True)

    @classmethod
    def get_values(cls,
                   list_of_fields: list[str],
                   key_of_map: str = None,
                   transform: Callable | None = None) -> dict:
        with cls.r.pipeline() as pipe:
            extract_function = partial(pipe.hget, key_of_map) \
                               if key_of_map else pipe.get
            [extract_function(field) for field in list_of_fields]
            results = dict(zip(list_of_fields, pipe.execute()))
        if transform:
            return {k: transform(v) for k, v in results.items()
                    if v is not None}
        return results

    @classmethod
    def set_values(cls,
                   list_of_fields: list[str],
                   list_of_values: list[str],
                   key_of_map: str = None,
                   transform: Callable | None = None) -> None:
        if transform:
            list_of_values = list(map(transform, list_of_values))
        with cls.r.pipeline() as pipe:
            extract_function = partial(pipe.hset, key_of_map) \
                    if key_of_map else pipe.set
            [extract_function(field, value) for field, value in
             zip(list_of_fields, list_of_values)]
            pipe.execute()

class IndicatorsCalc:

    def calculate_rsi(self, prices: list[Decimal],
                      period: int = 14) -> float | None:
        if len(prices) < period + 1:
            return None

        close = pd.Series([float(p) for p in reversed(prices)])
        rsi = ta.momentum.RSIIndicator(close=close, window=period).rsi().iloc[-1]

        return round(rsi, 2) if pd.notna(rsi) else None

    def calculate_bollinger_bands(
        self, prices: list[Decimal], period: int = 20, std_dev: float = 2.0
    ) -> dict[str, float] | None:
        if len(prices) < period:
            return None

        close = pd.Series([float(p) for p in reversed(prices)])
        bb = ta.volatility.BollingerBands(close=close, window=period, window_dev=int(std_dev))
        upper = bb.bollinger_hband().iloc[-1]
        middle = bb.bollinger_mavg().iloc[-1]
        lower = bb.bollinger_lband().iloc[-1]

        if not all(pd.notna(v) for v in [upper, middle, lower]):
            return None

        return {
            "upper": round(upper, 4),
            "middle": round(middle, 4),
            "lower": round(lower, 4),
        }

    def calculate_support_resistance(
        self, quotes: list, lookback: int = 50, num_levels: int = 6
    ) -> list[float] | None:
        """
        Calculate support and resistance levels using local highs/lows.

        Args:
            quotes: List of HistQuotes objects (ordered by time DESC)
            lookback: Number of candles to analyze
            num_levels: Number of S/R levels to return

        Returns:
            List of price levels sorted ascending, or None
        """
        if len(quotes) < lookback:
            return None

        quotes_to_analyze = quotes[:lookback]
        levels = []

        for i in range(1, len(quotes_to_analyze) - 1):
            current = float(quotes_to_analyze[i].high_price)
            prev = float(quotes_to_analyze[i - 1].high_price)
            next_q = float(quotes_to_analyze[i + 1].high_price)

            if current > prev and current > next_q:
                levels.append(current)

            current_low = float(quotes_to_analyze[i].low_price)
            prev_low = float(quotes_to_analyze[i - 1].low_price)
            next_low = float(quotes_to_analyze[i + 1].low_price)

            if current_low < prev_low and current_low < next_low:
                levels.append(current_low)

        if not levels:
            return None

        clustered_levels = self._cluster_levels(levels, threshold=0.005)
        clustered_levels.sort()

        return clustered_levels[:num_levels]

    def _cluster_levels(self, levels: list[float], threshold: float = 0.005) -> list[float]:
        """
        Cluster price levels that are close together.

        Args:
            levels: List of price levels
            threshold: Percentage threshold for clustering (0.005 = 0.5%)

        Returns:
            List of clustered levels (averages of clusters)
        """
        if not levels:
            return []

        sorted_levels = sorted(levels)
        clusters = []
        current_cluster = [sorted_levels[0]]

        for i in range(1, len(sorted_levels)):
            current_level = sorted_levels[i]
            cluster_avg = sum(current_cluster) / len(current_cluster)

            if abs(current_level - cluster_avg) / cluster_avg <= threshold:
                current_cluster.append(current_level)
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [current_level]

        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))

        return [round(level, 2) for level in clusters]

    def calculate_macd(
        self, quotes: list, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> dict[str, float] | None:
        if len(quotes) < slow_period + signal_period:
            return None

        close = pd.Series([float(q.close_price) for q in quotes])
        macd = ta.trend.MACD(
            close=close,
            window_fast=fast_period,
            window_slow=slow_period,
            window_sign=signal_period,
        )

        macd_line = macd.macd().iloc[-1]
        signal_line = macd.macd_signal().iloc[-1]
        histogram = macd.macd_diff().iloc[-1]

        if not all(pd.notna(v) for v in [macd_line, signal_line, histogram]):
            return None

        return {
            "macd": round(macd_line, 4),
            "signal": round(signal_line, 4),
            "histogram": round(histogram, 4),
        }

    def calculate_ema(self, prices: list[Decimal], period: int) -> float | None:
        if len(prices) < period:
            return None

        close = pd.Series([float(p) for p in reversed(prices)])
        ema = ta.trend.EMAIndicator(close=close, window=period).ema_indicator().iloc[-1]

        return round(ema, 4) if pd.notna(ema) else None

    def calculate_ma(self, prices: list[Decimal], period: int) -> float | None:
        if len(prices) < period:
            return None

        close = pd.Series([float(p) for p in reversed(prices)])
        sma = ta.trend.SMAIndicator(close=close, window=period).sma_indicator().iloc[-1]

        return round(sma, 4) if pd.notna(sma) else None
