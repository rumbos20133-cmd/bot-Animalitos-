import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="¡Hola!"
    )


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.environ["TOKEN"]).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()
