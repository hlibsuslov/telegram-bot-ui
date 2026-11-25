"""Coffee order bot (aiogram 3): menu, order form, AI answers and a profile screen.

Eval fixture: a small, deliberately imperfect bot that activation cases run in, so requests
such as "fix long-message splitting" have a bot to refer to. Never run against a real token.
"""
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

dp = Dispatcher()
ORDERS: dict[int, dict] = {}   # user id -> form fields filled so far
FORM_FIELDS = ("size", "milk", "pickup_time")


def kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows])


MAIN_MENU = kb([("Order coffee", "order")], [("Ask the barista AI", "ask")], [("My profile", "profile")])


@dp.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer("Welcome to Bean There! What would you like?", reply_markup=MAIN_MENU)


@dp.callback_query(F.data == "menu")
async def menu(call: CallbackQuery) -> None:
    await call.message.edit_text("What would you like?", reply_markup=MAIN_MENU)


@dp.callback_query(F.data == "order")
async def order(call: CallbackQuery) -> None:
    form = ORDERS.setdefault(call.from_user.id, {})
    lines = [f"{field}: {form.get(field, '—')}" for field in FORM_FIELDS]
    await call.message.edit_text("Your order\n" + "\n".join(lines), reply_markup=kb(
        [("Size", "set:size"), ("Milk", "set:milk"), ("Pickup time", "set:pickup_time")],
        [("Submit", "submit")],
        [("⬅️ Back", "menu")]))


@dp.callback_query(F.data == "submit")
async def submit(call: CallbackQuery) -> None:
    form = ORDERS.get(call.from_user.id, {})
    if any(field not in form for field in FORM_FIELDS):
        await call.answer("Fill in every field first", show_alert=True)
        return
    await call.message.edit_text("Order placed!", reply_markup=kb([("Return", "menu")]))


@dp.callback_query(F.data == "ask")
async def ask(call: CallbackQuery) -> None:
    await call.message.edit_text("Send me your question.", reply_markup=kb([("Go back", "menu")]))


def split_text(text: str, size: int = 4096) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


@dp.message(F.text)
async def answer_question(message: Message) -> None:
    reply = await generate_answer(message.text)   # long HTML from the model
    for part in split_text(reply):
        await message.answer(part, parse_mode="HTML")


@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery) -> None:
    # TODO: colour this screen with the accent of the user's own share screen.
    await call.message.edit_text(f"Hi, {call.from_user.first_name}!", reply_markup=kb([("« Main menu", "menu")]))


async def generate_answer(question: str) -> str:
    return f"<b>Barista AI</b>\n{question}"   # stub for the model call


async def main() -> None:
    await dp.start_polling(Bot(os.environ["BOT_TOKEN"]))


if __name__ == "__main__":
    asyncio.run(main())
