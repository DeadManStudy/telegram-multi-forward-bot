import os
import threading
import asyncio
from datetime import datetime

from flask import Flask, request, abort
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# 공통 로그 함수
# =========================
def log(tag, msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{tag}] {msg}", flush=True)


# =========================
# BOOT
# =========================
log("BOOT", "프로그램 시작")

# =========================
# ENV
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://xxx.onrender.com
PORT = int(os.environ.get("PORT", 10000))

TARGET_CHAT_IDS = [
    int(cid.strip())
    for cid in os.environ.get("TARGET_CHAT_IDS", "").split(",")
    if cid.strip()
]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN 환경 변수가 없습니다")

log("ENV", "환경 변수 로딩 완료")
log("ENV", f"포워딩 대상 채팅 수: {len(TARGET_CHAT_IDS)}")

# =========================
# Flask
# =========================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성 완료")

# =========================
# Telegram Handler
# =========================
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        log("MSG", "메시지 아님 (무시)")
        return

    msg = update.message
    src_chat = msg.chat

    log(
        "MSG",
        f"수신 | from={src_chat.id} | type={src_chat.type}"
    )

    if not TARGET_CHAT_IDS:
        log("FWD", "❌ 포워딩 대상 없음")
        return

    for target_chat_id in TARGET_CHAT_IDS:
        try:
            if msg.text:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=msg.text
                )
            else:
                await msg.forward(chat_id=target_chat_id)

            log("FWD", f"✅ {target_chat_id} 전달 성공")

        except Exception as e:
            log("FWD", f"❌ {target_chat_id} 전달 실패: {e}")

# =========================
# Telegram Application
# =========================
telegram_app = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 생성 완료")

telegram_app.add_handler(
    MessageHandler(filters.ALL, forward_all)
)
log("TG", "MessageHandler 등록 완료")


# =========================
# Webhook Endpoint
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)

    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_loop
    )

    return "ok", 200


@app.route("/", methods=["GET", "HEAD"])
def index():
    log("HTTP", "GET / 요청 수신")
    return "ok", 200


# =========================
# Telegram Thread
# =========================
def run_telegram():
    global telegram_loop

    telegram_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(telegram_loop)

    log("TG", "initialize 시작")
    telegram_loop.run_until_complete(telegram_app.initialize())
    log("TG", "initialize 완료")

    log("TG", "start 시작")
    telegram_loop.run_until_complete(telegram_app.start())
    log("TG", "start 완료")

    webhook_full_url = f"{WEBHOOK_URL}/webhook"
    log("TG", f"webhook 설정 시도: {webhook_full_url}")

    telegram_loop.run_until_complete(
        telegram_app.bot.set_webhook(webhook_full_url)
    )

    log("TG", "✅ Webhook 설정 완료")

    telegram_loop.run_forever()


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    log("MAIN", "메인 엔트리 진입")

    tg_thread = threading.Thread(target=run_telegram, daemon=True)
    tg_thread.start()
    log("TG", "Telegram 백그라운드 스레드 시작")

    log("FLASK", f"Flask 서버 실행 (0.0.0.0:{PORT})")
    app.run(host="0.0.0.0", port=PORT)
