import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

TARGET_CHATS = [
    -5258812606,
]

async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    for chat_id in TARGET_CHATS:
        await context.bot.copy_message(
            chat_id=chat_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, forward_all))
app.run_polling()
