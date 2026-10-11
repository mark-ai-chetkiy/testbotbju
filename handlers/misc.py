"""Свободный ввод: если написать «гречка 150» без кнопки — тоже посчитаю."""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import ui

router = Router()


@router.message(StateFilter(None), F.text)
async def on_free_text(message: Message, state: FSMContext):
    if await ui.try_menu(message, state):
        return
    if await ui.try_command(message, state):
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    from handlers.food import handle_query

    await handle_query(message, state, text)
