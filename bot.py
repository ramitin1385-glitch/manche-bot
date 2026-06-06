from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "توکن_جدید_ربات"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 ربات منچ جدید آماده است!"
    )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
