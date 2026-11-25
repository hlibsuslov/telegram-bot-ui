import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, Message

router = Router()

MENU = [
    BotCommand(command="start", description="Open the main menu"),
    BotCommand(command="help", description="How the bot works"),
    BotCommand(command="orders", description="Show my orders"),
]


@router.message(CommandStart())
async def on_start(message: Message):
    await message.answer("Hi")


@router.message(Command("help"))
async def on_help(message: Message):
    await message.answer("Help")


@router.message(Command(commands=["orders", "history"]))
async def on_orders(message: Message):
    await message.answer("Orders")


@router.message(F.text == "/ping")
async def on_ping(message: Message):
    await message.answer("pong")


# @router.message(Command("old"))
async def setup(bot: Bot):
    await bot.set_my_commands(MENU)
    await bot.set_my_commands(
        [BotCommand(command="start", description="Open the menu")],
        scope=BotCommandScopeAllPrivateChats(),
        language_code="ru",
    )


async def main():
    bot = Bot("TOKEN")
    dp = Dispatcher()
    dp.include_router(router)
    await setup(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
