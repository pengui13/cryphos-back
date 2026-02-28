import asyncio
import json
from datetime import UTC, datetime
import redis.asyncio as redis
import websockets
from django.conf import settings

OKX_URL = "wss://ws.okx.com:8443/ws/v5/public"



BUCKET_SIZES = {
    "BTCUSDT": 100,
    "ETHUSDT": 10,
    "default": 0.01,
}

TTL_SECONDS = 86400


class LiquidationFetcher:
    def __init__(self):
        self.running = False
        self.redis: redis.Redis = None

    async def start(self):
        self.running = True
        self.redis = await redis.from_url(settings.REDIS_URL)
        print("Connected to Redis")

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
        async with websockets.connect(OKX_URL) as ws:
            subscribe_msg = {
                "op": "subscribe",
                "args": [{"channel": "liquidation-orders", "instType": "SWAP"}],
            }
            await ws.send(json.dumps(subscribe_msg))
            print("Subscribed to OKX liquidations")

            asyncio.create_task(self._ping_loop(ws))

            async for message in ws:
                await self._handle_message(message)

    async def _ping_loop(self, ws):
        while self.running:
            try:
                await ws.send("ping")
                await asyncio.sleep(20)
            except Exception as e:
                print(e)
                break

    async def _handle_message(self, message: str | bytes):
        if message == "pong":
            return

        try:
            data = json.loads(message)
        except Exception as e:
            print(e)
            return

        if "data" not in data:
            return

        for item in data.get("data", []):
            inst_id = item.get("instId", "")
            for detail in item.get("details", []):
                await self._process_liquidation(inst_id, detail)

    async def _process_liquidation(self, inst_id: str, detail: dict):
        side = detail.get("side", "").lower()
        size = float(detail.get("sz", 0))
        price = float(detail.get("bkPx", 0))

        symbol = inst_id.replace("-SWAP", "").replace("-", "")

        usd_value = size * price
        liq_type = "short" if side == "buy" else "long"

        liquidation = {
            "symbol": symbol,
            "type": liq_type,
            "price": price,
            "qty": size,
            "usd": usd_value,
            "ts": datetime.now(UTC).isoformat(),
            "exchange": "okx",
        }

        # Publish to Redis pub/sub for WebSocket clients
        await self.redis.publish("liquidations", json.dumps(liquidation))

        # Store in recent liquidations list (for initial load)
        await self.redis.lpush("recent_liquidations", json.dumps(liquidation))
        await self.redis.ltrim("recent_liquidations", 0, 99)  # Keep last 100

        # Heatmap data
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
            pipe.lpush("big_liquidations", json.dumps(liquidation))
            pipe.ltrim("big_liquidations", 0, 99)

        await pipe.execute()

        print(f"{symbol} {liq_type.upper()} ${usd_value:,.0f} @ {price:,.2f}")


async def main():
    fetcher = LiquidationFetcher()
    try:
        await fetcher.start()
    except KeyboardInterrupt:
        await fetcher.stop()


if __name__ == "__main__":
    asyncio.run(main())
