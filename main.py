"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- Super Admin만 포워딩 가능
- 프리미엄 이모지 보존 (forward_message)
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
import json
import logging
import asyncio
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log(tag, msg):
    logging.info(f"[{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경변수
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SUPER_ADMIN_IDS = set(
    int(x) for x in os.getenv("SUPER_ADMIN_IDS", "").split(",") if x.strip()
)

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 누락")

if not SUPER_ADMIN_IDS:
    raise RuntimeError("SUPER_ADMIN_IDS 비어있음")

log("ENV", f"SUPER_ADMIN_IDS={SUPER_ADMIN_IDS}")

# ======================
# 6. 데이터 파일 (temp_group)
# ======================
TEMP_GROUP_FILE = "temp_groups.json"

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
        return default
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

TEMP_GROUPS = set(load_json(TEMP_GROUP_FILE, []))

log("STATE", f"temp_group 수={len(TEMP_GROUPS)}")

# ======================
# 7. Flask
# ======================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성")

# ======================
# 8. Telegram Application
# ======================
application = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 생성")

# ======================
# 9. 유틸
# ======================
def is_super_admin(uid: int):
    return uid in SUPER_ADMIN_IDS

def is_group(update: Update):
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 10. 명령어
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능합니다.")
        return

    cid = update.effective_chat.id
    TEMP_GROUPS.add(cid)
    save_json(TEMP_GROUP_FILE, list(TEMP_GROUPS))
    log("GROUP", f"temp_group 추가됨 {cid}")

    await update.message.reply_text("✅ temp_group에 등록되었습니다.")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in TEMP_GROUPS:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹입니다.")
        return

    TEMP_GROUPS.remove(cid)
    save_json(TEMP_GROUP_FILE, list(TEMP_GROUPS))
    log("GROUP", f"temp_group 제거됨 {cid}")

    await update.message.reply_text("🗑️ temp_group에서 제거되었습니다.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TEMP_GROUPS:
        await update.message.reply_text("📭 등록된 그룹이 없습니다.")
        return

    text = "📤 등록된 포워딩 그룹 목록\n\n"
    text += "[ TEMP GROUP ]\n"
    for gid in TEMP_GROUPS:
        text += f"- {gid}\n"

    await update.message.reply_text(text)

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in SUPER_ADMIN_IDS:
        return

    text = "🛡️ Super Admin 목록\n\n"
    for aid in SUPER_ADMIN_IDS:
        text += f"- {aid}\n"

    await update.message.reply_text(text)

# ======================
# 11. 포워딩 (개인 채팅 + Super Admin)
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    uid = update.effective_user.id

    # 개인 채팅에서만 처리
    if update.effective_chat.type != "private":
        return

    if not is_super_admin(uid):
        log("MSG", f"포워딩 차단됨 (관리자 아님 uid={uid})")
        await update.message.reply_text("❌ 관리자만 포워딩 가능합니다.")
        return

    for gid in TEMP_GROUPS:
        try:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
            log("FORWARD", f"{uid} → {gid} 전달 성공")
        except Exception as e:
            log("FORWARD", f"{uid} → {gid} 전달 실패: {e}")

# ======================
# 12. 핸들러 등록
# ======================
application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(CommandHandler("list_admins", list_admins))

application.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_message)
)

log("TG", "핸들러 등록 완료")

# ======================
# 13. Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
    except Exception as e:
        log("HTTP", f"Update 파싱 실패: {e}")
        abort(400)

    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        telegram_loop
    )
    return "OK", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# 14. Telegram 루프
# ======================
telegram_loop = asyncio.new_event_loop()

async def run_telegram():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    log("TG", "Webhook 설정 완료")

def start_telegram():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(run_telegram())
    telegram_loop.run_forever()

# ======================
# 15. MAIN
# ======================
if __name__ == "__main__":
    Thread(target=start_telegram, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    log("FLASK", f"Flask 실행 port={port}")
    app.run(host="0.0.0.0", port=port)
