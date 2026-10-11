from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import db
import render
import ui

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state):
    db.upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(render.welcome(), reply_markup=ui.menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message, state):
    await message.answer(render.help_text(), reply_markup=ui.menu_kb())


@router.message(F.text.in_(ui.MENU))
async def on_menu(message: Message, state):
    await ui.try_menu(message, state)
