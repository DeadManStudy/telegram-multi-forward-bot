"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- 그룹을 동적으로 등록하여 메시지를 다중 포워딩
"""

import os
import logging
import asyncio
from datetime import datetime
from threading import Thread

from flask import Flask, request, abort

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ======================
# 로깅
# ======================
logging.basicConfig(level=logging.INFO)

def log(tag, msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{tag}] {msg}")

log("BOOT", "프로그램 시작")

# ======================
# 환경 변수
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 누락")

# ======================
# Flask
# ======================
app = Flask(__name__)

# ======================
# Telegram
# ======================
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ======================
# 대상 그룹
# ======================
TARGET_GROUPS: set[int] = set()

# ======================
# 유틸
# ======================
def is_group(update: Update) -> bool:
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 명령어
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("❌ 그룹에서만 사용 가능합니다.")
        return

    cid = update.effective_chat.id
    TARGET_GROUPS.add(cid)

    log("GROUP", f"추가: {cid}")
    await update.message.reply_text("✅ 이 그룹이 전달 대상에 추가되었습니다.")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    TARGET_GROUPS.discard(cid)
    log("GROUP", f"제거: {cid}")
    await update.message.reply_text("🗑️ 전달 대상에서 제거했습니다.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TARGET_GROUPS:
        await update.message.reply_text("📭 등록된 그룹이 없습니다.")
        return

    text = "📤 전달 중인 그룹:\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"

    await update.message.reply_text(text)

# ======================
# 포워딩 (명령어 제외)
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    src_chat_id = update.effective_chat.id

    if not TARGET_GROUPS:
        log("FORWARD", "대상 그룹 없음")
        return

    for target_id in TARGET_GROUPS:
        # 🔥 포워딩에서만 자기 자신 차단
        if target_id == src_chat_id:
            continue

        try:
            await context.bot.forward_message(
                chat_id=target_id,
                from_chat_id=src_chat_id,
                message_id=update.message.message_id,
            )
            log("FORWARD", f"{src_chat_id} → {target_id}")
        except Exception as e:
            log("ERROR", f"{target_id} 전달 실패: {e}")

# ======================
# 핸들러
# ======================
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))

telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)
)

# ======================
# Webhook
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    except Exception:
        abort(400)

    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/")
def health():
    return "OK", 200

# ======================
# Telegram 실행
# ======================
async def run_telegram():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    log("TG", "Webhook 설정 완료")

def start_telegram():
    asyncio.run(run_telegram())

# ======================
# 엔트리
# ======================
if __name__ == "__main__":
    Thread(target=start_telegram, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
