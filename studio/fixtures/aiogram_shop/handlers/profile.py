from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import ReplyKeyboardBuilder

router = Router()


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("My orders"), callback_data="orders")],
        [InlineKeyboardButton(text=_("Language"), callback_data="lang")],
        [InlineKeyboardButton(text=_("Main menu"), callback_data="menu")]])


@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery) -> None:
    await callback.message.edit_text(_("Your profile"), reply_markup=profile_kb())


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    await message.answer(_("Your profile"), reply_markup=profile_kb())


@router.callback_query(F.data == "orders")
async def orders(callback: CallbackQuery) -> None:
    await callback.message.edit_text(_("No orders yet."), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("Back"), callback_data="profile")]]))


def lang_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="English")
    kb.button(text="Русский")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


@router.callback_query(F.data == "lang")
async def language(callback: CallbackQuery) -> None:
    await callback.message.answer(_("Choose a language"), reply_markup=lang_kb())


@router.message(F.text == "English")
async def lang_en(message: Message) -> None:
    await message.answer("Language: English", reply_markup=profile_kb())


@router.message(F.text == "Русский")
async def lang_ru(message: Message) -> None:
    await message.answer("Язык: русский", reply_markup=profile_kb())
