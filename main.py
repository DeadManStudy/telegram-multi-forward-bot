"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- 슈퍼 어드민 전용 다중 그룹 포워딩
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
    format="%(asctime)s | %(levelname)s | %(message)s",
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
# 6. 그룹 환경변수
# ======================
def load_group_env(name):
    return set(
        int(x) for x in os.getenv(name, "").split(",") if x.strip()
    )

GROUPS = {
    "GROUP1": load_group_env("GROUP1_IDS"),
    "GROUP2": load_group_env("GROUP2_IDS"),
    "GROUP3": load_group_env("GROUP3_IDS"),
}

TEMP_GROUPS: set[int] = set()
ACTIVE_SEND_GROUP: str | None = None

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

# ======================
# 10. 명령어
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능")
        return

    cid = update.effective_chat.id
    TEMP_GROUPS.add(cid)
    log("GROUP", f"TEMP_GROUP 추가 {cid}")
    await update.message.reply_text("✅ TEMP_GROUP에 추가됨")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid in TEMP_GROUPS:
        TEMP_GROUPS.remove(cid)
        await update.message.reply_text("🗑️ TEMP_GROUP에서 제거됨")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        return

    text = "📤 포워딩 그룹 목록\n\n"

    for name, ids in GROUPS.items():
        if not ids:
            continue
        text += f"[ {name} ]\n"
        for gid in ids:
            try:
                chat = await context.bot.get_chat(gid)
                text += f"- {chat.title}\n"
            except Exception:
                text += f"- (접근 불가: {gid})\n"
        text += "\n"

    if TEMP_GROUPS:
        text += "[ TEMP_GROUP ]\n"
        for gid in TEMP_GROUPS:
            text += f"- {gid}\n"

    await update.message.reply_text(text)

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        return

    text = "🛡️ 슈퍼 어드민 목록\n\n"
    for uid in SUPER_ADMIN_IDS:
        text += f"- {uid}\n"
    await update.message.reply_text(text)

async def send_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE_SEND_GROUP

    uid = update.effective_user.id
    if not is_super_admin(uid):
        return

    cmd = update.message.text.replace("/", "").upper()
    if cmd not in GROUPS:
        return

    ACTIVE_SEND_GROUP = cmd

    names = []
    for gid in GROUPS[cmd]:
        try:
            chat = await context.bot.get_chat(gid)
            names.append(chat.title)
        except Exception:
            pass

    title_text = ", ".join(names) if names else cmd
    await update.message.reply_text(
        f"📨 [{title_text}] 으로 메시지를 전송합니다"
    )

# ======================
# 11. 메시지 포워딩
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE_SEND_GROUP

    if not update.message:
        return

    if update.effective_chat.type != "private":
        return

    uid = update.effective_user.id
    if not is_super_admin(uid):
        return

    target_groups = set(TEMP_GROUPS)
    if ACTIVE_SEND_GROUP:
        target_groups |= GROUPS.get(ACTIVE_SEND_GROUP, set())

    for gid in target_groups:
        try:
            await context.bot.forward_message(
                chat_id=gid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
            log("FORWARD", f"→ {gid}")
        except Exception as e:
            log("FORWARD", f"실패 {gid}: {e}")

# ======================
# 12. 핸들러 등록
# ======================
application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(CommandHandler("list_admins", list_admins))

application.add_handler(CommandHandler("send_group1", send_group))
application.add_handler(CommandHandler("send_group2", send_group))
application.add_handler(CommandHandler("send_group3", send_group))

application.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_message)
)

log("TG", "핸들러 등록 완료")

# ======================
# 13. Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
    except Exception as e:
        log("HTTP", f"Update 파싱 실패 {e}")
        abort(400)

    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        telegram_loop,
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
