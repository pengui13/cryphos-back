import websockets
import asyncio
import redis.asyncio as redis
from datetime import datetime
import json

BYBIT_URL = "wss://stream.bybit.com/v5/public/linear"
REDIS_URL = "redis://redis:6379/1"

BUCKET_SIZES = {
    "BTCUSDT": 100,
    "ETHUSDT": 10,
    "default": 0.01,
}

TTL_SECONDS = 86400


class LiquidationFetcher:
    SYMBOLS = [
        "BTCUSDT",
        "ETHUSDT",
        "XRPUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "SUIUSDT",
        "TRXUSDT",
        "LINKUSDT",
        "PEPEUSDT",
        "LTCUSDT",
        "AVAXUSDT",
        "TAOUSDT",
        "HBARUSDT",
        "BCHUSDT",
        "NEARUSDT",
        "AAVEUSDT",
        "UNIUSDT",
        "FILUSDT",
        "XLMUSDT",
        "WLDUSDT",
        "TRUMPUSDT",
        "ARBUSDT",
        "WIFUSDT",
        "DOTUSDT",
        "POLUSDT",
        "PENGUUSDT",
        "BONKUSDT",
        "SHIBUSDT",
        "ICPUSDT",
    ]

    def __init__(self):
        self.running = False
        self.redis: redis.Redis = None

    async def start(self):
        self.running = True
        self.redis = await redis.from_url(REDIS_URL)

        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                print(f"Error: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.redis:
            await self.redis.close()

    async def _connect_and_listen(self):
        async with websockets.connect(BYBIT_URL) as ws:
            subscribe_msg = {
                "op": "subscribe",
                "args": [f"liquidation.{symbol}" for symbol in self.SYMBOLS],
            }
            await ws.send(json.dumps(subscribe_msg))
            print(f"Subscribed to {len(self.SYMBOLS)} symbols")

            asyncio.create_task(self._ping_loop(ws))

            async for message in ws:
                await self._handle_message(message)

    async def _ping_loop(self, ws):
        while self.running:
            try:
                await ws.send(json.dumps({"op": "ping"}))
                await asyncio.sleep(20)
            except:
                break

    async def _handle_message(self, message: str):
        data = json.loads(message)

        if "topic" not in data or not data["topic"].startswith("liquidation"):
            return

        liq_data = data.get("data", {})

        symbol = liq_data.get("symbol", "")
        price = float(liq_data.get("price", 0))
        size = float(liq_data.get("size", 0))
        side = liq_data.get("side", "").lower()
        usd_value = size * price

        liq_type = "short" if side == "buy" else "long"

        bucket_size = BUCKET_SIZES.get(symbol, BUCKET_SIZES["default"])
        bucket = int(price // bucket_size) * bucket_size

        heatmap_key = f"heatmap:{symbol}"
        stats_key = f"stats:{symbol}"
        total_stats_key = "stats:total"

        pipe = self.redis.pipeline()

        pipe.hincrbyfloat(heatmap_key, f"{bucket}:{liq_type}", usd_value)
        pipe.expire(heatmap_key, TTL_SECONDS)

        pipe.hincrbyfloat(stats_key, f"{liq_type}_usd", usd_value)
        pipe.hincrby(stats_key, f"{liq_type}_count", 1)
        pipe.expire(stats_key, TTL_SECONDS)

        pipe.hincrbyfloat(total_stats_key, f"{liq_type}_usd", usd_value)
        pipe.hincrby(total_stats_key, "count", 1)
        pipe.expire(total_stats_key, TTL_SECONDS)

        if usd_value > 50_000:
            big_liq = json.dumps(
                {
                    "symbol": symbol,
                    "type": liq_type,
                    "price": price,
                    "usd": usd_value,
                    "ts": datetime.utcnow().isoformat(),
                }
            )
            pipe.lpush("big_liquidations", big_liq)
            pipe.ltrim("big_liquidations", 0, 99)

        await pipe.execute()

        if usd_value > 100_000:
            print(f"{symbol} {liq_type.upper()} ${usd_value:,.0f} @ {price:,.2f}")


async def main():
    fetcher = LiquidationFetcher()
    try:
        await fetcher.start()
    except KeyboardInterrupt:
        await fetcher.stop()


if __name__ == "__main__":
    asyncio.run(main())
