from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()


@router.callback_query(F.data == "promo")
async def promo(callback: CallbackQuery) -> None:
    await callback.message.answer_animation("https://example.com/promo.gif", caption=(
        '<tg-emoji emoji-id="5373141891321699086">🔥</tg-emoji> <b>2 for 1</b> on lattes until Sunday'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Invite a friend", callback_data="promo:invite")],
            [InlineKeyboardButton(text="Main menu", callback_data="menu")]]))


@router.callback_query(F.data == "promo:invite")
async def invite(callback: CallbackQuery) -> None:
    link = f"https://t.me/coffeepoint_bot?start=ref{callback.from_user.id}"
    await callback.message.answer(f"Share your link: {link}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Main menu", callback_data="menu")]]))


@router.message(CommandStart(deep_link=True))
async def start_ref(message: Message) -> None:
    await message.answer("Welcome! Your friend gave you a free cookie 🍪", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Open menu", callback_data="catalog")]]))


@router.message(Command("secret"))
async def secret(message: Message) -> None:
    await message.answer_photo("AgACAgIAAxkBAAIEsecret01", caption="Today's secret drink", has_spoiler=True)
