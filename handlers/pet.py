"""Питомец-тамагочи: рост, настроение, стрик."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import db
import pet
import render
import ui

router = Router()


class PetSG(StatesGroup):
    name = State()


async def show(message: Message, state: FSMContext, user_id: int):
    p = db.get_pet(user_id)
    if not p:
        await state.set_state(PetSG.name)
        return await message.answer(render.pet_intro(),
                                    reply_markup=ui.cancel_kb())
    s = pet.stats(user_id, pet.target_for(user_id))
    await message.answer(render.pet_card(p["name"], s),
                         reply_markup=ui.menu_kb())


async def cmd_pet(message: Message, state: FSMContext):
    await show(message, state, message.from_user.id)


@router.message(Command("pet"))
async def cmd_pet_cmd(message: Message, state: FSMContext):
    await state.clear()
    await show(message, state, message.from_user.id)


@router.message(PetSG.name, F.text)
async def on_name(message: Message, state: FSMContext):
    if await ui.try_menu(message, state):
        return
    if await ui.try_command(message, state):
        return
    if await ui.is_cancel(message):
        await state.clear()
        return await message.answer("Ладно, выберешь имя позже 👌",
                                    reply_markup=ui.menu_kb())
    name = (message.text or "").strip()
    if not name:
        return await message.answer("Напиши имя одним словом 🙂")
    name = name[:20]
    db.create_pet(message.from_user.id, name)
    await state.clear()
    await message.answer(f"🎉 Теперь меня зовут <b>{render.esc(name)}</b>!")
    await show(message, state, message.from_user.id)
