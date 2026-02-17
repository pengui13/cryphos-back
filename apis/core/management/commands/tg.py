import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

User = get_user_model()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the Telegram bot and approve users when they send /start"

    def handle(self, *args, **options):

        @sync_to_async
        def get_user_by_tg(username):
            try:
                return User.objects.filter(tg_nickname=username).first()
            except Exception:
                return None

        @sync_to_async
        def save_user(user):
            user.save()

        async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            tg_user = update.effective_user
            chat_id = update.effective_chat.id
            username = tg_user.username
            first_name = tg_user.first_name or ""
            last_name = tg_user.last_name or ""
            full_name = f"{first_name} {last_name}".strip()

            if not username:
                msg = """
⚠️ <b>Username Required</b>

Please set a Telegram username in your settings to continue.

<i>Settings → Edit Profile → Username</i>
""".strip()
                await update.message.reply_text(msg, parse_mode="HTML")
                logger.warning(
                    f"User {tg_user.id} ({full_name}) tried to start bot without username"
                )
                return

            try:
                user = await get_user_by_tg(username)

                if user is None:
                    msg = f"""
⚠️ <b>Account Not Found</b>

No account linked to <code>@{username}</code>

<b>To connect:</b>
1. Visit <b>cryphos.io/settings</b>
2. Enter username: <code>{username}</code>
3. Save and return here
4. Send /start

<i>Need help? Contact @cryphos_support</i>
""".strip()
                    await update.message.reply_text(msg, parse_mode="HTML")
                    logger.warning(f"No user found for @{username} (chat_id: {chat_id})")
                    return

                user.tg_approved = True
                user.chat_id = chat_id
                await save_user(user)

                logger.info(f"Approved user {user.username} (@{username}) with chat_id {chat_id}")

                msg = f"""
✅ <b>Connected Successfully</b>

Welcome, @{username}

Your account is now active and ready to receive trading signals.

<b>What's next:</b>
- Create a bot at <b>cryphos.io/lab</b>
- Configure your indicators
- Receive signals here 24/7

<code>────────────────────</code>
/help · /status
""".strip()
                await update.message.reply_text(msg, parse_mode="HTML")

            except Exception as e:
                logger.error(f"Error in /start: {e}", exc_info=True)
                msg = """
❌ <b>Connection Failed</b>

Something went wrong. Please try again.

<i>If the issue persists, contact @cryphos_support</i>
""".strip()
                await update.message.reply_text(msg, parse_mode="HTML")

        async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            msg = """
<b>Cryphos Bot</b>

<b>Commands:</b>
/start · Connect your account
/status · Check connection status
/help · Show this message

<b>Links:</b>
- Dashboard: cryphos.io
- Create bot: cryphos.io/lab
- Settings: cryphos.io/settings

<code>────────────────────</code>
<i>Support: @cryphos_support</i>
""".strip()
            await update.message.reply_text(msg, parse_mode="HTML")

        async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            tg_user = update.effective_user
            username = tg_user.username
            chat_id = update.effective_chat.id

            if not username:
                msg = """
⚠️ <b>Username Required</b>

Set a username in Telegram settings first.
""".strip()
                await update.message.reply_text(msg, parse_mode="HTML")
                return

            try:
                user = await get_user_by_tg(username)

                if user is None:
                    msg = """
⚠️ <b>Not Connected</b>

No account found. Visit <b>cryphos.io/settings</b> to link your Telegram.
""".strip()
                    await update.message.reply_text(msg, parse_mode="HTML")
                    return

                if user.tg_approved and user.chat_id:
                    msg = f"""
<b>Status: </b>🟢 Active

<b>Account:</b> @{username}
<b>Signals:</b> Enabled
<b>Chat ID:</b> <code>{chat_id}</code>

<code>────────────────────</code>
<i>Signals will be delivered to this chat</i>
""".strip()
                else:
                    msg = """
<b>Status: </b>🔴 Inactive

Send /start to activate your account.
""".strip()

                await update.message.reply_text(msg, parse_mode="HTML")

            except Exception as e:
                logger.error(f"Error in /status: {e}", exc_info=True)
                msg = """
❌ <b>Error</b>

Could not check status. Please try again.
""".strip()
                await update.message.reply_text(msg, parse_mode="HTML")

        async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            msg = """
Unknown command. Send /help for available commands.
""".strip()
            await update.message.reply_text(msg, parse_mode="HTML")

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Update {update} caused error {context.error}", exc_info=True)
            if update and isinstance(update, Update) and update.effective_message:
                msg = """
❌ <b>Error</b>

Something went wrong. Please try again later.
""".strip()
                await update.effective_message.reply_text(msg, parse_mode="HTML")

        # Build app
        app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(MessageHandler(filters.Regex("^start$"), start_command))
        app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

        app.add_error_handler(error_handler)

        self.stdout.write(self.style.SUCCESS("🤖 Starting Cryphos Telegram bot..."))

        try:
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to start bot: {str(e)}"))
            logger.error(f"Bot startup failed: {e}", exc_info=True)
