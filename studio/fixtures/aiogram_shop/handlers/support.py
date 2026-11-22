from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()
SUPPORT_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="FAQ video", callback_data="support:faq")],
    [InlineKeyboardButton(text="Voice answer", callback_data="support:voice")],
    [InlineKeyboardButton(text="Price list", callback_data="support:prices")],
    [InlineKeyboardButton(text="Write to a person", url="https://t.me/coffeepoint_help")],
    [InlineKeyboardButton(text="Main menu", callback_data="menu")]])


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery) -> None:
    await callback.message.edit_text("How can we help?", reply_markup=SUPPORT_KB)


@router.callback_query(F.data == "support:faq")
async def faq(callback: CallbackQuery) -> None:
    await callback.message.answer_video("BAACAgIAAxkBAAIEfaqvideo", caption="FAQ in 60 seconds",
                                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                            [InlineKeyboardButton(text="← Support", callback_data="support")]]))


@router.callback_query(F.data == "support:voice")
async def voice(callback: CallbackQuery) -> None:
    await callback.message.answer_voice("AwACAgIAAxkBAAIEvoice001", caption="Our barista explains the menu")


@router.callback_query(F.data == "support:prices")
async def prices(callback: CallbackQuery) -> None:
    await callback.message.answer_photo(FSInputFile("assets/prices.png"), caption="Price list")


async def greeting(message: Message) -> None:
    await message.answer_video_note("DQACAgIAAxkBAAIEnote0001")


router.message.register(greeting, Command("hello"))


@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    await message.answer("How can we help?", reply_markup=SUPPORT_KB)


@router.message(Command("playlist"))
async def playlist(message: Message) -> None:
    await message.answer_audio("CQACAgIAAxkBAAIEaudio001", caption="Café playlist", title="Morning")
