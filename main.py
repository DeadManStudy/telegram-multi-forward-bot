import os
import json
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =====================
# 환경변수
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN or not RENDER_EXTERNAL_URL:
    raise RuntimeError("BOT_TOKEN 또는 RENDER_EXTERNAL_URL 환경변수가 없습니다.")

# =====================
# 파일 경로
# =====================
ADMINS_FILE = "admins.json"

# =====================
# 파일 유틸
# =====================
def load_admins():
    if not os.path.exists(ADMINS_FILE):
        return []
    with open(ADMINS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_admins(admins):
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)

# =====================
# Telegram 핸들러
# =====================
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != SUPER_ADMIN_ID:
        await update.message.reply_text("❌ 권한이 없습니다.")
        return

    admins = load_admins()
    if not admins:
        await update.message.reply_text("📭 등록된 관리자가 없습니다.")
        return

    text = "📋 관리자 목록:\n" + "\n".join(str(a) for a in admins)
    await update.message.reply_text(text)

# =====================
# Telegram Application
# =====================
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("list_admins", list_admins))

# =====================
# Flask App
# =====================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
async def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "OK", 200

# =====================
# 웹훅 설정
# =====================
@app.before_first_request
def setup_webhook():
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    application.bot.set_webhook(webhook_url)
    print(f"Webhook set to: {webhook_url}")

# =====================
# Run
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
