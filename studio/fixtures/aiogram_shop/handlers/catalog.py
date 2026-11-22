from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
PHOTOS = {"coffee": "AgACAgIAAxkBAAICoffee01", "tea": "AgACAgIAAxkBAAICtea0001"}


class CatCb(CallbackData, prefix="cat"):
    slug: str


class ItemCb(CallbackData, prefix="item"):
    sku: str


def back_kb(to: str = "catalog") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="← Back", callback_data="catalog")],
                                                 [InlineKeyboardButton(text="Main menu", callback_data="menu")]])


def catalog_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Coffee", callback_data=CatCb(slug="coffee").pack())
    kb.button(text="Tea", callback_data=CatCb(slug="tea").pack())
    kb.button(text="Desserts", callback_data=CatCb(slug="desserts").pack())
    kb.button(text="Merch", callback_data=CatCb(slug="merch").pack())
    kb.button(text="Search", callback_data="search")
    kb.button(text="Main menu", callback_data="menu")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery) -> None:
    await callback.message.edit_text("<b>Menu</b>\nPick a category.", reply_markup=catalog_kb())


@router.callback_query(CatCb.filter(F.slug == "coffee"))
async def cat_coffee(callback: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Espresso", callback_data=ItemCb(sku="espresso").pack()),
         InlineKeyboardButton(text="Latte", callback_data=ItemCb(sku="latte").pack())],
        [InlineKeyboardButton(text="← Back", callback_data="catalog")]])
    await callback.message.answer_photo(PHOTOS["coffee"], caption="<b>Coffee</b>\nFresh every morning.", reply_markup=kb)


@router.callback_query(CatCb.filter(F.slug == "tea"))
async def cat_tea(callback: CallbackQuery) -> None:
    await callback.message.answer_photo(photo="AgACAgIAAxkBAAICtea0001", caption="<b>Tea</b>\nLoose leaf, 6 kinds.",
                                        reply_markup=back_kb())


@router.callback_query(CatCb.filter(F.slug == "desserts"))
async def cat_desserts(callback: CallbackQuery) -> None:
    await callback.message.edit_text("<b>Desserts</b>\nCroissants and cakes.", reply_markup=back_kb())


@router.callback_query(CatCb.filter(F.slug == "merch"))
async def cat_merch(callback: CallbackQuery) -> None:
    await callback.message.answer_photo("AgACAgIAAxkBAAICmerch01", caption="<b>Merch</b>\nMugs and beans.",
                                        has_spoiler=True, reply_markup=back_kb())


@router.callback_query(ItemCb.filter(F.sku == "espresso"))
async def item_espresso(callback: CallbackQuery) -> None:
    in_stock = True
    if not in_stock:
        await callback.message.edit_text("Espresso is sold out today.", reply_markup=back_kb())
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Add to cart", callback_data="add:espresso",
                                                                     style="success")],
                                               [InlineKeyboardButton(text="← Back", callback_data="catalog")]])
    await callback.message.edit_text("<b>Espresso</b>\n$2.50 · 30 ml", reply_markup=kb)


@router.callback_query(ItemCb.filter(F.sku == "latte"))
async def item_latte(callback: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Add to cart", callback_data="add:latte",
                                                                     style="success")],
                                               [InlineKeyboardButton(text="← Back", callback_data="catalog")]])
    await callback.message.edit_text("<b>Latte</b>\n$3.80 · 300 ml", reply_markup=kb)


@router.callback_query(F.data.startswith("add:"))
async def add_to_cart(callback: CallbackQuery) -> None:
    await callback.answer("Added to cart ✅")


@router.callback_query(F.data == "search")
async def search(callback: CallbackQuery) -> None:
    results = ["Espresso", "Latte", "Flat white"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r, callback_data=f"item:{r.lower()}")]
                                               for r in results])
    await callback.message.edit_text(f"Found {len(results)} drinks", reply_markup=kb)
