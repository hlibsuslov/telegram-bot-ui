"""Synthetic aiogram 3 coffee-shop bot for `bot-ui import` tests. Never run; no token."""
import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from handlers import cart, catalog, profile, promo, start, support


async def main() -> None:
    bot = Bot(os.environ["BOT_TOKEN"], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    for module in (start, catalog, cart, profile, support, promo):
        dp.include_router(module.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
