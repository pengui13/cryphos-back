import asyncio
import json
from datetime import UTC, datetime
import redis.asyncio as redis
import websockets
from django.conf import settings
from loguru import logger


class LiquidationFetcher:

    def __init__(self):
        self.running = False
        self.redis = None

    async def start(self):
        self.running = True
        self.redis = await redis.from_url(settings.REDIS_URL)

        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"Error: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.redis:
            await self.redis.close()

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

        await self.redis.publish("liquidations", json.dumps(liquidation))
        await self.redis.lpush("recent_liquidations", json.dumps(liquidation))
        await self.redis.ltrim("recent_liquidations", 0, 99)

    async def _connect_and_listen(self):
        async with websockets.connect(settings.OKX_URL) as ws:
            subscribe_msg = {
                "op": "subscribe",
                "args": [{"channel": "liquidation-orders",
                          "instType": "SWAP"}],
            }
            await ws.send(json.dumps(subscribe_msg))

            asyncio.create_task(self._ping_loop(ws))

            async for message in ws:
                await self._handle_message(message)

    async def _handle_message(self, message: str | bytes):
        if message == "pong":
            return

        try:
            data = json.loads(message)
        except Exception as e:
            logger.error(e)
            return

        if "data" not in data:
            return

        for item in data.get("data", []):
            inst_id = item.get("instId", "")
            for detail in item.get("details", []):
                await self._process_liquidation(inst_id, detail)

    async def _ping_loop(self, ws):
        while self.running:
            try:
                await ws.send("ping")
                await asyncio.sleep(20)
            except Exception as e:
                logger.error(e)
                break


async def main():
    fetcher = LiquidationFetcher()
    try:
        await fetcher.start()
    except KeyboardInterrupt:
        await fetcher.stop()


if __name__ == "__main__":
    asyncio.run(main())
