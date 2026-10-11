from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
import pet
import render
import ui
from gemini import recognize
from nutrition import best_db_match, fmt, scale

router = Router()


class PhotoSG(StatesGroup):
    wait = State()


def _items_kb(items: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"➕ {it['name'].capitalize()} · {fmt(it['k'])} ккал",
                                  callback_data=f"padd:{i}")]
            for i, it in enumerate(items)]
    rows.append([InlineKeyboardButton(text="✅ Добавить всё в дневник", callback_data="pall")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="pcancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_photo(message: Message, state: FSMContext):
    if not config.GEMINI_API_KEY:
        return await message.answer(
            "📷 <b>Распознавание по фото скоро включим</b>\n\n"
            "Пока посчитаю еду по названию:\n"
            "🔍 напиши, например, «гречка 150»\n"
            "📖 или выбери готовый рецепт",
            reply_markup=ui.menu_kb())
    await state.set_state(PhotoSG.wait)
    await message.answer(
        "📷 <b>Пришли фото блюда</b>\n"
        "Определю, что на тарелке, и посчитаю калории и БЖУ на порцию.",
        reply_markup=ui.cancel_kb())


@router.message(Command("photo"))
async def cmd_photo_cmd(message: Message, state: FSMContext):
    await state.clear()
    await cmd_photo(message, state)


@router.message(PhotoSG.wait, F.photo)
async def on_photo(message: Message, state: FSMContext, bot):
    await message.answer("🔍 Анализирую фото…")
    file = await bot.get_file(message.photo[-1].file_id)
    data = await bot.download(file)
    try:
        raw = await recognize(data.read())
    except Exception as e:  # noqa: BLE001
        await state.clear()
        return await message.answer(f"⚠️ Не получилось распознать: {render.esc(e)}",
                                    reply_markup=ui.menu_kb())
    if not raw:
        await state.clear()
        return await message.answer(
            "😕 Не смог определить еду на фото. Попробуй фото получше "
            "при хорошем освещении.", reply_markup=ui.menu_kb())

    items = []
    for it in raw:
        prod = best_db_match(it["name"])
        if prod:
            s = scale(prod, it["grams"])
            items.append({"name": prod["n"], "grams": it["grams"], **s})
        else:
            items.append({
                "name": it["name"], "grams": it["grams"],
                "p": it["protein"], "f": it["fat"],
                "c": it["carbs"], "k": it["calories"],
            })
    await state.set_state(PhotoSG.wait)
    await state.update_data(photo_items=items)
    await message.answer(render.photo_card(items), reply_markup=_items_kb(items))


@router.message(PhotoSG.wait, F.text)
async def on_photo_text(message: Message, state: FSMContext):
    if await ui.try_menu(message, state):
        return
    if await ui.try_command(message, state):
        return
    if await ui.is_cancel(message):
        await state.clear()
        await message.answer("Отменено 👌", reply_markup=ui.menu_kb())
        return
    await message.answer("Жду фото 📷 Или нажми «❌ Отмена»")


async def _add(cb: CallbackQuery, item: dict):
    db.add_food(cb.from_user.id, item["name"], item["grams"],
                item["p"], item["f"], item["c"], item["k"])


@router.callback_query(F.data.startswith("padd:"))
async def on_add_one(cb: CallbackQuery, state: FSMContext):
    items = (await state.get_data()).get("photo_items") or []
    i = int(cb.data.split(":")[1])
    if i >= len(items):
        return await cb.answer("Данные устарели")
    await _add(cb, items[i])
    await cb.answer(f"➕ {items[i]['name']} — добавлено!")


@router.callback_query(F.data == "pall")
async def on_add_all(cb: CallbackQuery, state: FSMContext):
    items = (await state.get_data()).get("photo_items") or []
    if not items:
        return await cb.answer("Данные устарели")
    for it in items:
        await _add(cb, it)
    await state.clear()
    text = ("✅ <b>Всё добавлено в дневник!</b>\n"
            "Открой «📊 Дневник», посмотри прогресс 🎯")
    react = pet.reaction(cb.from_user.id)
    if react:
        text += "\n\n" + react
    await cb.message.edit_text(text)
    await cb.answer("Готово ✅")


@router.callback_query(F.data == "pcancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Отменено 👌")
    await cb.answer()
