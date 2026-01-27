import os
import asyncio
import threading
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

    print("📩 message received:", update.message.text)

    for chat_id in TARGET_CHAT_IDS:
        try:
            await context.bot.forward_message(
                chat_id=chat_id,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
            )
        except Exception as e:
            print("Forward error:", e)


telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))


@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)

    # 🔥 핵심: 백그라운드 루프에 task 등록
    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_loop,
    )

    return "ok", 200


def start_telegram_loop():
    global telegram_loop
    telegram_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(telegram_loop)

    telegram_loop.run_until_complete(telegram_app.initialize())
    telegram_loop.run_forever()


if __name__ == "__main__":
    # 🔥 Telegram 전용 이벤트 루프를 별도 스레드에서 실행
    threading.Thread(
        target=start_telegram_loop,
        daemon=True,
    ).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
