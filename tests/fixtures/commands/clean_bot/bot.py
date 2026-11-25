from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

router = Router()
MENU = [
    BotCommand(command="start", description="Open the main menu"),
    BotCommand(command="help", description="Show what the bot can do"),
    BotCommand(command="settings", description="Change language and alerts"),
]


@router.message(CommandStart())
async def on_start(message: Message):
    await message.answer("Hi")


@router.message(Command("help"))
async def on_help(message: Message):
    await message.answer("Help")


@router.message(Command("settings"))
async def on_settings(message: Message):
    await message.answer("Settings")


async def setup(bot):
    await bot.set_my_commands(MENU)
