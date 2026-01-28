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

# =====================
# 기본 설정
# =====================
BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUPS_FILE = "groups.json"

# 🔐 관리자 Telegram user_id
ADMIN_USER_IDS = [
    123456789,  # ← 본인 ID로 교체
]

# =====================
# 그룹 데이터 관리
# =====================
def load_groups():
    if not os.path.exists(GROUPS_FILE):
        return {}
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_groups(groups):
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

groups = load_groups()  
# 구조:
# {
#   "-1001234567890": {
#       "title": "공지방",
#       "type": "supergroup"
#   }
# }

# =====================
# Flask + Telegram App
# =====================
app = Flask(__name__)
telegram_app = Application.builder().token(BOT_TOKEN).build()

# =====================
# 공통: 관리자 체크
# =====================
def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id in ADMIN_USER_IDS

# =====================
# 🔁 모든 메시지 자동 포워딩
# =====================
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    # 명령어 메시지는 포워딩 제외
    if update.message.text and update.message.text.startswith("/"):
        return

    for chat_id in groups.keys():
        try:
            if int(chat_id) != update.effective_chat.id:
                await update.message.forward(chat_id=int(chat_id))
        except Exception as e:
            print(f"Forward error to {chat_id}: {e}")

# =====================
# ➕ /add_group
# =====================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    chat = update.effective_chat
    chat_id = str(chat.id)

    if chat_id in groups:
        await update.message.reply_text("⚠️ 이미 포워딩 대상입니다.")
        return

    groups[chat_id] = {
        "title": chat.title,
        "type": chat.type,
    }
    save_groups(groups)

    await update.message.reply_text(
        f"✅ 포워딩 대상에 추가되었습니다.\n\n"
        f"이름: {chat.title}\n"
        f"ID: {chat.id}"
    )

# =====================
# ➖ /remove_group
# =====================
async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    chat_id = str(update.effective_chat.id)

    if chat_id not in groups:
        await update.message.reply_text("⚠️ 이 방은 포워딩 대상이 아닙니다.")
        return

    removed = groups.pop(chat_id)
    save_groups(groups)

    await update.message.reply_text(
        f"🗑️ 포워딩 대상에서 제거되었습니다.\n\n"
        f"이름: {removed.get('title')}\n"
        f"ID: {chat_id}"
    )

# =====================
# 📋 /list_groups
# =====================
async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ 관리자만 사용할 수 있습니다.")
        return

    if not groups:
        await update.message.reply_text("📭 등록된 단체방이 없습니다.")
        return

    lines = ["📋 포워딩 대상 단체방 목록:\n"]
    for cid, info in groups.items():
        lines.append(
            f"- {info.get('title')} ({info.get('type')})\n  ID: {cid}"
        )

    await update.message.reply_text("\n".join(lines))

# =====================
# 핸들러 등록
# =====================
telegram_app.add_handler(MessageHandler(filters.ALL, forward_all))
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))

# =====================
# Flask Routes
# =====================
@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

# =====================
# Run
# =====================
if __name__ == "__main__":
    telegram_app.initialize()
    telegram_app.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
