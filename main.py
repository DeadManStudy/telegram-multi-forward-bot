"""
telegram-multi-forward-bot
- Webhook 기반 Telegram 봇
- Render Web Service용
- 그룹을 동적으로 등록하여 메시지를 다중 포워딩
"""

# ======================
# 1. 기본 라이브러리
# ======================
import os
import json
import logging
import asyncio
from datetime import datetime
from threading import Thread

# ======================
# 2. Flask (Webhook 수신용)
# ======================
from flask import Flask, request, abort

# ======================
# 3. Telegram 라이브러리
# ======================
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ======================
# 4. 로깅 설정
# ======================
logging.basicConfig(level=logging.INFO)

def log(tag: str, message: str):
    """Render 로그에서 단계별로 보기 좋게 출력"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{tag}] {message}")

log("BOOT", "프로그램 시작")

# ======================
# 5. 환경 변수 로딩
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://xxxx.onrender.com

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN 또는 WEBHOOK_URL 이 설정되지 않았습니다.")

log("ENV", "환경 변수 로딩 완료")

# ======================
# 6. Flask 앱 생성
# ======================
app = Flask(__name__)
log("FLASK", "Flask 앱 생성 완료")

# ======================
# 7. Telegram Application 생성
# ======================
telegram_app = Application.builder().token(BOT_TOKEN).build()
log("TG", "Telegram Application 생성 완료")

# ======================
# 8. 메시지를 전달할 그룹 목록
# ======================
# - /add_group 로 추가
# - /remove_group 로 제거
TARGET_GROUPS: set[int] = set()

# ======================
# 9. 유틸 함수
# ======================
def is_group_chat(update: Update) -> bool:
    """그룹 / 슈퍼그룹 여부 판단"""
    return update.effective_chat.type in ("group", "supergroup")

# ======================
# 10. 그룹 관리 명령어
# ======================
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 채팅방을 포워딩 대상에 추가"""
    if not is_group_chat(update):
        await update.message.reply_text("❌ 이 명령어는 그룹에서만 사용할 수 있어요.")
        return

    chat_id = update.effective_chat.id
    TARGET_GROUPS.add(chat_id)

    log("GROUP", f"추가됨: {chat_id}")
    await update.message.reply_text("✅ 이 그룹이 메시지 전달 대상에 추가되었습니다.")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 채팅방을 포워딩 대상에서 제거"""
    if not is_group_chat(update):
        await update.message.reply_text("❌ 이 명령어는 그룹에서만 사용할 수 있어요.")
        return

    chat_id = update.effective_chat.id

    if chat_id not in TARGET_GROUPS:
        await update.message.reply_text("⚠️ 이 그룹은 전달 대상이 아닙니다.")
        return

    TARGET_GROUPS.remove(chat_id)
    log("GROUP", f"제거됨: {chat_id}")
    await update.message.reply_text("🗑️ 이 그룹을 전달 대상에서 제거했습니다.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 메시지를 보내고 있는 그룹 목록 출력"""
    if not TARGET_GROUPS:
        await update.message.reply_text("📭 현재 메시지를 보내는 그룹이 없습니다.")
        return

    text = "📤 메시지를 전달 중인 그룹 목록:\n\n"
    for gid in TARGET_GROUPS:
        text += f"- {gid}\n"

    await update.message.reply_text(text)

# ======================
# 11. 메시지 포워딩 로직
# ======================
async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    - 개인 채팅 / 그룹 어디서든 수신
    - 등록된 그룹으로 메시지 전달
    """
    if not update.message:
        return

    if not TARGET_GROUPS:
        log("FORWARD", "전달 대상 그룹 없음")
        return

    for group_id in TARGET_GROUPS:
        try:
            await context.bot.forward_message(
                chat_id=group_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
            log("FORWARD", f"{group_id} 로 전달 완료")
        except Exception as e:
            log("FORWARD", f"❌ 실패 ({group_id}): {e}")

# ======================
# 12. 핸들러 등록
# ======================
telegram_app.add_handler(CommandHandler("add_group", add_group))
telegram_app.add_handler(CommandHandler("remove_group", remove_group))
telegram_app.add_handler(CommandHandler("list_groups", list_groups))

# 텍스트 메시지 수신 시 포워딩
telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)
)

log("TG", "핸들러 등록 완료")

# ======================
# 13. Flask Webhook 엔드포인트
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    log("HTTP", "POST /webhook 수신")

    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        log("HTTP", "Update 객체 변환 성공")
    except Exception as e:
        log("HTTP", f"❌ Update 변환 실패: {e}")
        abort(400)

    # Telegram Application 큐에 전달
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/", methods=["GET"])
def health():
    log("HTTP", "GET / 요청 수신")
    return "OK", 200

# ======================
# 14. Telegram 백그라운드 실행
# ======================
async def run_telegram():
    log("TG", "initialize 시작")
    await telegram_app.initialize()
    log("TG", "initialize 완료")

    log("TG", "start 시작")
    await telegram_app.start()
    log("TG", "start 완료")

    webhook_full_url = f"{WEBHOOK_URL}/webhook"
    log("TG", f"Webhook 설정 시도: {webhook_full_url}")

    await telegram_app.bot.set_webhook(webhook_full_url)
    log("TG", "✅ Webhook 설정 완료")

def start_telegram_thread():
    asyncio.run(run_telegram())

# ======================
# 15. 메인 엔트리
# ======================
if __name__ == "__main__":
    log("MAIN", "메인 엔트리 진입")

    # Telegram은 백그라운드에서 실행
    Thread(target=start_telegram_thread, daemon=True).start()
    log("TG", "Telegram 백그라운드 스레드 시작")

    # Render에서 요구하는 포트
    port = int(os.environ.get("PORT", 10000))
    log("FLASK", f"Flask 서버 실행 (0.0.0.0:{port})")

    app.run(host="0.0.0.0", port=port)
