import asyncio
import logging

from aiogram import Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан — заполни файл .env")

    db.init_db()

    bot = Bot(config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    register_all(dp)

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    log.info("Health-check сервер запущен на порту %s", config.PORT)

    log.info("Бот запущен, идёт polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
