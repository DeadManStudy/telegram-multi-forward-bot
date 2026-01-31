"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- 개인 채팅 메시지 관리자가 포워딩
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

log("ENV", f"SUPER_ADMIN_IDS={SUPER_ADMIN_IDS}")

# ======================
# 6. 데이터 파일
# ======================
GROUP_FILE = "groups.json"
ADMIN_FILE = "admins.json"

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

TARGET_GROUPS = set(load_json(GROUP_FILE, []))
ADMINS = set(load_json(ADMIN_FILE, []))

log("STATE", f"등록된 그룹 수={len(TARGET_GROUPS)}")
log("STATE", f"관리자 수={len(ADMINS)}")

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
def is_group(update: Update):
    return update.effective_chat.type in ("group", "supergroup")

def is_super_admin(uid: int):
    return uid in SUPER_ADMIN_IDS

def is_admin(uid: int):
    return uid in ADMINS or is_super_admin(uid)

# ======================
# 10. 명령어
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능")
        return

    TARGET_GROUPS.add(cid)
    save_json(GROUP_FILE, list(TARGET_GROUPS))
    log("GROUP", f"추가됨 {cid}")
    await update.message.reply_text("✅ 포워딩 그룹으로 등록됨")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in TARGET_GROUPS:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹")
        return

    TARGET_GROUPS.remove(cid)
    save_json(GROUP_FILE, list(TARGET_GROUPS))
    log("GROUP", f"제거됨 {cid}")
    await update.message.reply_text("🗑️ 포워딩 그룹에서 제거됨")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TARGET_GROUPS:
        await update.message.reply_text("📭 등록된 그룹 없음")
        return

    text = "📤 포워딩 그룹 목록:\n\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"
    await update.message.reply_text(text)

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_super_admin(uid):
        return

    if not context.args:
        return

    new_admin = int(context.args[0])
    ADMINS.add(new_admin)
    save_json(ADMIN_FILE, list(ADMINS))
    log("ADMIN", f"관리자 추가 {new_admin}")
    await update.message.reply_text("✅ 관리자 추가됨")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🛡️ 관리자 목록:\n\n"
    for uid in ADMINS.union(SUPER_ADMIN_IDS):
        text += f"- {uid}\n"
    await update.message.reply_text(text)

# ======================
# 11. 포워딩 (개인 채팅 + 관리자만)
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    uid = update.effective_user.id
    cid = update.effective_chat.id

    # 🔹 개인 채팅에서만 포워딩
    if update.effective_chat.type != "private":
        return

    # 🔹 관리자 체크
    if not is_admin(uid):
        log("MSG", f"관리자 아님 → 차단 (uid={uid})")
        await update.message.reply_text("❌ 포워딩 차단됨")
        return

    for gid in TARGET_GROUPS:
        try:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=cid,
                message_id=update.message.message_id,
            )
            log("FORWARD", f"{cid} → {gid} 전달 성공")
        except Exception as e:
            log("FORWARD", f"{cid} → {gid} 전달 실패: {e}")

# ======================
# 12. 핸들러 등록
# ======================
application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(CommandHandler("add_admin", add_admin))
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
