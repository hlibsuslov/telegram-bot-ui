from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()

WELCOME = ('<tg-emoji emoji-id="5368324170671202286">☕</tg-emoji> <b>Coffee Point</b>\n'
           "Order ahead and skip the queue.")
TEXTS = {"help": "Commands: /start, /menu, /cart, /profile, /support", "about": "We roast beans every Monday."}


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Menu", callback_data="catalog", icon_custom_emoji_id="5370869711888194012",
                              style="primary")],
        [InlineKeyboardButton(text="Cart", callback_data="cart"),
         InlineKeyboardButton(text="Profile", callback_data="profile")],
        [InlineKeyboardButton(text="Support", callback_data="support"),
         InlineKeyboardButton(text="Promo", callback_data="promo")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME, reply_markup=main_menu())


@router.callback_query(F.data == "menu")
async def back_to_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(WELCOME, reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(TEXTS["help"])


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer_photo("https://example.com/roastery.jpg", caption=TEXTS["about"],
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                   [InlineKeyboardButton(text="Back to menu", callback_data="menu")]]))
