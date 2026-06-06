from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8945308523:AAHNP6225eb6jqy2u_kf00x9iFeS_cdSlEQ"

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
