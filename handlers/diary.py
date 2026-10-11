from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
import render
import ui
from nutrition import calc_targets

router = Router()


async def cmd_today(message: Message, state: FSMContext):
    await state.clear()
    rows = db.get_today(message.from_user.id)
    if not rows:
        return await message.answer(
            "📊 <b>На сегодня пока пусто</b>\n\n"
            "Добавь еду одним из способов:\n"
            "🔍 напиши «гречка 150»\n"
            "📷 пришли фото блюда\n"
            "📖 выбери рецепт",
            reply_markup=ui.menu_kb())

    t = db.totals(rows)
    prof = db.get_profile(message.from_user.id)
    targets = None
    if prof:
        targets = calc_targets(prof["gender"], prof["age"], prof["height"],
                               prof["weight"], prof["activity"], prof["goal"])
    await message.answer(render.diary_card(rows, t, targets), reply_markup=ui.menu_kb())


@router.message(Command("today"))
async def cmd_today_cmd(message: Message, state: FSMContext):
    await cmd_today(message, state)


async def cmd_reset(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, очистить день", callback_data="resyes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="resno")],
    ])
    await message.answer("Очистить дневник за сегодня?", reply_markup=kb)


@router.message(Command("reset"))
async def cmd_reset_cmd(message: Message, state: FSMContext):
    await state.clear()
    await cmd_reset(message, state)


@router.callback_query(F.data == "resyes")
async def on_reset_yes(cb: CallbackQuery, state: FSMContext):
    db.clear_today(cb.from_user.id)
    await cb.message.edit_text("🗑 Дневник за сегодня очищен.")
    await cb.answer("Готово ✅")


@router.callback_query(F.data == "resno")
async def on_reset_no(cb: CallbackQuery):
    await cb.message.edit_text("Отменил 👌")
    await cb.answer()
