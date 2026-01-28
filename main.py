import os
import json
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
)

# ======================
# 환경 변수
# ======================
BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPER_ADMIN_ID = int(os.environ["SUPER_ADMIN_ID"])

# ======================
# 데이터 파일
# ======================
GROUPS_FILE = "groups.json"

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

groups = load_json(GROUPS_FILE, {})

# ======================
# Flask
# ======================
app = Flask(__name__)

telegram_app = Application.builder().token(BOT_TOKEN).build()

# ======================
# 관리자 체크 (슈퍼 어드민 고정)
# ======================
def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == SUPER_ADMIN_ID)

# ======================
# 포워딩 로직
# ======================
async def forward_all(update: Update, context):
    if not update.message:
        return

    print("📩 message from:", update.effective_user.id)

    if not is_admin(update):
        print("⛔ not admin")
        return

    if not groups:
        print("⚠️ groups.json 비어있음")
        return

    for cid in groups:
        try:
            await update.message.forward(chat_id=int(cid))
            print(f"✅ forwarded to {cid}")
        except Exception as e:
            print(f"❌ forward error to {cid}:", e)

# ======================
# 핸들러
# ======================
telegram_app.add_handler(
    MessageHandler(filters.ALL, forward_all)
)

# ======================
# Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/")
def index():
    return "OK", 200

# ======================
# 실행
# ======================
if __name__ == "__main__":
    async def run():
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(
            url="https://telegram-multi-forward-bot.onrender.com/webhook"
        )
        print("✅ Webhook set")

    asyncio.run(run())
    app.run(host="0.0.0.0", port=10000)
