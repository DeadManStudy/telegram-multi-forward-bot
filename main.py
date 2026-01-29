"""
telegram-multi-forward-bot
- Flask Webhook 기반
- Render Web Service 대응
- 그룹을 동적으로 등록하여 메시지 다중 포워딩
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
import asyncio
import logging
from datetime import datetime
from threading import Thread

# ======================
# 2. Flask
# ======================
from flask import Flask, request, abort

# ======================
# 3. Telegram
# ======================
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ======================
# 4. 로깅
# ======================
logging.basicConfig(level=logging.INFO)

def log(tag, msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경 변수
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://xxxx.onrender.com

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 누락")

log("ENV", "환경 변수 로딩 완료")

# ======================
# 6. Flask 앱
# ======================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성")

# ======================
# 7. Telegram Application
# ======================
telegram_app = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 생성")

# ======================
# 8. 이벤트 루프 (중요)
# ======================
telegram_loop = asyncio.new_event_loop()

# ======================
# 9. 포워딩 대상 그룹
# ======================
TARGET_GROUPS: set[int] = set()

# ======================
# 10. 유틸
# ======================
def is_group(update: Update) -> bool:
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 11. 명령어 핸들러
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log("CMD", "/add_group 수신")

    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능합니다.")
        return

    gid = update.effective_chat.id
    TARGET_GROUPS.add(gid)

    log("GROUP", f"추가됨: {gid}")
    await update.message.reply_text("✅ 이 그룹이 전달 대상에 추가되었습니다.")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log("CMD", "/remove_group 수신")

    gid = update.effective_chat.id
    if gid not in TARGET_GROUPS:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹입니다.")
        return

    TARGET_GROUPS.remove(gid)
    log("GROUP", f"제거됨: {gid}")
    await update.message.reply_text("🗑️ 전달 대상에서 제거되었습니다.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log("CMD", "/list_groups 수신")

    if not TARGET_GROUPS:
        await update.message.reply_text("📭 등록된 그룹이 없습니다.")
        return

    text = "📤 메시지 전달 중인 그룹:\n\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"

    await update.message.reply_text(text)

# ======================
# 12. 메시지 포워딩
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    src = update.effective_chat.id
    log("FORWARD", f"메시지 수신: from {src}")

    if not TARGET_GROUPS:
        log("FORWARD", "전달 대상 없음")
        return

    for gid in TARGET_GROUPS:
        if gid == src:
            continue  # 자기 자신에게 재포워딩 방지

        try:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=src,
                message_id=update.message.message_id,
            )
            log("FORWARD", f"{src} → {gid} 전달 성공")
        except Exception as e:
            log("FORWARD", f"❌ {gid} 실패: {e}")

# ======================
# 13. 핸들러 등록
# ======================
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)
)

log("TG", "핸들러 등록 완료")

# ======================
# 14. Webhook 엔드포인트
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        log("HTTP", "Update 객체 생성 완료")
    except Exception as e:
        log("HTTP", f"❌ Update 파싱 실패: {e}")
        abort(400)

    # 🔥 핵심: Dispatcher에 직접 전달
    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_loop,
    )

    return "OK", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# 15. Telegram 백그라운드 실행
# ======================
async def run_telegram():
    log("TG", "initialize 시작")
    await telegram_app.initialize()

    log("TG", "start 시작")
    await telegram_app.start()

    webhook_url = f"{WEBHOOK_URL}/webhook"
    await telegram_app.bot.set_webhook(webhook_url)
    log("TG", f"Webhook 설정 완료: {webhook_url}")

def start_telegram():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(run_telegram())
    telegram_loop.run_forever()

# ======================
# 16. 메인
# ======================
if __name__ == "__main__":
    Thread(target=start_telegram, daemon=True).start()
    log("TG", "Telegram 백그라운드 루프 실행")

    port = int(os.environ.get("PORT", 10000))
    log("FLASK", f"Flask 서버 실행: {port}")
    app.run(host="0.0.0.0", port=port)
