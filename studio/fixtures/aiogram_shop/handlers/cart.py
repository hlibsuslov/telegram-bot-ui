from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           Message, ReplyKeyboardMarkup, ReplyKeyboardRemove)

router = Router()


class Checkout(StatesGroup):
    address = State()
    phone = State()


def cart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Checkout", callback_data="checkout", style="primary")],
        [InlineKeyboardButton(text="Clear cart", callback_data="cart:clear", style="danger")],
        [InlineKeyboardButton(text="Main menu", callback_data="menu")]])


@router.callback_query(F.data == "cart")
async def show_cart(callback: CallbackQuery) -> None:
    items = []
    if not items:
        await callback.message.edit_text("Your cart is empty.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Open menu", callback_data="catalog")]]))
    else:
        await callback.message.edit_text(f"<b>Cart</b>\n{len(items)} items, total {sum(items)}", reply_markup=cart_kb())


@router.message(Command("cart"))
async def cmd_cart(message: Message) -> None:
    await message.answer("<b>Cart</b>\nTap to review your order.", reply_markup=cart_kb())


@router.callback_query(F.data == "cart:clear")
async def clear_cart(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Clear the whole cart?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Yes, clear", callback_data="cart:clear:yes", style="danger"),
        InlineKeyboardButton(text="Keep it", callback_data="cart")]]))


@router.callback_query(F.data == "cart:clear:yes")
async def clear_cart_yes(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Cart cleared.", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Main menu", callback_data="menu")]]))


@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Checkout.address)
    await callback.message.answer("Where should we bring it? Send the address.",
                                  reply_markup=ForceReply(input_field_placeholder="Street, house, flat"))


@router.message(Checkout.address)
async def checkout_address(message: Message, state: FSMContext) -> None:
    await state.update_data(address=message.text)
    await state.set_state(Checkout.phone)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Share phone", request_contact=True)]],
                             resize_keyboard=True, input_field_placeholder="Or type the number")
    await message.answer(f"Address: {message.text}\nNow your phone number.", reply_markup=kb)


@router.message(Checkout.phone)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Thanks! Review and pay.", reply_markup=ReplyKeyboardRemove())
    await message.answer("<b>Order summary</b>\nTotal: $6.30", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Pay $6.30", callback_data="pay", style="success")]]))


@router.callback_query(F.data == "pay")
async def pay(callback: CallbackQuery) -> None:
    ok = await charge(callback.from_user.id)
    if ok:
        await callback.message.answer_sticker("CAACAgIAAxkBAAIDsuccess1", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Track order", callback_data="track")]]))
    else:
        await callback.message.edit_text("⚠️ Payment failed. No money was taken.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Try again", callback_data="pay")],
                             [InlineKeyboardButton(text="Main menu", callback_data="menu")]]))


@router.callback_query(F.data == "track")
async def track(callback: CallbackQuery) -> None:
    await callback.message.answer_animation("https://example.com/courier.gif", caption="Your courier is on the way 🛵",
                                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                                [InlineKeyboardButton(text="Main menu", callback_data="menu")]]))


async def charge(user_id: int) -> bool:
    return True
