import asyncio
import base64
import logging

from aiogram import Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
import gemini
from handlers import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


async def recognize(request: web.Request) -> web.Response:
    """Распознавание еды по фото для статической Mini App.

    Ключ Gemini остаётся на сервере: во фронтенд он не попадает.
    На холодный старт Render приложение подготавливает сервис заранее,
    но первый запрос после простоя всё равно может занять ~40 секунд.
    """
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=CORS)

    try:
        data = await request.json()
        raw = str(data.get("image") or "")
        if "," in raw:  # data:image/jpeg;base64,...
            raw = raw.split(",", 1)[1]
        image_bytes = base64.b64decode(raw, validate=True)
        if not image_bytes or len(image_bytes) > 8_000_000:
            raise ValueError("Слишком большое или пустое изображение")

        mime = str(data.get("mime") or "image/jpeg")
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            mime = "image/jpeg"

        items = await gemini.recognize(image_bytes, mime)
        return web.json_response({"items": items}, headers=CORS)
    except Exception as exc:
        log.exception("Не удалось распознать фото")
        return web.json_response(
            {"error": str(exc)[:200]}, status=500, headers=CORS,
        )


async def debug_models(request: web.Request) -> web.Response:
    return web.json_response({"models": await gemini.probe_models()}, headers=CORS)


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
    app.router.add_route("*", "/api/recognize", recognize)
    app.router.add_get("/api/debug-models", debug_models)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    log.info("Health-check сервер запущен на порту %s", config.PORT)

    log.info("Бот запущен, идёт polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
