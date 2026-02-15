import json
import asyncio
import redis.asyncio as redis
from channels.generic.websocket import AsyncWebsocketConsumer

REDIS_URL = "redis://redis:6379/1"


class LiquidationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()

        self.redis = await redis.from_url(REDIS_URL)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe("liquidations")

        self.listener_task = asyncio.create_task(self._listen_redis())

    async def disconnect(self, close_code):
        if hasattr(self, "listener_task"):
            self.listener_task.cancel()

        if hasattr(self, "pubsub"):
            await self.pubsub.unsubscribe("liquidations")
            await self.pubsub.close()

        if hasattr(self, "redis"):
            await self.redis.close()

    async def _listen_redis(self):
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    await self.send(text_data=message["data"].decode())
        except asyncio.CancelledError:
            pass

    async def receive(self, text_data):

        pass
