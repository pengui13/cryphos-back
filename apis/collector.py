import asyncio
import json
import time
from loguru import logger
import redis.asyncio as redis
import websockets
from django.conf import settings


class LastPriceFetcher:

    def __init__(self):
        self.redis = None

    def _normalize_symbol(self, stream_name: str) -> str:
        return stream_name.split("@", 1)[0].upper()

    async def _handle_message(self, raw: str):
        msg = json.loads(raw)
        stream = msg.get("stream", "")
        data = msg.get("data", {})
        symbol = self._normalize_symbol(stream)
        price = data.get("c")
        if price is None:
            return

        ts = int(time.time() * 1000)
        pipe = self.redis.pipeline()
        pipe.hset(settings.LAST_HASH, symbol, price)
        pipe.hset(settings.TS_HASH, symbol, ts)
        await pipe.execute()

    async def start(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await self._collect()

    def _build_url(self) -> str:
        streams = "/".join(f"{s}@miniTicker" for s in settings.SYMBOLS)
        return settings.WS_BASE + streams

    async def _collect(self):
        url = self._build_url()
        backoff = 1
        while True:
            try:
                async with websockets.connect(url, ping_interval=20,
                                              ping_timeout=20) as ws:

                    async for raw in ws:
                        await self._handle_message(raw)

            except Exception as e:
                logger.error(e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)


async def main():
    fetcher = LastPriceFetcher()
    await fetcher.start()


if __name__ == "__main__":
    asyncio.run(main())
