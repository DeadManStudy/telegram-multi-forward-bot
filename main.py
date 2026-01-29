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

# ===============================
# 기본 설정
# ===============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://xxx.onrender.com
PORT = int(os.getenv("PORT", 10000))

GROUP_FILE = "groups.json"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# ===============================
# 그룹 저장 유틸
# ===============================

def load_groups():
    if not os.path.exists(GROUP_FILE):
        return []
    with open(GROUP_FILE, "r") as f:
        return json.load(f)

def save_groups(groups):
    with open(GROUP_FILE, "w") as f:
        json.dump(groups, f)

# ===============================
# 명령어 핸들러
# ===============================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    groups = load_groups()

    logger.info(f"[COMMAND] /add_group from chat_id={chat_id}")

    if chat_id in groups:
        await update.message.reply_text("이미 등록된 그룹입니다.")
        logger.info(f"[GROUP] already exists: {chat_id}")
        return

    groups.append(chat_id)
    save_groups(groups)

    await update.message.reply_text(f"그룹 등록 완료: {chat_id}")
    logger.info(f"[GROUP] added: {chat_id}")
    logger.info(f"[GROUP] current groups = {groups}")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    groups = load_groups()

    logger.info(f"[COMMAND] /remove_group from chat_id={chat_id}")

    if chat_id not in groups:
        await update.message.reply_text("등록되지 않은 그룹입니다.")
        logger.info(f"[GROUP] not found: {chat_id}")
        return

    groups.remove(chat_id)
    save_groups(groups)

    await update.message.reply_text(f"그룹 삭제 완료: {chat_id}")
    logger.info(f"[GROUP] removed: {chat_id}")
    logger.info(f"[GROUP] current groups = {groups}")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = load_groups()

    logger.info(f"[COMMAND] /list_groups")

    if not groups:
        await update.message.reply_text("등록된 그룹이 없습니다.")
        logger.info("[GROUP] list empty")
        return

    msg = "\n".join(str(g) for g in groups)
    await update.message.reply_text(f"등록된 그룹 목록:\n{msg}")
    logger.info(f"[GROUP] list = {groups}")

# ===============================
# 메시지 포워딩
# ===============================

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat.id
    text = msg.text

    logger.info(
        f"[UPDATE] MESSAGE chat_id={chat_id} "
        f"type={'COMMAND' if text and text.startswith('/') else 'TEXT'} "
        f"text={text}"
    )

    # 명령어는 포워딩 금지
    if text and text.startswith("/"):
        logger.info("[SKIP] command message → no forwarding")
        return

    groups = load_groups()
    logger.info(f"[FORWARD] target groups = {groups}")

    if not groups:
        logger.info("[SKIP] no groups registered")
        return

    for target_chat_id in groups:
        if target_chat_id == chat_id:
            logger.info(f"[SKIP] self chat_id={chat_id}")
            continue

        try:
            logger.info(
                f"[FORWARD] sending from {chat_id} → {target_chat_id}"
            )
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=text
            )
            logger.info(f"[FORWARD] success → {target_chat_id}")

        except Exception as e:
            logger.error(
                f"[ERROR] failed to send to {target_chat_id}: {e}"
            )

# ===============================
# Flask + Webhook
# ===============================

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message))

@app.route("/", methods=["GET"])
def index():
    return "Bot is running"

@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.json, application.bot)
    logger.info(
        f"[WEBHOOK] update received: keys={list(request.json.keys())}"
    )
    await application.process_update(update)
    return "OK"

# ===============================
# 부트스트랩
# ===============================

async def main():
    logger.info("[BOOT] 프로그램 시작")

    await application.initialize()
    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

    logger.info("[TG] Webhook 설정 완료")
    logger.info("[FLASK] 서버 시작")

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    app.run(host="0.0.0.0", port=PORT)
