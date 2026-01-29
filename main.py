import os
import json
import logging
import asyncio
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

# =========================================================
# 로깅 설정
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

logger.info("[BOOT] 프로그램 시작")

# =========================================================
# 환경 변수 로딩
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN:
    logger.error("[ENV] BOT_TOKEN 없음 → 즉시 종료")
    raise RuntimeError("BOT_TOKEN missing")

if not WEBHOOK_URL:
    logger.error("[ENV] WEBHOOK_URL 없음 → 즉시 종료")
    raise RuntimeError("WEBHOOK_URL missing")

logger.info("[ENV] BOT_TOKEN 로딩 완료")
logger.info(f"[ENV] WEBHOOK_URL = {WEBHOOK_URL}")

# =========================================================
# 데이터 저장 (단체방 목록)
# =========================================================
DATA_FILE = "groups.json"

def load_groups():
    if not os.path.exists(DATA_FILE):
        logger.info("[DATA] groups.json 없음 → 새로 생성")
        return set()
    with open(DATA_FILE, "r") as f:
        data = set(json.load(f))
        logger.info(f"[DATA] 그룹 로딩 완료: {data}")
        return data

def save_groups(groups):
    with open(DATA_FILE, "w") as f:
        json.dump(list(groups), f)
    logger.info(f"[DATA] 그룹 저장 완료: {groups}")

target_groups = load_groups()
logger.info(f"[STATE] 현재 등록된 그룹 수: {len(target_groups)}")

# =========================================================
# Telegram 핸들러
# =========================================================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"[COMMAND] /add_group from chat_id={chat_id}")

    if chat_id in target_groups:
        await update.message.reply_text("이미 등록된 그룹입니다.")
        logger.info("[ADD_GROUP] 이미 등록됨")
        return

    target_groups.add(chat_id)
    save_groups(target_groups)

    await update.message.reply_text("✅ 이 그룹이 전달 대상에 추가되었습니다.")
    logger.info(f"[ADD_GROUP] 등록 완료 chat_id={chat_id}")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"[COMMAND] /remove_group from chat_id={chat_id}")

    if chat_id not in target_groups:
        await update.message.reply_text("등록되지 않은 그룹입니다.")
        logger.info("[REMOVE_GROUP] 대상 아님")
        return

    target_groups.remove(chat_id)
    save_groups(target_groups)

    await update.message.reply_text("❌ 이 그룹이 전달 대상에서 제거되었습니다.")
    logger.info(f"[REMOVE_GROUP] 제거 완료 chat_id={chat_id}")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("[COMMAND] /list_groups")

    if not target_groups:
        await update.message.reply_text("등록된 그룹이 없습니다.")
        logger.info("[LIST_GROUPS] 없음")
        return

    text = "📋 현재 전달 대상 그룹:\n"
    for gid in target_groups:
        text += f"- {gid}\n"

    await update.message.reply_text(text)
    logger.info(f"[LIST_GROUPS] 출력 완료 ({len(target_groups)}개)")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    source_chat_id = update.effective_chat.id
    text = update.message.text

    logger.info(
        f"[UPDATE] MESSAGE 수신 chat_id={source_chat_id} text='{text[:30]}'"
    )

    if source_chat_id in target_groups:
        logger.info("[FORWARD] 소스가 대상 그룹 → 자기 자신 전달 방지")
        return

    if not target_groups:
        logger.info("[FORWARD] 전달 대상 그룹 없음")
        return

    logger.info(f"[FORWARD] 전달 대상 그룹 수: {len(target_groups)}")

    for gid in target_groups:
        try:
            await context.bot.send_message(chat_id=gid, text=text)
            logger.info(f"[FORWARD] 전달 성공 → chat_id={gid}")
        except Exception as e:
            logger.error(f"[FORWARD] 전달 실패 → chat_id={gid} error={e}")

# =========================================================
# Telegram Application 생성
# =========================================================
logger.info("[TG] Telegram Application 생성 중")
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("add_group", add_group))
application.add_handler(CommandHandler("remove_group", remove_group))
application.add_handler(CommandHandler("list_groups", list_groups))
application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)
)

logger.info("[TG] 핸들러 등록 완료")

# =========================================================
# Flask Webhook 서버
# =========================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    logger.info("[HEALTH] 헬스 체크 요청")
    return "OK"

@app.route("/webhook", methods=["POST"])
def webhook():
    logger.info("[WEBHOOK] update 수신")

    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    asyncio.run(application.process_update(update))
    logger.info("[WEBHOOK] update 처리 완료")

    return "OK"

# =========================================================
# 실행
# =========================================================
async def main():
    logger.info("[TG] Webhook 설정 시작")
    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logger.info("[TG] Webhook 설정 완료")

if __name__ == "__main__":
    asyncio.run(main())

    logger.info(f"[FLASK] Flask 서버 시작 (port={PORT})")
    app.run(host="0.0.0.0", port=PORT)
