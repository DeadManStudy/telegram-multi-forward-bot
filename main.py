"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇 (Render Web Service)
- 관리자/슈퍼어드민만 메시지 포워딩 가능
- 그룹을 동적으로 등록하여 다중 포워딩
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
# 2. Flask (Webhook)
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
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log(tag, msg):
    logging.info(f"[{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경 변수
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

SUPER_ADMIN_IDS = set(
    int(x) for x in os.environ.get("SUPER_ADMIN_IDS", "").split(",") if x
)

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 없음")

log("ENV", f"SUPER_ADMIN_IDS={SUPER_ADMIN_IDS}")

# ======================
# 6. 전역 상태
# ======================
TARGET_GROUPS: set[int] = set()
ADMIN_IDS: set[int] = set()

log("STATE", f"등록된 그룹 수={len(TARGET_GROUPS)}")
log("STATE", f"관리자 수={len(ADMIN_IDS)}")

# ======================
# 7. Flask
# ======================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성")

# ======================
# 8. Telegram Application
# ======================
telegram_app = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 생성")

# ======================
# 9. 권한 유틸
# ======================
def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMIN_IDS

def is_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMIN_IDS or user_id in ADMIN_IDS

def is_group(update: Update) -> bool:
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 10. 그룹 관리 명령어
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능")
        return

    TARGET_GROUPS.add(update.effective_chat.id)
    log("GROUP", f"추가됨 {update.effective_chat.id}")
    await update.message.reply_text("✅ 이 그룹이 포워딩 대상에 추가됨")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id

    if cid not in TARGET_GROUPS:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹")
        return

    TARGET_GROUPS.remove(cid)
    log("GROUP", f"제거됨 {cid}")
    await update.message.reply_text("🗑️ 포워딩 대상에서 제거됨")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TARGET_GROUPS:
        await update.message.reply_text("📭 등록된 그룹 없음")
        log("GROUP", "목록 요청: 비어 있음")
        return

    text = "📤 포워딩 중인 그룹:\n\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"

    log("GROUP", f"목록 출력: {len(TARGET_GROUPS)}개")
    await update.message.reply_text(text)

# ======================
# 11. 관리자 관리 명령어
# ======================
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_super_admin(user_id):
        await update.message.reply_text("⛔ 슈퍼어드민만 가능")
        return

    if not context.args:
        await update.message.reply_text("사용법: /add_admin <user_id>")
        return

    admin_id = int(context.args[0])
    ADMIN_IDS.add(admin_id)
    log("ADMIN", f"관리자 추가 {admin_id}")
    await update.message.reply_text(f"✅ 관리자 추가됨: {admin_id}")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_super_admin(user_id):
        await update.message.reply_text("⛔ 슈퍼어드민만 가능")
        return

    if not context.args:
        await update.message.reply_text("사용법: /remove_admin <user_id>")
        return

    admin_id = int(context.args[0])
    ADMIN_IDS.discard(admin_id)
    log("ADMIN", f"관리자 제거 {admin_id}")
    await update.message.reply_text(f"🗑️ 관리자 제거됨: {admin_id}")

# ======================
# ⭐ 12. 관리자 목록 조회 (/list_admins)
# ======================
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ 관리자만 확인 가능")
        log("ADMIN", f"관리자 목록 조회 차단 user_id={user_id}")
        return

    text = "👮 관리자 목록\n\n"

    text += "⭐ 슈퍼어드민\n"
    for uid in SUPER_ADMIN_IDS:
        text += f"- {uid}\n"

    text += "\n🛡 일반 관리자\n"
    if ADMIN_IDS:
        for uid in ADMIN_IDS:
            text += f"- {uid}\n"
    else:
        text += "(없음)\n"

    log("ADMIN", "관리자 목록 출력")
    await update.message.reply_text(text)

# ======================
# 13. 메시지 포워딩 (관리자만)
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(user_id):
        log("BLOCK", f"포워딩 차단 user_id={user_id} chat_id={chat_id}")
        await update.message.reply_text("⛔ 관리자만 메시지를 전달할 수 있습니다.")
        return

    if not TARGET_GROUPS:
        log("MSG", "포워딩 대상 없음 → 무시")
        return

    log("AUTH", f"관리자 메시지 수신 user_id={user_id}")

    for gid in TARGET_GROUPS:
        if gid == chat_id:
            continue
        try:
            await update.message.copy(chat_id=gid)
            log("FORWARD", f"전달 성공 → {gid}")
        except Exception as e:
            log("FORWARD", f"전달 실패 → {gid} ({e})")

# ======================
# 14. 핸들러 등록
# ======================
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))

telegram_app.add_handler(CommandHandler("add_admin", add_admin))
telegram_app.add_handler(CommandHandler("remove_admin", remove_admin))
telegram_app.add_handler(CommandHandler("list_admins", list_admins))

telegram_app.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_message)
)

log("TG", "핸들러 등록 완료")

# ======================
# 15. Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    except Exception as e:
        log("HTTP", f"Update 변환 실패 {e}")
        abort(400)

    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        telegram_loop
    )

    return "OK", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# 16. Telegram 루프
# ======================
telegram_loop = asyncio.new_event_loop()

async def run_telegram():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    log("TG", "Webhook 설정 완료")

def start_telegram():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(run_telegram())
    telegram_loop.run_forever()

# ======================
# 17. 메인
# ======================
if __name__ == "__main__":
    Thread(target=start_telegram, daemon=True).start()
    log("MAIN", "Telegram 백그라운드 스레드 시작")

    port = int(os.environ.get("PORT", 10000))
    log("FLASK", f"Flask 실행 port={port}")
    app.run(host="0.0.0.0", port=port)
