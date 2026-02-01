"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- 봇 개인 채팅에서만 메시지 포워딩
- SUPER ADMIN 기반 제어
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
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
SUPER_ADMIN_IDS = {
    int(x) for x in os.getenv("SUPER_ADMIN_IDS", "").split(",") if x.strip()
}

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 누락")

log("ENV", f"SUPER_ADMIN_IDS={SUPER_ADMIN_IDS}")

# ======================
# 6. 그룹 로딩 (환경변수)
# ======================
def load_group_env(name):
    return {
        int(x) for x in os.getenv(name, "").split(",") if x.strip()
    }

GROUPS = {
    "GROUP1": load_group_env("GROUP1_IDS"),
    "GROUP2": load_group_env("GROUP2_IDS"),
    "GROUP3": load_group_env("GROUP3_IDS"),
}

TEMP_GROUPS: set[int] = set()

# ======================
# 7. 상태 변수
# ======================
CURRENT_TARGET: str | None = None

# ======================
# 8. Flask
# ======================
app = Flask(__name__)

# ======================
# 9. Telegram Application
# ======================
application = Application.builder().token(BOT_TOKEN).build()

# ======================
# 10. 유틸
# ======================
def is_super_admin(uid: int) -> bool:
    return uid in SUPER_ADMIN_IDS

def is_private(update: Update) -> bool:
    return update.effective_chat.type == "private"

def is_group(update: Update) -> bool:
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 11. 명령어
# ======================
async def send_group(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    global CURRENT_TARGET

    if not is_private(update):
        return
    if not is_super_admin(update.effective_user.id):
        return

    CURRENT_TARGET = name
    await update.message.reply_text(f"✅ [{name}]으로 메시지를 전송합니다")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_TARGET

    if not is_private(update):
        return
    if not is_super_admin(update.effective_user.id):
        return

    CURRENT_TARGET = None
    await update.message.reply_text("⛔ 메시지 전송을 중지했습니다")

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return

    cid = update.effective_chat.id
    TEMP_GROUPS.add(cid)
    await update.message.reply_text("✅ TEMP_GROUP에 추가됨")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return

    cid = update.effective_chat.id
    TEMP_GROUPS.discard(cid)
    await update.message.reply_text("🗑️ TEMP_GROUP에서 제거됨")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        return

    text = "📤 포워딩 그룹 목록\n\n"

    for name, ids in GROUPS.items():
        text += f"[ {name} ]\n"
        if not ids:
            text += "- (등록된 그룹 없음)\n\n"
            continue

        for gid in ids:
            try:
                chat = await context.bot.get_chat(gid)
                text += f"- {chat.title}\n"
            except Exception:
                text += f"- (접근 불가)\n"
        text += "\n"

    text += "[ TEMP_GROUP ]\n"
    if not TEMP_GROUPS:
        text += "- (등록된 그룹 없음)\n"
    else:
        for gid in TEMP_GROUPS:
            text += f"- {gid}\n"

    await update.message.reply_text(text)

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        return

    text = "🛡️ SUPER ADMIN 목록\n\n"
    for uid in SUPER_ADMIN_IDS:
        text += f"- {uid}\n"

    await update.message.reply_text(text)

# ======================
# 12. 메시지 포워딩
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not is_private(update):
        return
    if not is_super_admin(update.effective_user.id):
        return
    if not CURRENT_TARGET:
        return

    targets = GROUPS.get(CURRENT_TARGET, set())
    for gid in targets:
        await context.bot.forward_message(
            chat_id=gid,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )

# ======================
# 13. 핸들러
# ======================
application.add_handler(CommandHandler("send_group1", lambda u, c: send_group(u, c, "GROUP1")))
application.add_handler(CommandHandler("send_group2", lambda u, c: send_group(u, c, "GROUP2")))
application.add_handler(CommandHandler("send_group3", lambda u, c: send_group(u, c, "GROUP3")))
application.add_handler(CommandHandler("stop", stop))
application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(CommandHandler("list_admins", list_admins))

application.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_message)
)

# ======================
# 14. Webhook
# ======================
telegram_loop = asyncio.new_event_loop()

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
    except Exception:
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
# 15. MAIN
# ======================
async def run_telegram():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    log("TG", "Webhook 설정 완료")

def start_telegram():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(run_telegram())
    telegram_loop.run_forever()

if __name__ == "__main__":
    Thread(target=start_telegram, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
