"""Разовая настройка публичного профиля бота через Telegram Bot API.

Запуск:  .venv/bin/python setup_bot.py
Меняет только имя, описания и список команд — логику бота не трогает.
"""
import asyncio

import aiohttp

import config

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

NAME = "БЖУ и Зал 🥗"
SHORT = "Считаю БЖУ, веду дневник и отслеживаю тренировки 🏋️"
DESCRIPTION = (
    "🥗 БЖУ и Зал — мини-приложение прямо в Телеге.\n\n"
    "• 344 продукта: найди и укажи вес порции — получишь калории и БЖУ\n"
    "• фото еды: ИИ рассчитает БЖУ по снимку\n"
    "• 35 рецептов и личная норма за 30 секунд\n"
    "• дневник с историей и прогрессом\n"
    "• вкладка «Зал»: чекины, челлендж, результат для тренера\n\n"
    "Открыть мини-приложение: https://t.me/GymTamagotchi_bot?startapp=channel"
)

COMMANDS = [
    {"command": "start", "description": "Запустить бота"},
    {"command": "profile", "description": "Мой профиль и норма БЖУ"},
    {"command": "food", "description": "Найти продукт: /food гречка 150"},
    {"command": "photo", "description": "Посчитать еду по фото"},
    {"command": "recipes", "description": "Рецепты с БЖУ"},
    {"command": "today", "description": "Дневник за сегодня"},
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
