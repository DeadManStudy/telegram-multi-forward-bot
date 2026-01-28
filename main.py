import os
import json
import asyncio
import threading
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
SUPER_ADMIN_ID = os.environ.get("SUPER_ADMIN_ID")

GROUPS_FILE = "groups.json"
ADMINS_FILE = "admins.json"

# ─────────────────────────
# JSON 유틸 (없으면 자동 생성)
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
# 슈퍼 관리자 자동 등록
# ─────────────────────────
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
# 메시지 포워딩 (관리자만 가능)
# ─────────────────────────
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    # 명령어는 포워딩 안 함
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
# 그룹 / 관리자 명령
# ─────────────────────────
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    chat = update.effective_chat
    groups[str(chat.id)] = {"title": chat.title}
    save_json(GROUPS_FILE, groups)

    await update.message.reply_text(
        f"✅ 그룹 등록됨\n\n{chat.title}\nID: {chat.id}"
    )

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    chat_id = str(update.effective_chat.id)
    if chat_id in groups:
        title = groups[chat_id].get("title")
        del groups[chat_id]
        save_json(GROUPS_FILE, groups)
        await update.message.reply_text(f"❌ 그룹 제거됨\n{title}")
    else:
        await update.message.reply_text("⚠️ 등록되지 않은 그룹입니다.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if not groups:
        await update.message.reply_text("📭 등록된 그룹이 없습니다.")
        return

    text = "📋 등록된 그룹 목록\n\n"
    for gid, info in groups.items():
        text += f"{info.get('title')} ({gid})\n"

    await update.message.reply_text(text)

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = "👑 관리자 목록\n\n" + "\n".join(str(a) for a in admins)
    await update.message.reply_text(text)

# ─────────────────────────
# 핸들러 등록
# ─────────────────────────
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))
telegram_app.add_handler(CommandHandler("list_admins", list_admins))
telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))

# ─────────────────────────
# Flask (Render 메인 서버)
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
# Telegram 백그라운드 실행
# ─────────────────────────
def run_telegram():
    async def runner():
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(
            url=f"{RENDER_EXTERNAL_URL}/webhook"
        )
        await telegram_app.start()
        print("🤖 Telegram bot started with webhook")

    asyncio.run(runner())

# ─────────────────────────
# Entry point
# ─────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_telegram, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
