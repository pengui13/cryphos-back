import asyncio
import json
import random
from loguru import logger
import redis.asyncio as redis
import websockets
from django.conf import settings


class KlinesFetcher:

    def __init__(self):
        self.redis = None

    async def start(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        tasks = [asyncio.create_task(
                self.consume_interval(interval))
                for interval in settings.INTERVALS]
        await asyncio.gather(*tasks)

    def _build_url(self, interval: str) -> str:
        streams = [f"{s}@kline_{interval}" for s in settings.SYMBOLS]
        return settings.WS_BASE + "/".join(streams)

    async def _handle_message(self, raw: str):
        data = json.loads(raw).get("data", {})
        k = data.get("k", {})
        symbol = k.get("s")
        k_interval = k.get("i")
        if not symbol or not k_interval:
            return

        payload = {
            "base_vol": k.get("v"),
            "quote_vol": k.get("q"),
            "closed": bool(k.get("x")),
            "open_time": k.get("t"),
            "close_time": k.get("T"),
        }

        await self.redis.hset(
            settings.KLINES_HASH,
            f"{symbol}:{k_interval}",
            json.dumps(payload),
        )

    async def consume_interval(self, interval: str):
        backoff = 1.0
        url = self._build_url(interval)
        while True:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=10000,
                ) as ws:
                    async for raw in ws:
                        await self._handle_message(raw)

            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as e:
                sleep_for = self.backoff + random.random() * 0.25
                logger.error(e)
                await asyncio.sleep(sleep_for)
                backoff = min(backoff * 2, 60.0)


async def main():
    fetcher = KlinesFetcher()
    await fetcher.start()

if __name__ == "__main__":
    asyncio.run(main())
