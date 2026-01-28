import os
import json
import asyncio
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
# 파일
# =====================
ADMINS_FILE = "admins.json"

def load_admins():
    if not os.path.exists(ADMINS_FILE):
        return []
    with open(ADMINS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# =====================
# Telegram 핸들러
# =====================
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN_ID:
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
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("list_admins", list_admins))

# =====================
# Flask App
# =====================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "OK", 200

# =====================
# 메인 엔트리
# =====================
async def setup():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{RENDER_EXTERNAL_URL}/webhook")
    print("✅ Webhook set")

if __name__ == "__main__":
    asyncio.run(setup())
    app.run(host="0.0.0.0", port=PORT)
