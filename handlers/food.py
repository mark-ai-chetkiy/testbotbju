import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
import pet
import render
import ui
from nutrition import fmt, scale, search_products

router = Router()

NUM_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*(г|гр|грамм|g|kg|кг)?\.?\s*$", re.I)


class FoodSG(StatesGroup):
    wait = State()


def parse_query(text: str) -> tuple[str, float | None]:
    m = NUM_RE.search(text)
    grams = None
    q = text
    if m:
        val = float(m.group(1).replace(",", "."))
        if (m.group(2) or "").lower() in ("kg", "кг"):
            val *= 1000
        if val > 0:
            grams = val
            q = text[:m.start()].strip(" ,.-")
    return q, grams


async def show_item(message: Message, state: FSMContext, item: dict):
    await state.update_data(pending=item)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ В дневник", callback_data="addfood")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="fcancel")],
    ])
    await message.answer(render.food_card(item) + "\n\nДобавить в дневник? 📝",
                         reply_markup=kb)


async def handle_query(message: Message, state: FSMContext, text: str):
    q, grams = parse_query(text)
    if not q:
        return await message.answer(
            "Напиши так: «гречка 150» или «творог 9% 200» 👇")
    matches = search_products(q)
    if not matches:
        return await message.answer(
            "😔 Не нашёл такой продукт.\n"
            "Попробуй другое название — например «творог», «куриная грудка», «рис».")
    if len(matches) == 1:
        i, prod = matches[0]
        g = grams or 100
        await show_item(message, state, {"name": prod["n"], "grams": g, **scale(prod, g)})
        if not grams:
            await message.answer("Принял за 100 г. Указать другой вес: «название 150»")
        return
    # несколько совпадений — покажем список, запомнив граммы
    await state.update_data(grams=grams or 100)
    rows = [[InlineKeyboardButton(text=f"{p['n'].capitalize()}  ·  {fmt(p['k'])} ккал/100 г",
                                  callback_data=f"fi:{i}")] for i, p in matches[:8]]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="fcancel")])
    await message.answer(render.search_result(matches, grams),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def cmd_food(message: Message, state: FSMContext, args: str = ""):
    if args:
        return await handle_query(message, state, args)
    await state.set_state(FoodSG.wait)
    await message.answer(
        "Ищи любой продукт 👇 Напиши название и граммы:\n"
        "«гречка 150» • «куриная грудка 200» • «сыр российский 50»",
        reply_markup=ui.cancel_kb())


@router.message(Command("food"))
async def cmd_food_cmd(message: Message, state: FSMContext):
    await state.clear()
    args = (message.text or "").split(maxsplit=1)
    await cmd_food(message, state, args[1] if len(args) > 1 else "")


@router.message(FoodSG.wait, F.text)
async def on_food_text(message: Message, state: FSMContext):
    if await ui.try_menu(message, state):
        return
    if await ui.try_command(message, state):
        return
    if await ui.is_cancel(message):
        await state.clear()
        await message.answer("Отменено 👌", reply_markup=ui.menu_kb())
        return
    await handle_query(message, state, message.text or "")


@router.callback_query(F.data == "fcancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Отменено 👌")
    await cb.answer()


@router.callback_query(F.data.startswith("fi:"))
async def on_pick(cb: CallbackQuery, state: FSMContext):
    i = int(cb.data.split(":")[1])
    prod = (await state.get_data()).get("grams") or 100
    from nutrition import load_products
    p = load_products()[i]
    await cb.message.edit_text("Выбрано ✅")
    await show_item(cb.message, state, {"name": p["n"], "grams": prod, **scale(p, prod)})
    await cb.answer()


@router.callback_query(F.data == "addfood")
async def on_add(cb: CallbackQuery, state: FSMContext):
    item = (await state.get_data()).get("pending")
    if not item:
        await cb.answer("Данные устарели, повтори запрос")
        return
    db.add_food(cb.from_user.id, item["name"], item["grams"],
                item["p"], item["f"], item["c"], item["k"])
    await state.clear()
    text = "✅ <b>Добавлено в дневник</b>\n\n" + render.food_card(item)
    react = pet.reaction(cb.from_user.id)
    if react:
        text += "\n\n" + react
    await cb.message.edit_text(text)
    await cb.answer("Добавлено! ✅")
