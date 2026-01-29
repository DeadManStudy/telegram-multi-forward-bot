"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- 그룹을 동적으로 등록하여 모든 메시지를 다중 포워딩
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
import logging
import asyncio
from datetime import datetime
from threading import Thread

# ======================
# 2. Flask (Webhook 수신)
# ======================
from flask import Flask, request, abort

# ======================
# 3. Telegram 라이브러리
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

def log(tag, msg):
    logging.info(f"[{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경 변수
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://xxxx.onrender.com

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN 이 설정되지 않음")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL 이 설정되지 않음")

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
telegram_app = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 객체 생성")

# ======================
# 8. 포워딩 대상 그룹 (메모리)
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
    cid = update.effective_chat.id
    log("CMD", f"/add_group from chat_id={cid}")

    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능")
        return

    TARGET_GROUPS.add(cid)
    log("GROUP", f"추가됨: {cid}")
    await update.message.reply_text("✅ 이 그룹이 전달 대상에 추가됨")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    log("CMD", f"/remove_group from chat_id={cid}")

    if cid not in TARGET_GROUPS:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹")
        return

    TARGET_GROUPS.remove(cid)
    log("GROUP", f"제거됨: {cid}")
    await update.message.reply_text("🗑️ 전달 대상에서 제거됨")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    log("CMD", f"/list_groups from chat_id={cid}")

    if not TARGET_GROUPS:
        log("GROUP", "목록 요청: 비어 있음")
        await update.message.reply_text("📭 등록된 그룹 없음")
        return

    text = "📤 전달 중인 그룹:\n\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"

    log("GROUP", f"목록 출력: {len(TARGET_GROUPS)}개")
    await update.message.reply_text(text)

# ======================
# 11. 메시지 포워딩 (모든 메시지)
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        log("MSG", "update.message 없음 → 무시")
        return

    if not TARGET_GROUPS:
        log("MSG", "포워딩 대상 없음 → 무시")
        return

    src = update.effective_chat.id
    mid = update.message.message_id
    msg_type = update.message.__class__.__name__

    log(
        "MSG",
        f"수신 메시지 type={msg_type}, chat_id={src}, message_id={mid}"
    )

    for gid in TARGET_GROUPS:
        # 자기 자신에게는 포워딩하지 않음
        if gid == src:
            log("FORWARD", f"자기 자신({gid}) → 스킵")
            continue

        try:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=src,
                message_id=mid,
            )
            log("FORWARD", f"{src} → {gid} 전달 성공")
        except Exception as e:
            log("FORWARD", f"❌ {gid} 전달 실패: {e}")

# ======================
# 12. 핸들러 등록
# ======================
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))

# 🔥 핵심 수정: 모든 메시지 수신
telegram_app.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_message)
)

log("TG", "모든 핸들러 등록 완료")

# ======================
# 13. Flask Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    try:
        update = Update.de_json(
            request.get_json(force=True),
            telegram_app.bot,
        )
    except Exception as e:
        log("HTTP", f"❌ Update 변환 실패: {e}")
        abort(400)

    chat = update.effective_chat
    if chat:
        log("UPDATE", f"type={chat.type}, chat_id={chat.id}")

    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_loop,
    )

    log("HTTP", "Update Telegram 루프로 전달 완료")
    return "OK", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# 14. Telegram 이벤트 루프
# ======================
telegram_loop = asyncio.new_event_loop()

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
    log("TG", "이벤트 루프 진입")
    telegram_loop.run_forever()

# ======================
# 15. 메인
# ======================
if __name__ == "__main__":
    Thread(target=start_telegram, daemon=True).start()
    log("MAIN", "Telegram 백그라운드 스레드 시작")

    port = int(os.environ.get("PORT", 10000))
    log("FLASK", f"Flask 실행 포트={port}")
    app.run(host="0.0.0.0", port=port)
