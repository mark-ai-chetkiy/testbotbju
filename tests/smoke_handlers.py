"""Оффлайн-прогон обработчиков: виртуальные апдейты, сеть к Telegram не нужна.

Запуск:  .venv/bin/python tests/smoke_handlers.py
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("GEMINI_API_KEY", "")

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import (CallbackQuery, Chat, Message, Update,  # noqa: E402
                           User)

import config  # noqa: E402
import db  # noqa: E402
from handlers import register_all  # noqa: E402


class FakeSession:
    """Ловит исходящие вызовы Bot API и возвращает заглушку."""

    def __init__(self) -> None:
        self.calls: list = []

    async def __call__(self, bot, method, timeout=None):
        self.calls.append(method)
        return True

    async def close(self) -> None:
        pass


USER = User(id=111, is_bot=False, first_name="Тест")
CHAT = Chat(id=111, type="private")
_uid = 0


def msg(text: str | None = None, photo: bool = False) -> Message:
    global _uid
    _uid += 1
    return Message(
        message_id=_uid, date=datetime.now(), chat=CHAT, from_user=USER, text=text
    )


async def feed(dp, bot, update: Update):
    await dp.feed_update(bot, update)


async def main() -> None:
    bot = Bot(config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session = FakeSession()
    db.init_db()
    dp = Dispatcher(storage=MemoryStorage())
    register_all(dp)
    upd = 0

    async def send(text: str):
        nonlocal upd
        upd += 1
        await dp.feed_update(bot, Update(update_id=upd, message=msg(text)))

    async def cb(data: str):
        nonlocal upd
        upd += 1
        m = msg()
        q = CallbackQuery(id=str(upd), from_user=USER, chat_instance="x",
                          data=data, message=m)
        await dp.feed_update(bot, Update(update_id=upd, callback_query=q))

    # /start
    await send("/start")
    # питомец: имя -> карточка
    await send("🐣 Питомец")
    await send("Бублик")
    # профиль
    await send("👤 Профиль")
    await send("👦 Парень")
    await send("25")
    await send("175")
    await send("70")
    await send("🏃 Средняя (3–5 тренировок в неделю)")
    await send("🔥 Похудение")
    # продукт
    await send("гречка 150")
    await cb("fi:0")
    # продукт с выбором
    await send("яблоко 100")
    await cb("fi:0")
    # рецепты
    await send("📖 Рецепты")
    await cb("rec:0:0")
    await cb("radd:0")
    await cb("rp:0")
    # питомец после еды
    await send("🐣 Питомец")
    # дневник
    await send("📊 Дневник")
    # норма
    await send("/norma")
    # сброс
    await send("⚙️ Сброс")
    await cb("resyes")
    await send("📊 Дневник")
    # помощь
    await send("/help")

    sent = [c for c in bot.session.calls if type(c).__name__ in
            ("SendMessage", "EditMessageText")]
    print(f"OK: {len(bot.session.calls)} вызовов Bot API, "
          f"{len(sent)} сообщений обработано")
    print("Типы вызовов:", sorted({type(c).__name__ for c in bot.session.calls}))
    print("SMOKE PASSED")


if __name__ == "__main__":
    asyncio.run(main())
