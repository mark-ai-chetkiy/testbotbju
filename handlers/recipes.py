from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
import pet
import render
from nutrition import fmt, load_recipes

router = Router()

PER_PAGE = 8


def _page_kb(page: int) -> InlineKeyboardMarkup:
    recipes = load_recipes()
    start = page * PER_PAGE
    rows = [[InlineKeyboardButton(text=f"🍽 {r['n']}  ·  {fmt(r['k'])} ккал",
                                  callback_data=f"rec:{start + i}:{page}")]
            for i, r in enumerate(recipes[start:start + PER_PAGE])]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"rp:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{_pages()}", callback_data="rhere"))
    if (page + 1) * PER_PAGE < len(recipes):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"rp:{page + 1}"))
    rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _pages() -> int:
    return (len(load_recipes()) + PER_PAGE - 1) // PER_PAGE


def _list_text() -> str:
    return render.recipe_list(len(load_recipes()))


async def cmd_recipes(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(_list_text(), reply_markup=_page_kb(0))


@router.message(Command("recipes"))
async def cmd_recipes_cmd(message: Message, state: FSMContext):
    await cmd_recipes(message, state)


@router.callback_query(F.data.startswith("rp:"))
async def on_page(cb: CallbackQuery, state: FSMContext):
    page = int(cb.data.split(":")[1])
    await cb.message.edit_text(_list_text(), reply_markup=_page_kb(page))
    await cb.answer()


@router.callback_query(F.data == "rhere")
async def on_here(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("rec:"))
async def on_recipe(cb: CallbackQuery, state: FSMContext):
    _, i, page = cb.data.split(":")
    i, page = int(i), int(page)
    r = load_recipes()[i]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 Добавить порцию в дневник",
                              callback_data=f"radd:{i}")],
        [InlineKeyboardButton(text="◀️ К списку рецептов", callback_data=f"rp:{page}")],
    ])
    await cb.message.edit_text(render.recipe_card(r), reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("radd:"))
async def on_add(cb: CallbackQuery, state: FSMContext):
    i = int(cb.data.split(":")[1])
    r = load_recipes()[i]
    db.add_food(cb.from_user.id, f"{r['n']} (рецепт)", 0,
                r["p"], r["f"], r["c"], r["k"])
    react = pet.reaction(cb.from_user.id)
    text = "🍽 Порция добавлена в дневник ✅"
    if react:
        text += f"\n{react}"
    await cb.answer(text)
