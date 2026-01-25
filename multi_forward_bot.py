import os
from telegram.ext import Updater, MessageHandler, Filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")

TARGET_CHATS = [
    -5258812606,
]

def forward_all(update, context):
    if update.effective_chat.type != "private":
        return

    for chat_id in TARGET_CHATS:
        context.bot.copy_message(
            chat_id=chat_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(MessageHandler(Filters.all, forward_all))

updater.start_polling()
updater.idle()
