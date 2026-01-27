import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]

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

    # 🔥 핵심: update_queue ❌ → process_update ✅
    asyncio.run(telegram_app.process_update(update))

    return "ok", 200


if __name__ == "__main__":
    async def main():
        await telegram_app.initialize()
        await telegram_app.start()

    asyncio.run(main())

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
