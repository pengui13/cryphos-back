import asyncio
import json
import random
import websockets
import redis.asyncio as redis

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

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "1d"]

VOL_HASH = "prices:klines"
REDIS_URL = "redis://redis:6379/1"

WS_BASE = "wss://stream.binance.com:9443/stream?streams="


def build_url(symbols, interval: str) -> str:
    streams = [f"{s.lower()}@kline_{interval}" for s in symbols]
    return WS_BASE + "/".join(streams)


async def consume_interval(symbols, interval: str, r):
    url = build_url(symbols, interval)

    backoff = 1.0
    while True:
        try:
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_queue=10000,
            ) as ws:
                backoff = 1.0
                async for raw in ws:
                    msg = json.loads(raw)
                    data = msg.get("data", {})
                    k = data.get("k", {})
                    symbol = k.get("s")
                    k_interval = k.get("i")
                    if not symbol or not k_interval:
                        continue

                    base_vol = k.get("v")
                    quote_vol = k.get("q")
                    is_closed = bool(k.get("x"))
                    open_time = k.get("t")
                    close_time = k.get("T")

                    payload = {
                        "base_vol": base_vol,
                        "quote_vol": quote_vol,
                        "closed": is_closed,
                        "open_time": open_time,
                        "close_time": close_time,
                    }

                    field = f"{symbol}:{k_interval}"
                    await r.hset(VOL_HASH, field, json.dumps(payload))

        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as e:
            sleep_for = backoff + random.random() * 0.25
            print(f"[{interval}] WS error {type(e).__name__}: {e}. Reconnect in {sleep_for:.2f}s")
            await asyncio.sleep(sleep_for)
            backoff = min(backoff * 2, 60.0)


async def main():
    r = redis.from_url(REDIS_URL, decode_responses=True)

    tasks = []
    for interval in INTERVALS:
        tasks.append(asyncio.create_task(consume_interval(SYMBOLS, interval, r)))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
