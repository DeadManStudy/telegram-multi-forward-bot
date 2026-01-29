import os
import asyncio
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from datetime import datetime


# =========================
# 공통 로그 함수
# =========================
def log(step, message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{step}] {message}", flush=True)


# =========================
# 환경 변수
# =========================
log("BOOT", "프로그램 시작")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not BOT_TOKEN:
    log("ENV", "❌ BOT_TOKEN 없음")
    raise RuntimeError("BOT_TOKEN missing")

if not WEBHOOK_URL:
    log("ENV", "❌ WEBHOOK_URL 없음")
    raise RuntimeError("WEBHOOK_URL missing")

log("ENV", "환경 변수 로딩 완료")


# =========================
# Flask 앱
# =========================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성 완료")


# =========================
# Telegram Application
# =========================
telegram_app = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 생성 완료")


# =========================
# 메시지 핸들러
# =========================
async def forward_all(update: Update, context):
    if not update.message:
        log("MSG", "메시지 아님 (무시)")
        return

    msg = update.message
    chat = msg.chat

    log(
        "MSG",
        f"수신 | chat_id={chat.id} | "
        f"type={chat.type} | "
        f"text={'있음' if msg.text else '없음'} | "
        f"media={'있음' if msg.photo or msg.video or msg.document else '없음'}"
    )


telegram_app.add_handler(
    MessageHandler(filters.ALL, forward_all)
)
log("TG", "MessageHandler 등록 완료")


# =========================
# Flask routes
# =========================
@app.route("/", methods=["GET"])
def index():
    log("HTTP", "GET / 요청 수신")
    return "Bot is running"


@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    data = request.get_json(force=True)
    if not data:
        log("HTTP", "❌ webhook payload 비어있음")
        return "no data", 400

    try:
        update = Update.de_json(data, telegram_app.bot)
        log("HTTP", "Update 객체 변환 성공")
    except Exception as e:
        log("HTTP", f"❌ Update 변환 실패: {e}")
        return "bad update", 400

    try:
        asyncio.run_coroutine_threadsafe(
            telegram_app.update_queue.put(update),
            telegram_app.loop
        )
        log("HTTP", "Update queue 전달 완료")
    except Exception as e:
        log("HTTP", f"❌ Queue 전달 실패: {e}")

    return "ok"


# =========================
# Telegram 초기화
# =========================
async def setup_telegram():
    log("TG", "initialize 시작")
    await telegram_app.initialize()
    log("TG", "initialize 완료")

    log("TG", "start 시작")
    await telegram_app.start()
    log("TG", "start 완료")

    log("TG", f"webhook 설정 시도: {WEBHOOK_URL}")
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    log("TG", "✅ Webhook 설정 완료")


def start_telegram():
    log("TG", "Telegram 백그라운드 스레드 시작")
    asyncio.run(setup_telegram())


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    log("MAIN", "메인 엔트리 진입")

    threading.Thread(
        target=start_telegram,
        daemon=True
    ).start()

    log("FLASK", "Flask 서버 실행 (0.0.0.0:10000)")
    app.run(host="0.0.0.0", port=10000)
