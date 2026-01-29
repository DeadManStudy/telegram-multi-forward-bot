import os
import json
import logging
from datetime import datetime

from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ========================
# 기본 설정
# ========================
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # https://xxx.onrender.com/webhook
PORT = int(os.environ.get("PORT", 10000))

DATA_FILE = "groups.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log(tag, msg):
    logger.info(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{tag}] {msg}")

# ========================
# 데이터 관리
# ========================
def load_groups():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_groups(groups):
    with open(DATA_FILE, "w") as f:
        json.dump(groups, f)

# ========================
# 명령어 핸들러
# ========================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    groups = load_groups()

    if chat_id not in groups:
        groups.append(chat_id)
        save_groups(groups)
        log("GROUP", f"추가됨: {chat_id}")

    await update.message.reply_text(f"✅ 그룹 등록 완료\nID: {chat_id}")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = load_groups()
    text = "\n".join(map(str, groups)) if groups else "등록된 그룹 없음"
    await update.message.reply_text(text)

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    groups = load_groups()

    if chat_id in groups:
        groups.remove(chat_id)
        save_groups(groups)
        log("GROUP", f"삭제됨: {chat_id}")

    await update.message.reply_text("❌ 그룹 제거 완료")

# ========================
# 🔥 포워딩 핸들러 (핵심)
# ========================
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    src_chat = update.effective_chat.id
    msg_id = update.message.message_id

    groups = load_groups()

    log("FORWARD", f"메시지 감지 from {src_chat}, 대상 {groups}")

    for target in groups:
        # 자기 자신에게 다시 보내는 건 스킵
        if target == src_chat:
            continue

        try:
            await context.bot.copy_message(
                chat_id=target,
                from_chat_id=src_chat,
                message_id=msg_id,
            )
            log("FORWARD", f"→ 전달 성공: {target}")
        except Exception as e:
            log("ERROR", f"전달 실패 ({target}): {e}")

# ========================
# 앱 초기화
# ========================
log("BOOT", "프로그램 시작")

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(CommandHandler("remove_group", remove_group))

# ⭐ 이 줄이 없으면 포워딩은 절대 안 됨
application.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, forward_all)
)

@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "OK"

@app.route("/")
def health():
    return "OK"

async def startup():
    log("TG", "initialize 시작")
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    await application.start()
    log("TG", "Webhook 등록 완료")

import asyncio
asyncio.get_event_loop().run_until_complete(startup())

log("FLASK", f"서버 실행: {PORT}")
app.run(host="0.0.0.0", port=PORT)
