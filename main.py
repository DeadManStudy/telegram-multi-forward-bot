import os
import asyncio
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

# =========================
# 환경 변수
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 환경 변수가 없습니다.")

# =========================
# Flask 앱
# =========================
app = Flask(__name__)

# =========================
# Telegram Application
# =========================
telegram_app = Application.builder().token(BOT_TOKEN).build()


# =========================
# 메시지 핸들러
# =========================
async def forward_all(update: Update, context):
    if update.message:
        print(
            f"📩 received | "
            f"chat_id={update.message.chat_id} | "
            f"type={update.message.chat.type}"
        )


telegram_app.add_handler(
    MessageHandler(filters.ALL, forward_all)
)


# =========================
# Flask routes
# =========================
@app.route("/", methods=["GET"])
def index():
    return "Bot is running"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)

    # asyncio queue에 안전하게 전달
    asyncio.run_coroutine_threadsafe(
        telegram_app.update_queue.put(update),
        telegram_app.loop
    )
    return "ok"


# =========================
# Telegram 초기화 (백그라운드)
# =========================
async def setup_telegram():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    print("✅ Webhook set")


def start_telegram():
    asyncio.run(setup_telegram())


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    # 🔥 Telegram은 백그라운드에서
    threading.Thread(target=start_telegram, daemon=True).start()

    # 🔥 Flask는 즉시 포트 오픈 (Render 생존 포인트)
    app.run(host="0.0.0.0", port=10000)
