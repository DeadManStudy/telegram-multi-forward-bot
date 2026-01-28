import os
import asyncio
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    ContextTypes,
)

# =====================
# 환경변수
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not BOT_TOKEN or not RENDER_EXTERNAL_URL:
    raise RuntimeError("BOT_TOKEN or RENDER_EXTERNAL_URL is missing")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

# =====================
# Flask
# =====================
app = Flask(__name__)

# =====================
# Telegram Application
# =====================
application = Application.builder().token(BOT_TOKEN).build()

# =====================
# 핸들러 (예시)
# =====================
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(update.message.text)

application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, echo)
)

# =====================
# Webhook 엔드포인트
# =====================
@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
        return "OK"
    except Exception as e:
        print("Webhook error:", e)
        abort(500)

# =====================
# 헬스체크
# =====================
@app.route("/", methods=["GET"])
def health():
    return "Bot is running"

# =====================
# Render 시작 시 Webhook 등록
# =====================
async def setup_webhook():
    await application.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
    )
    print("Webhook set to:", WEBHOOK_URL)

if __name__ == "__main__":
    asyncio.run(setup_webhook())

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
