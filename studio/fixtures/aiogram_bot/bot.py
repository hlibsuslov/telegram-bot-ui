"""Synthetic aiogram bot for `bot-ui inventory` tests (never run)."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()


def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Catalog", callback_data="menu:catalog")],
        [InlineKeyboardButton(text="Help", url="https://example.com/help")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("<b>Welcome</b>\nPick a section.", reply_markup=menu())


@router.callback_query(F.data == "menu:catalog")
async def on_catalog(query: CallbackQuery) -> None:
    items = [InlineKeyboardButton(text=name, callback_data=f"item:{i}") for i, name in enumerate(["A", "B"])]
    await query.message.edit_text("Catalog", reply_markup=InlineKeyboardMarkup(inline_keyboard=[items]))


@router.callback_query(F.data.startswith("item:"))
async def on_item(query: CallbackQuery) -> None:
    await query.message.edit_text(f"Item {query.data}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer("Write to support@example.com")
