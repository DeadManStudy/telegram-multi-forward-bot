import os
import json
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────
# 환경변수
# ─────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))
RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]

GROUPS_FILE = "groups.json"
ADMINS_FILE = "admins.json"

# ─────────────────────────
# JSON 유틸
# ─────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

groups = load_json(GROUPS_FILE, {})
admins = load_json(ADMINS_FILE, [])

# ─────────────────────────
# 슈퍼 관리자 등록
# ─────────────────────────
SUPER_ADMIN_ID = os.environ.get("SUPER_ADMIN_ID")

if SUPER_ADMIN_ID:
    sid = int(SUPER_ADMIN_ID)
    if sid not in admins:
        admins.append(sid)
        save_json(ADMINS_FILE, admins)
        print(f"✅ SUPER_ADMIN 등록됨: {sid}")

# ─────────────────────────
# 관리자 체크
# ─────────────────────────
def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in admins)

# ─────────────────────────
# Telegram Application
# ─────────────────────────
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ─────────────────────────
# 메시지 포워딩 (관리자만)
# ─────────────────────────
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    # 명령어는 포워딩 제외
    if update.message.text and update.message.text.startswith("/"):
        return

    if not is_admin(update):
        return

    for cid in groups:
        try:
            await update.message.forward(chat_id=int(cid))
        except Exception as e:
            print(f"❌ Forward error to {cid}: {e}")

# ─────────────────────────
# 명령어
# ─────────────────────────
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    chat = update.effective_chat
    groups[str(chat.id)] = {"title": chat.title}
    save_json(GROUPS_FILE, groups)

    await update.message.reply_text(
        f"✅ 그룹 등록됨\n\n{chat.title}\n{chat.id}"
    )

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = "👑 관리자 목록\n\n" + "\n".join(str(a) for a in admins)
    await update.message.reply_text(text)

# ─────────────────────────
# 핸들러 등록
# ─────────────────────────
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("list_admins", list_admins))
telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))

# ─────────────────────────
# Flask (Webhook 수신용)
# ─────────────────────────
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

# ─────────────────────────
# 메인 실행부
# ─────────────────────────
async def main():
    await telegram_app.initialize()
    await telegram_app.start()

    await telegram_app.bot.set_webhook(
        url=f"{RENDER_EXTERNAL_URL}/webhook"
    )

    print("🤖 Telegram webhook registered")

if __name__ == "__main__":
    asyncio.run(main())
    app.run(host="0.0.0.0", port=PORT)
