import re

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

import db
import render
import ui
from nutrition import ACTIVITY, calc_targets

router = Router()


class ProfileSG(StatesGroup):
    gender = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    goal = State()


def _kb(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True,
                               keyboard=[[KeyboardButton(text=t) for t in r] for r in rows])


def _num(text: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", text or "")
    return float(m.group(0).replace(",", ".")) if m else None


def _save(user_id: int, gender: str, age: int, height: float, weight: float,
          activity: int, goal: str) -> dict:
    t = calc_targets(gender, age, height, weight, activity, goal)
    db.save_profile(user_id, gender, age, height, weight, activity, goal,
                    t["calories"], t["protein"], t["fat"], t["carbs"])
    p = db.get_profile(user_id)
    p.update(t)
    return p


async def cmd_profile(message: Message, state: FSMContext):
    if await ui.is_cancel(message):
        await state.clear()
        await message.answer("Отменено 👌", reply_markup=ui.menu_kb())
        return
    cur = await state.get_state()
    if cur is None:
        await state.set_state(ProfileSG.gender)
        return await message.answer(
            "Давай рассчитаю твою норму 💪 Укажи пол:",
            reply_markup=_kb([["Мужской", "Женский"], ["❌ Отмена"]]),
        )

    if cur == ProfileSG.gender.state:
        t = (message.text or "").strip().lower()
        if t.startswith("муж"):
            await state.update_data(gender="m")
        elif t.startswith("жен"):
            await state.update_data(gender="f")
        else:
            return await message.answer("Выбери кнопкой: Мужской или Женский")
        await state.set_state(ProfileSG.age)
        return await message.answer("Сколько тебе лет? Числом: 25")

    if cur == ProfileSG.age.state:
        v = _num(message.text or "")
        if not v or not 10 <= v <= 100:
            return await message.answer("Введи возраст числом от 10 до 100")
        await state.update_data(age=int(v))
        await state.set_state(ProfileSG.height)
        return await message.answer("Рост в см: 175")

    if cur == ProfileSG.height.state:
        v = _num(message.text or "")
        if not v or not 100 <= v <= 250:
            return await message.answer("Введи рост числом от 100 до 250 см")
        await state.update_data(height=v)
        await state.set_state(ProfileSG.weight)
        return await message.answer("Вес в кг: 70")

    if cur == ProfileSG.weight.state:
        v = _num(message.text or "")
        if not v or not 30 <= v <= 300:
            return await message.answer("Введи вес числом от 30 до 300 кг")
        await state.update_data(weight=v)
        await state.set_state(ProfileSG.activity)
        lines = [f"{k}. {v[0]}" for k, v in ACTIVITY.items()]
        return await message.answer(
            "Насколько ты активен?\n" + "\n".join(lines) + "\n\nОтветь цифрой 1–5",
            reply_markup=_kb([[str(i) for i in range(1, 6)], ["❌ Отмена"]]),
        )

    if cur == ProfileSG.activity.state:
        v = _num(message.text or "")
        if not v or int(v) not in ACTIVITY:
            return await message.answer("Выбери цифру от 1 до 5")
        await state.update_data(activity=int(v))
        await state.set_state(ProfileSG.goal)
        return await message.answer(
            "Какая цель?",
            reply_markup=_kb([["🔥 Похудение", "⚖️ Поддержка"], ["💪 Набор массы"],
                              ["❌ Отмена"]]),
        )

    if cur == ProfileSG.goal.state:
        t = (message.text or "").strip()
        g = {"🔥 Похудение": "lose", "⚖️ Поддержка": "keep",
             "💪 Набор массы": "gain"}.get(t)
        if not g:
            return await message.answer("Выбери цель кнопкой")
        await state.update_data(goal=g)
        data = await state.get_data()
        await state.clear()
        profile = _save(message.from_user.id, data["gender"], data["age"],
                        data["height"], data["weight"], data["activity"], g)
        await message.answer(render.norm_card(profile, profile),
                             reply_markup=ui.menu_kb())


@router.message(Command("profile"))
async def cmd_profile_cmd(message: Message, state: FSMContext):
    await state.clear()
    await cmd_profile(message, state)


@router.message(Command("norma"))
async def cmd_norma(message: Message, state: FSMContext):
    await state.clear()
    prof = db.get_profile(message.from_user.id)
    if not prof:
        return await message.answer("Профиль ещё не заполнен — нажми «👤 Мой профиль»")
    targets = calc_targets(prof["gender"], prof["age"], prof["height"],
                           prof["weight"], prof["activity"], prof["goal"])
    await message.answer(render.norm_card(prof, targets), reply_markup=ui.menu_kb())


@router.message(
    StateFilter(
        ProfileSG.gender, ProfileSG.age, ProfileSG.height,
        ProfileSG.weight, ProfileSG.activity, ProfileSG.goal,
    )
)
async def state_any(message: Message, state: FSMContext):
    if await ui.try_menu(message, state):
        return
    if await ui.try_command(message, state):
        return
    await cmd_profile(message, state)
