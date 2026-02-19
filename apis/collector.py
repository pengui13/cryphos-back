import asyncio
import json
import time
from collections.abc import Iterable

import redis.asyncio as redis
import websockets

BINANCE_COMBINED = "wss://stream.binance.com:9443/stream?streams="

SYMBOLS = [
    "btcusdt",
    "usdcusdt",
    "ethusdt",
    "xrpusdt",
    "solusdt",
    "usd1usdt",
    "sentusdt",
    "bnbusdt",
    "dogeusdt",
    "adausdt",
    "paxgusdt",
    "zecusdt",
    "fdusdusdt",
    "suiusdt",
    "trxusdt",
    "linkusdt",
    "pepeusdt",
    "ltcusdt",
    "asterusdt",
    "avaxusdt",
    "wlfiusdt",
    "pumpusdt",
    "taousdt",
    "eurusdt",
    "hbarusdt",
    "bchusdt",
    "nearusdt",
    "enausdt",
    "aaveusdt",
    "usdeusdt",
    "uniusdt",
    "filusdt",
    "xlmusdt",
    "wldusdt",
    "trumpusdt",
    "wbtcusdt",
    "arbusdt",
    "zamausdt",
    "xplusdt",
    "wifusdt",
    "bfusdusdt",
    "dotusdt",
    "polusdt",
    "penguusdt",
    "bonkusdt",
    "virtualusdt",
    "shibusdt",
    "proveusdt",
    "icpusdt",
]

LAST_HASH = "prices:last"
TS_HASH = "prices:ts"
# TODO Rename it , because currently naming price:volume is a piece of shit

REDIS_URL = "redis://redis:6379/1"


def make_url(symbols: Iterable[str]) -> str:
    streams = "/".join(f"{s}@miniTicker" for s in symbols)
    return BINANCE_COMBINED + streams


def normalize_symbol(stream_name: str) -> str:
    return stream_name.split("@", 1)[0].upper()


async def collector():
    r = redis.from_url(REDIS_URL, decode_responses=True)

    url = make_url(SYMBOLS)
    backoff = 1

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                backoff = 1

                async for raw in ws:
                    msg = json.loads(raw)
                    stream = msg.get("stream", "")
                    data = msg.get("data", {})
                    symbol = normalize_symbol(stream)
                    price = data.get("c")
                    if price is None:
                        continue
                    ts = int(time.time() * 1000)
                    pipe = r.pipeline()
                    pipe.hset(LAST_HASH, symbol, price)
                    pipe.hset(TS_HASH, symbol, ts)
                    await pipe.execute()

        except Exception as e:
            print(e)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


async def main():
    await collector()


if __name__ == "__main__":
    asyncio.run(main())
