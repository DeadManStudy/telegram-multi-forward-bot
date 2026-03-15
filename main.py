"""
telegram-multi-forward-bot (Railway Safe Version)

- Webhook 기반 Telegram 봇
- Railway 배포용
- Queue + Worker broadcast 구조
- Rate limit 적용
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
import logging
import asyncio
from threading import Thread

# ======================
# 2. Flask
# ======================
from flask import Flask, request, abort

# ======================
# 3. Telegram
# ======================
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ======================
# 4. 로깅
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log(tag, msg):
    logging.info(f"[{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경변수
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

SUPER_ADMIN_IDS = {
    int(x) for x in os.getenv("SUPER_ADMIN_IDS", "").split(",") if x.strip()
}

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 누락")

# ======================
# 6. 그룹 로딩
# ======================
def load_group_env(name):
    return {
        int(x) for x in os.getenv(name, "").split(",") if x.strip()
    }

GROUPS = {
    "GROUP1": load_group_env("GROUP1_IDS"),
    "GROUP2": load_group_env("GROUP2_IDS"),
    "GROUP3": load_group_env("GROUP3_IDS"),
}

# ======================
# 7. 상태 변수
# ======================
CURRENT_TARGET = None

# ======================
# 8. Queue
# ======================
SEND_QUEUE = asyncio.Queue()

# ======================
# 9. Flask
# ======================
app = Flask(__name__)

# ======================
# 10. Telegram App
# ======================
application = Application.builder().token(BOT_TOKEN).build()

# ======================
# 11. 유틸
# ======================
def is_super_admin(uid: int) -> bool:
    return uid in SUPER_ADMIN_IDS

def is_private(update: Update) -> bool:
    return update.effective_chat.type == "private"

# ======================
# 12. Broadcast Worker
# ======================
async def sender_worker():

    log("WORKER", "sender worker 시작")

    while True:

        gid, update = await SEND_QUEUE.get()

        try:

            await application.bot.forward_message(
                chat_id=gid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )

            log("SEND", f"forward → {gid}")

        except Exception as e:
            log("ERROR", f"{gid} | {e}")

        await asyncio.sleep(2)  # rate limit


# ======================
# 13. 명령어
# ======================
async def send_group(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):

    global CURRENT_TARGET

    if not is_private(update):
        return

    if not is_super_admin(update.effective_user.id):
        return

    CURRENT_TARGET = name

    await update.message.reply_text(
        f"✅ [{name}]으로 메시지를 전송합니다"
    )


async def send_group1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_group(update, context, "GROUP1")


async def send_group2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_group(update, context, "GROUP2")


async def send_group3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_group(update, context, "GROUP3")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global CURRENT_TARGET

    if not is_private(update):
        return

    if not is_super_admin(update.effective_user.id):
        return

    CURRENT_TARGET = None

    await update.message.reply_text(
        "⛔ 메시지 전송 중지"
    )


# ======================
# 14. 메시지 처리
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if not is_private(update):
        return

    if not is_super_admin(update.effective_user.id):
        return

    if not CURRENT_TARGET:
        return

    targets = GROUPS.get(CURRENT_TARGET, set())

    for gid in targets:

        await SEND_QUEUE.put((gid, update))

    await update.message.reply_text(
        f"📤 {len(targets)}개 그룹 전송 시작"
    )


# ======================
# 15. 핸들러 등록
# ======================
application.add_handler(CommandHandler("send_group1", send_group1))
application.add_handler(CommandHandler("send_group2", send_group2))
application.add_handler(CommandHandler("send_group3", send_group3))

application.add_handler(CommandHandler("stop", stop))

application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)
)

# ======================
# 16. Webhook
# ======================
telegram_loop = asyncio.new_event_loop()

@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
    except Exception:
        abort(400)

    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        telegram_loop
    )

    return "OK"


@app.route("/")
def health():
    return "OK"


# ======================
# 17. Telegram 실행
# ======================
async def run_telegram():

    await application.initialize()
    await application.start()

    # worker 시작
    asyncio.create_task(sender_worker())

    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

    log("TG", "Webhook 설정 완료")


def start_telegram():

    asyncio.set_event_loop(telegram_loop)

    telegram_loop.run_until_complete(run_telegram())

    telegram_loop.run_forever()


# ======================
# 18. MAIN
# ======================
if __name__ == "__main__":

    Thread(target=start_telegram, daemon=True).start()

    port = int(os.getenv("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
