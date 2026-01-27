import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 🔥 포워딩할 단체방 ID들
TARGET_CHAT_IDS = [
    -5258812606,
]

app = Flask(__name__)

telegram_app = Application.builder().token(BOT_TOKEN).build()

# 🔁 모든 메시지 자동 포워딩
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    for chat_id in TARGET_CHAT_IDS:
        try:
            await update.message.forward(chat_id=chat_id)
        except Exception as e:
            print(f"Forward error: {e}")

telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))

@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

if __name__ == "__main__":
    telegram_app.initialize()
    telegram_app.start()

    # Render에서 제공하는 PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
