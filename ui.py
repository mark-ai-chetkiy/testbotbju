from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MENU = {
    "👤 Профиль": "profile",
    "🔍 Продукт": "food",
    "📷 Фото еды": "photo",
    "📖 Рецепты": "recipes",
    "📊 Дневник": "today",
    "🐣 Питомец": "pet",
    "ℹ️ Помощь": "help",
    "⚙️ Сброс": "reset",
}


def menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        ["👤 Профиль", "🔍 Продукт", "📷 Фото еды"],
        ["📖 Рецепты", "📊 Дневник", "🐣 Питомец"],
        ["ℹ️ Помощь", "⚙️ Сброс"],
    ]
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
    )


async def try_menu(message, state: FSMContext) -> bool:
    """Если нажата кнопка главного меню — запускает нужный сценарий."""
    text = message.text or ""
    if text not in MENU:
        return False
    await state.clear()
    await dispatch(MENU[text], message, state)
    return True


async def is_cancel(message) -> bool:
    return (message.text or "") == "❌ Отмена"


async def try_command(message, state) -> bool:
    """Выполняет /команду, даже если пользователь в середине сценария."""
    text = (message.text or "").strip()
    if not text.startswith("/"):
        return False
    from handlers import start, profile, food, photo, recipes, diary, pet  # локальный импорт
    parts = text[1:].split()
    cmd = parts[0].split("@")[0].lower()
    args = " ".join(parts[1:])
    await state.clear()
    actions = {
        "start": lambda: start.cmd_start(message, state),
        "help": lambda: start.cmd_help(message, state),
        "profile": lambda: profile.cmd_profile(message, state),
        "norma": lambda: profile.cmd_norma(message, state),
        "food": lambda: food.cmd_food(message, state, args),
        "photo": lambda: photo.cmd_photo(message, state),
        "recipes": lambda: recipes.cmd_recipes(message, state),
        "today": lambda: diary.cmd_today(message, state),
        "reset": lambda: diary.cmd_reset(message, state),
        "pet": lambda: pet.cmd_pet(message, state),
    }
    if cmd in actions:
        await actions[cmd]()
        return True
    return False


async def dispatch(key: str, message, state: FSMContext):
    from handlers import start, profile, food, photo, recipes, diary, pet  # локальный импорт
    actions = {
        "profile": profile.cmd_profile,
        "food": food.cmd_food,
        "photo": photo.cmd_photo,
        "recipes": recipes.cmd_recipes,
        "today": diary.cmd_today,
        "pet": pet.cmd_pet,
        "help": start.cmd_help,
        "reset": diary.cmd_reset,
    }
    await actions[key](message, state)
