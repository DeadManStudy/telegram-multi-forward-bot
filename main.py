from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

TOKEN = os.environ["BOT_TOKEN"]

TARGET_CHAT_IDS = [
    -5258812606,
]

# ---- 더미 HTTP 서버 (Render용) ----
def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()
# ---------------------------------

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("보낼 메시지를 입력하세요.")
        return

    for chat_id in TARGET_CHAT_IDS:
        await context.bot.send_message(chat_id=chat_id, text=text)

    await update.message.reply_text("✅ 전송 완료")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("send", send_all))

app.run_polling()
