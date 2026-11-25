from telegram import BotCommand, BotCommandScopeAllGroupChats
from telegram.ext import Application, CommandHandler


async def start(update, context):
    await update.message.reply_text("Hi")


async def info(update, context):
    await update.message.reply_text("Info")


async def post_init(application):
    await application.bot.set_my_commands([BotCommand("start", "Start the bot"), BotCommand("about", "About us")])
    await application.bot.set_my_commands(
        [("start", "Start the bot")],
        scope=BotCommandScopeAllGroupChats(),
    )


def main():
    app = Application.builder().token("TOKEN").post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["about", "info"], info))
    app.run_polling()


if __name__ == "__main__":
    main()
