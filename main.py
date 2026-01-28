import os
import json
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))

GROUPS_FILE = "groups.json"
ADMINS_FILE = "admins.json"

# ─────────────────────────────────────
# 📦 파일 유틸
# ─────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ JSON load failed ({path}): {e}")
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

groups = load_json(GROUPS_FILE, {})
admins = load_json(ADMINS_FILE, [])

# ⚠️ 최초 1회용: 환경변수로 슈퍼관리자 지정 가능
SUPER_ADMIN_ID = os.environ.get("SUPER_ADMIN_ID")
if SUPER_ADMIN_ID:
    sid = int(SUPER_ADMIN_ID)
    if sid not in admins:
        admins.append(sid)
        save_json(ADMINS_FILE, admins)

# ─────────────────────────────────────
# 🔐 관리자 체크
# ─────────────────────────────────────
def is_admin(update: Update) -> bool:
    user = update.effective_user
    return user and user.id in admins

# ─────────────────────────────────────
# 🤖 Telegram App
# ─────────────────────────────────────
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ─────────────────────────────────────
# 🔁 관리자 메시지만 포워딩
# ─────────────────────────────────────
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    # 명령어는 포워딩 제외
    if update.message.text and update.message.text.startswith("/"):
        return

    # 관리자만 포워딩 가능
    if not is_admin(update):
        return

    for chat_id in groups.keys():
        try:
            await update.message.forward(chat_id=int(chat_id))
        except Exception as e:
            print(f"Forward error to {chat_id}: {e}")

# ─────────────────────────────────────
# 📦 그룹 관리
# ─────────────────────────────────────
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    chat = update.effective_chat
    cid = str(chat.id)

    if cid in groups:
        await update.message.reply_text("⚠️ 이미 등록된 단체방입니다.")
        return

    groups[cid] = {
        "title": chat.title,
        "type": chat.type,
    }
    save_json(GROUPS_FILE, groups)

    await update.message.reply_text(
        f"✅ 단체방 추가 완료\n\n{chat.title}\n{chat.id}"
    )

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    chat = update.effective_chat
    cid = str(chat.id)

    if cid not in groups:
        await update.message.reply_text("⚠️ 등록되지 않은 단체방입니다.")
        return

    del groups[cid]
    save_json(GROUPS_FILE, groups)

    await update.message.reply_text(
        f"🗑️ 단체방 제거 완료\n\n{chat.title}\n{chat.id}"
    )

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    if not groups:
        await update.message.reply_text("📭 등록된 단체방이 없습니다.")
        return

    text = "📋 포워딩 대상 단체방\n\n"
    for cid, info in groups.items():
        text += f"• {info['title']} ({cid})\n"

    await update.message.reply_text(text)

# ─────────────────────────────────────
# 👑 관리자 관리
# ─────────────────────────────────────
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    if not context.args:
        await update.message.reply_text("사용법: /add_admin <user_id>")
        return

    uid = int(context.args[0])
    if uid in admins:
        await update.message.reply_text("⚠️ 이미 관리자입니다.")
        return

    admins.append(uid)
    save_json(ADMINS_FILE, admins)

    await update.message.reply_text(f"✅ 관리자 추가 완료\nID: {uid}")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    if not context.args:
        await update.message.reply_text("사용법: /remove_admin <user_id>")
        return

    uid = int(context.args[0])
    if uid not in admins:
        await update.message.reply_text("⚠️ 관리자가 아닙니다.")
        return

    admins.remove(uid)
    save_json(ADMINS_FILE, admins)

    await update.message.reply_text(f"🗑️ 관리자 제거 완료\nID: {uid}")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    text = "👑 관리자 목록\n\n"
    for uid in admins:
        text += f"• {uid}\n"

    await update.message.reply_text(text)

# ─────────────────────────────────────
# 핸들러 등록
# ─────────────────────────────────────
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))

telegram_app.add_handler(CommandHandler("add_admin", add_admin))
telegram_app.add_handler(CommandHandler("remove_admin", remove_admin))
telegram_app.add_handler(CommandHandler("list_admins", list_admins))

telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))

# ─────────────────────────────────────
# 🌐 Flask Webhook
# ─────────────────────────────────────
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

if __name__ == "__main__":
    telegram_app.initialize()
    telegram_app.start()
    app.run(host="0.0.0.0", port=PORT)

