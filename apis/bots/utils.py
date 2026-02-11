"""
Indicators calculation utilities for trading bots.
"""
import logging
from typing import List, Optional, Dict
from decimal import Decimal
import statistics

logger = logging.getLogger(__name__)


class IndicatorsCalc:
    """Calculate technical indicators from historical quotes."""

    def calculate_rsi_for_quote(self, quote, period: int = 14) -> Optional[float]:
        """
        Calculate RSI using Wilder's Smoothing Method (matches TradingView).
        Requires at least 'period * 2' historical quotes for proper warmup.
        """
        from assets.models import HistQuotes
        
        # Fetch more candles for proper smoothing (warmup period)
        quotes = (
            HistQuotes.objects
            .filter(symbol=quote.symbol, interval=quote.interval)
            .filter(time__lte=quote.time)
            .order_by("-time")[: period * 4 + 1]  # Get enough for warmup
        )

        if len(quotes) < period + 1:
            logger.warning(f"Not enough data for RSI: need {period + 1}, got {len(quotes)}")
            return None

        # Reverse to chronological order (oldest first) for calculation
        quotes = list(reversed(quotes))
        
        # Calculate price changes
        changes = []
        for i in range(1, len(quotes)):
            current = float(quotes[i].close_price)
            previous = float(quotes[i - 1].close_price)
            change = current - previous
            changes.append(change)
        
        if len(changes) < period:
            return None
        
        # Separate gains and losses
        gains = [max(change, 0) for change in changes]
        losses = [abs(min(change, 0)) for change in changes]
        
        # STEP 1: Calculate first average gain/loss (Simple Moving Average)
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        # STEP 2: Apply Wilder's Smoothing for remaining candles
        # This is the KEY difference from your code!
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        # STEP 3: Calculate RSI
        if avg_loss == 0:
            return 100.0  # All gains, RSI = 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)

    def calculate_bollinger_bands(
        self, 
        quotes: List, 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands.
        
        Args:
            quotes: List of HistQuotes objects (ordered by time DESC)
            period: SMA period (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)
        
        Returns:
            Dict with 'upper', 'middle', 'lower' bands or None
        """
        if len(quotes) < period:
            return None

        # Get closing prices
        closes = [float(q.close_price) for q in quotes[:period]]

        # Calculate SMA (middle band)
        sma = sum(closes) / period

        # Calculate standard deviation
        variance = sum((x - sma) ** 2 for x in closes) / period
        std = variance ** 0.5

        # Calculate bands
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)

        return {
            "upper": round(upper_band, 2),
            "middle": round(sma, 2),
            "lower": round(lower_band, 2),
            "std": round(std, 2),
        }

    def calculate_support_resistance(
        self, 
        quotes: List, 
        lookback: int = 50,
        num_levels: int = 6
    ) -> Optional[List[float]]:
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
        
        # Find local highs and lows
        levels = []
        
        for i in range(1, len(quotes_to_analyze) - 1):
            current = float(quotes_to_analyze[i].high_price)
            prev = float(quotes_to_analyze[i - 1].high_price)
            next_q = float(quotes_to_analyze[i + 1].high_price)
            
            # Local high
            if current > prev and current > next_q:
                levels.append(current)
            
            # Local low
            current_low = float(quotes_to_analyze[i].low_price)
            prev_low = float(quotes_to_analyze[i - 1].low_price)
            next_low = float(quotes_to_analyze[i + 1].low_price)
            
            if current_low < prev_low and current_low < next_low:
                levels.append(current_low)

        if not levels:
            return None

        # Cluster similar levels (within 0.5% of each other)
        clustered_levels = self._cluster_levels(levels, threshold=0.005)
        
        # Sort and return top N levels
        clustered_levels.sort()
        
        return clustered_levels[:num_levels]

    def _cluster_levels(self, levels: List[float], threshold: float = 0.005) -> List[float]:
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
            
            # Check if current level is within threshold of cluster average
            if abs(current_level - cluster_avg) / cluster_avg <= threshold:
                current_cluster.append(current_level)
            else:
                # Save current cluster and start new one
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [current_level]

        # Don't forget the last cluster
        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))

        return [round(level, 2) for level in clusters]

    def calculate_macd(
        self,
        quotes: List,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            quotes: List of HistQuotes objects (ordered by time DESC)
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line EMA period (default: 9)
        
        Returns:
            Dict with 'macd', 'signal', 'histogram' or None
        """
        if len(quotes) < slow_period + signal_period:
            return None

        closes = [float(q.close_price) for q in quotes]

        # Calculate EMAs
        fast_ema = self._calculate_ema(closes, fast_period)
        slow_ema = self._calculate_ema(closes, slow_period)

        if fast_ema is None or slow_ema is None:
            return None

        # MACD line = fast EMA - slow EMA
        macd_line = fast_ema - slow_ema

        # Calculate signal line (EMA of MACD)
        # For simplicity, using SMA here; proper implementation would use EMA
        macd_values = [macd_line]  # In real implementation, calculate for all periods
        signal_line = sum(macd_values[:signal_period]) / signal_period if len(macd_values) >= signal_period else macd_line

        # Histogram = MACD - Signal
        histogram = macd_line - signal_line

        return {
            "macd": round(macd_line, 4),
            "signal": round(signal_line, 4),
            "histogram": round(histogram, 4),
        }

    def _calculate_ema(self, values: List[float], period: int) -> Optional[float]:
        """
        Calculate Exponential Moving Average.
        
        Args:
            values: List of values (most recent first)
            period: EMA period
        
        Returns:
            EMA value or None
        """
        if len(values) < period:
            return None

        # Use SMA for initial EMA
        sma = sum(values[:period]) / period
        
        # Calculate multiplier
        multiplier = 2 / (period + 1)
        
        # Calculate EMA
        ema = sma
        for value in values[:period]:
            ema = (value - ema) * multiplier + ema

        return ema