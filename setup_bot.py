"""Разовая настройка публичного профиля бота через Telegram Bot API.

Запуск:  .venv/bin/python setup_bot.py
Меняет только имя, описания и список команд — логику бота не трогает.
"""
import asyncio

import aiohttp

import config

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

NAME = "БЖУ-бот 🥗"
SHORT = "Считаю калории и БЖУ, веду дневник и распознаю еду по фото 📷"
DESCRIPTION = (
    "🥗 БЖУ-бот — бесплатный помощник по питанию.\n\n"
    "Что умею:\n"
    "• Рассчитываю личную норму калорий и БЖУ\n"
    "• Считаю КБЖУ продуктов и блюд\n"
    "• Распознаю еду по фото\n"
    "• Веду дневник и показываю остаток на день\n"
    "• 35 рецептов с готовым БЖУ\n\n"
    "Все данные хранятся только у нас, без рекламы и регистрации. "
    "Начни с команды /start 🚀"
)

COMMANDS = [
    {"command": "start", "description": "Запустить бота"},
    {"command": "profile", "description": "Мой профиль и норма БЖУ"},
    {"command": "food", "description": "Найти продукт: /food гречка 150"},
    {"command": "photo", "description": "Посчитать еду по фото"},
    {"command": "recipes", "description": "Рецепты с БЖУ"},
    {"command": "today", "description": "Дневник за сегодня"},
    {"command": "pet", "description": "Мой питомец-тамагочи"},
    {"command": "norma", "description": "Показать мою норму"},
    {"command": "help", "description": "Как пользоваться"},
]


async def main() -> None:
    async with aiohttp.ClientSession() as s:
        calls = [
            ("setMyName", {"name": NAME}),
            ("setMyShortDescription", {"short_description": SHORT}),
            ("setMyDescription", {"description": DESCRIPTION}),
            ("setMyCommands", {"commands": COMMANDS}),
        ]
        for method, payload in calls:
            async with s.post(f"{API}/{method}", json=payload) as r:
                data = await r.json()
                mark = "✅" if data.get("ok") else "❌"
                print(f"{mark} {method}: {data.get('description', data)}")

        async with s.post(f"{API}/getMyName") as r:
            print("Имя сейчас:", (await r.json())["result"]["name"])
        async with s.post(f"{API}/getMyCommands") as r:
            cmds = (await r.json())["result"]
            print("Команд:", len(cmds))


if __name__ == "__main__":
    asyncio.run(main())
