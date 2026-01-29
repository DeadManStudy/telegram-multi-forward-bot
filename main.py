"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service 대응
- 그룹 동적 등록 + 다중 포워딩
- 디버그 로그 강화 최종본
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
import logging
import asyncio
import threading
from datetime import datetime

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
# 4. 로깅 설정
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

def log(tag: str, msg: str):
    logger.info(f"[{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경 변수
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://xxxx.onrender.com

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN 없음")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL 없음")

log("ENV", "BOT_TOKEN 확인됨")
log("ENV", f"WEBHOOK_URL = {WEBHOOK_URL}")

# ======================
# 6. Flask 앱
# ======================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성 완료")

# ======================
# 7. Telegram Application
# ======================
application = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 객체 생성")

# ======================
# 8. 전역 상태
# ======================
TARGET_GROUPS: set[int] = set()

# ======================
# 9. 유틸
# ======================
def is_group(update: Update) -> bool:
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 10. 명령어 핸들러
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log("CMD", f"/add_group from chat_id={update.effective_chat.id}")

    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능")
        log("CMD", "실패: 그룹 아님")
        return

    TARGET_GROUPS.add(update.effective_chat.id)
    log("GROUP", f"추가됨: {update.effective_chat.id}")
    await update.message.reply_text("✅ 이 그룹이 전달 대상에 추가됨")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    log("CMD", f"/remove_group from chat_id={cid}")

    if cid not in TARGET_GROUPS:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹")
        log("GROUP", "제거 실패: 등록 안 됨")
        return

    TARGET_GROUPS.remove(cid)
    log("GROUP", f"제거됨: {cid}")
    await update.message.reply_text("🗑️ 전달 대상에서 제거됨")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log("CMD", f"/list_groups from chat_id={update.effective_chat.id}")

    if not TARGET_GROUPS:
        await update.message.reply_text("📭 등록된 그룹 없음")
        log("GROUP", "목록 요청: 비어 있음")
        return

    text = "📤 전달 중인 그룹:\n\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"

    await update.message.reply_text(text)
    log("GROUP", f"목록 출력: {len(TARGET_GROUPS)}개")

# ======================
# 11. 메시지 포워딩
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        log("MSG", "메시지 없음 → 무시")
        return

    if not TARGET_GROUPS:
        log("MSG", "포워딩 대상 없음 → 무시")
        return

    src = update.effective_chat.id
    mid = update.message.message_id

    log("MSG", f"수신 메시지 chat_id={src}, message_id={mid}")

    for gid in TARGET_GROUPS:
        try:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=src,
                message_id=mid,
            )
            log("FORWARD", f"{src} → {gid} 성공")
        except Exception as e:
            log("FORWARD", f"{src} → {gid} 실패: {e}")

# ======================
# 12. 핸들러 등록
# ======================
application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)
)

log("TG", "모든 핸들러 등록 완료")

# ======================
# 13. Telegram 이벤트 루프
# ======================
telegram_loop = asyncio.new_event_loop()

async def init_telegram():
    log("TG", "initialize 시작")
    await application.initialize()

    log("TG", "start 시작")
    await application.start()

    webhook_url = f"{WEBHOOK_URL}/webhook"
    await application.bot.set_webhook(webhook_url)
    log("TG", f"Webhook 설정 완료: {webhook_url}")

def start_telegram():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(init_telegram())
    log("TG", "이벤트 루프 진입")
    telegram_loop.run_forever()

# ======================
# 14. Flask Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        log(
            "UPDATE",
            f"type={update.effective_chat.type}, chat_id={update.effective_chat.id}",
        )
    except Exception as e:
        log("HTTP", f"❌ Update 파싱 실패: {e}")
        abort(400)

    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        telegram_loop,
    )

    log("HTTP", "Update Telegram 루프로 전달 완료")
    return "OK", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# 15. 메인
# ======================
if __name__ == "__main__":
    threading.Thread(target=start_telegram, daemon=True).start()
    log("MAIN", "Telegram 백그라운드 스레드 시작")

    port = int(os.environ.get("PORT", 10000))
    log("FLASK", f"Flask 실행 포트={port}")
    app.run(host="0.0.0.0", port=port)
