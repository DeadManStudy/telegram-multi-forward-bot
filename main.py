"""
telegram-multi-forward-bot FINAL
- Super Admin only
- Fixed groups (env) + temp_group (runtime)
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

SUPER_ADMIN_IDS = {
    int(x) for x in os.getenv("SUPER_ADMIN_IDS", "").split(",") if x.strip()
}

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("환경변수 누락")

# ======================
# 6. 그룹 로딩
# ======================
GROUP_FILE = "groups.json"

def load_groups():
    groups = {}

    # 🔹 환경변수 그룹
    for k, v in os.environ.items():
        if k.startswith("GROUP_") and k.endswith("_IDS"):
            name = k.replace("GROUP_", "").replace("_IDS", "").lower()
            groups[name] = {int(x) for x in v.split(",") if x.strip()}

    # 🔹 temp_group은 항상 존재
    groups.setdefault("temp_group", set())

    # 🔹 런타임 저장 그룹
    if os.path.exists(GROUP_FILE):
        with open(GROUP_FILE) as f:
            saved = json.load(f)
        groups["temp_group"].update(saved.get("temp_group", []))

    return groups

def save_groups():
    with open(GROUP_FILE, "w") as f:
        json.dump(
            {"temp_group": list(GROUP_SETS["temp_group"])},
            f
        )

GROUP_SETS = load_groups()
log("STATE", f"GROUP_SETS={GROUP_SETS}")

ACTIVE_GROUP = {}  # uid -> group_name

# ======================
# 7. Flask
# ======================
app = Flask(__name__)

# ======================
# 8. Telegram App
# ======================
application = Application.builder().token(BOT_TOKEN).build()

# ======================
# 9. 권한
# ======================
def is_super_admin(uid: int) -> bool:
    return uid in SUPER_ADMIN_IDS

# ======================
# 10. 그룹 관리
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat = update.effective_chat

    if not is_super_admin(uid):
        return

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ 단체방에서만 사용 가능")
        return

    GROUP_SETS["temp_group"].add(chat.id)
    save_groups()

    await update.message.reply_text("✅ temp_group에 등록됨")
    log("GROUP", f"{chat.id} → temp_group")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        return

    text = "📦 그룹 목록:\n\n"
    for name, ids in GROUP_SETS.items():
        text += f"🔹 {name}\n"
        for gid in ids:
            try:
                chat = await context.bot.get_chat(gid)
                title = chat.title or gid
            except Exception:
                title = gid
            text += f"  - {title}\n"
        text += "\n"

    await update.message.reply_text(text)

# ======================
# 11. send_group
# ======================
def make_send_handler(group_name: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_super_admin(uid):
            return

        if group_name not in GROUP_SETS:
            await update.message.reply_text("❌ 존재하지 않는 그룹")
            return

        ACTIVE_GROUP[uid] = group_name

        titles = []
        for gid in GROUP_SETS[group_name]:
            try:
                chat = await context.bot.get_chat(gid)
                titles.append(chat.title or gid)
            except Exception:
                titles.append(str(gid))

        msg = f"📤 다음 단체방으로 전송됩니다:\n\n"
        for t in titles:
            msg += f"- {t}\n"

        await update.message.reply_text(msg)
        log("MODE", f"{uid} → {group_name}")

    return handler

# ======================
# 12. 중단
# ======================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ACTIVE_GROUP.pop(update.effective_user.id, None)
    await update.message.reply_text("⏹️ 전송 중단")

# ======================
# 13. 포워딩
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if update.effective_chat.type != "private":
        return

    uid = update.effective_user.id
    if not is_super_admin(uid):
        await update.message.reply_text("❌ 관리자만 포워딩 가능")
        return

    group = ACTIVE_GROUP.get(uid)
    if not group:
        return

    for gid in GROUP_SETS[group]:
        await context.bot.forward_message(
            chat_id=gid,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

# ======================
# 14. 핸들러
# ======================
application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(CommandHandler("stop", stop))

for name in GROUP_SETS:
    application.add_handler(
        CommandHandler(f"send_{name}", make_send_handler(name))
    )

application.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_message)
)

# ======================
# 15. Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        telegram_loop
    )
    return "OK", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# 16. Run
# ======================
telegram_loop = asyncio.new_event_loop()

async def run_tg():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

def start_tg():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(run_tg())
    telegram_loop.run_forever()

if __name__ == "__main__":
    Thread(target=start_tg, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
