from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os

TOKEN = os.environ["TOKEN"]

TARGET_CHAT_IDS = [
    -5258812606,
    # 여기에 다른 단체방 ID 추가
]

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    for chat_id in TARGET_CHAT_IDS:
        await update.message.forward(chat_id=chat_id)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, forward_message))
    app.run_polling()

if __name__ == "__main__":
    main()
