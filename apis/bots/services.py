from .models import Bot
from accounts.models import User

class BotService:

    @staticmethod
    def create_with_indicators(user: User, validated_data: dict):
        assets = validated_data.pop("bot_assets", [])
        bot = Bot.objects.create(owner=user, **validated_data)
        bot.assets.set(assets)
        IndicatorService.create_for_bot(bot, raw_data)
        bot.activate()
        return bot
    
class IndicatorService:
    
    @staticmethod
    def create_for_bot(bot, raw_data):
        raw_data['bot'] = bot