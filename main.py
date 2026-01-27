from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.environ["TOKEN"]

TARGET_CHAT_IDS = [
    -5258812606,
]

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("보낼 메시지를 입력하세요.")
        return

    text = " ".join(context.args)

    for chat_id in TARGET_CHAT_IDS:
        await context.bot.send_message(chat_id=chat_id, text=text)

    await update.message.reply_text("✅ 전송 완료")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("send", send_all))
    app.run_polling()

if __name__ == "__main__":
    main()
