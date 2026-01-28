import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
)

# =========================
# 환경 변수
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")

# =========================
# Flask 앱
# =========================
app = Flask(__name__)

# =========================
# Telegram Application
# =========================
telegram_app = Application.builder().token(BOT_TOKEN).build()


# =========================
# 메시지 처리 로직
# =========================
async def forward_all(update: Update, context):
    """
    모든 메시지를 수신했음을 로그로만 확인
    (포워딩 대상은 필요 시 여기에 추가)
    """
    if update.message:
        print(
            f"📩 message received | "
            f"chat_id={update.message.chat_id} | "
            f"type={update.message.chat.type}"
        )

        # 👉 예시: 특정 chat_id로 포워딩하고 싶다면 아래 주석 해제
        # TARGET_CHAT_ID = 123456789
        # await update.message.forward(chat_id=TARGET_CHAT_ID)


# 모든 메시지 타입 처리
telegram_app.add_handler(
    MessageHandler(filters.ALL, forward_all)
)


# =========================
# Flask Routes
# =========================
@app.route("/", methods=["GET"])
def index():
    # Render 헬스체크용
    return "Bot is running"


@app.route("/webhook", methods=["POST"])
async def webhook():
    """
    Telegram → Webhook → Flask → Application.update_queue
    """
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return "ok"


# =========================
# Application 초기화 & Webhook 설정
# =========================
async def setup_telegram():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    print("✅ Webhook set")


# =========================
# Entry Point
# =========================
if __name__ == "__main__":
    # Telegram Application 초기화
    asyncio.run(setup_telegram())

    # Render는 PORT=10000 사용
    app.run(host="0.0.0.0", port=10000)
