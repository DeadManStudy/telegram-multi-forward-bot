import os
import json
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────
# 환경 변수
# ─────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPER_ADMIN_ID = int(os.environ["SUPER_ADMIN_ID"])

GROUPS_FILE = "groups.json"
ADMINS_FILE = "admins.json"

# ─────────────────────────
# JSON 유틸
# ─────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

groups = load_json(GROUPS_FILE, {})
admins = load_json(ADMINS_FILE, [])

# 슈퍼 관리자 자동 등록
if SUPER_ADMIN_ID not in admins:
    admins.append(SUPER_ADMIN_ID)
    save_json(ADMINS_FILE, admins)
    print(f"✅ SUPER_ADMIN 등록됨: {SUPER_ADMIN_ID}")

# ─────────────────────────
# 관리자 체크
# ─────────────────────────
def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id in admins

# ─────────────────────────
# 명령어
# ─────────────────────────
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    chat = update.effective_chat
    groups[str(chat.id)] = {"title": chat.title}
    save_json(GROUPS_FILE, groups)
    await update.message.reply_text(
        f"✅ 그룹 등록 완료\n\n{chat.title}\n{chat.id}"
    )

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    text = "👑 관리자 목록\n\n" + "\n".join(str(a) for a in admins)
    await update.message.reply_text(text)

# ─────────────────────────
# 메시지 포워딩
# ─────────────────────────
async def forward_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if update.message.text and update.message.text.startswith("/"):
        return
    if not is_admin(update):
        return

    for cid in groups:
        try:
            await update.message.forward(chat_id=int(cid))
        except Exception as e:
            print(f"❌ Forward error: {e}")

# ─────────────────────────
# 메인
# ─────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("add_group", add_group))
    app.add_handler(CommandHandler("list_admins", list_admins))
    app.add_handler(MessageHandler(filters.ALL, forward_all))

    print("🤖 Bot started (polling)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
