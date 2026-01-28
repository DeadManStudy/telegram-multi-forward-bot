import os
import json
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

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN이 없습니다.")

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
# 핸들러
# =====================
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("❌ 권한이 없습니다.")
        return

    admins = load_admins()
    if not admins:
        await update.message.reply_text("📭 관리자 없음")
        return

    await update.message.reply_text(
        "📋 관리자 목록:\n" + "\n".join(map(str, admins))
    )

# =====================
# 메인
# =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("list_admins", list_admins))

    print("🤖 Bot started (polling)")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
