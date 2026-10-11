"""Единый визуальный стиль бота: карточки, таблицы, прогресс-бары (HTML)."""
from html import escape

from nutrition import ACTIVITY, GOALS, fmt


def esc(x) -> str:
    return escape(str(x))


def bar(done: float, total: float, width: int = 10) -> str:
    ratio = 0.0
    if total and total > 0:
        ratio = max(0.0, min(done / total, 1.0))
    filled = round(ratio * width)
    return "🟩" * filled + "⬜" * (width - filled)


def _macros(p, f, c) -> str:
    return f"🥩 <b>{fmt(p)}</b>  ·  🧈 <b>{fmt(f)}</b>  ·  🍚 <b>{fmt(c)}</b>"


def welcome() -> str:
    return (
        "🥗 <b>Привет! Я твой БЖУ-бот</b>\n"
        "Считаю калории и БЖУ, веду дневник и распознаю еду по фото.\n"
        "<i>Бесплатно. Без рекламы. Без регистрации.</i>\n\n"
        "🔥 <b>Что я умею</b>\n"
        "👤 <b>Профиль</b> — личная норма калорий и БЖУ\n"
        "🔍 <b>Продукт</b> — напиши «гречка 150»\n"
        "📷 <b>Фото еды</b> — посчитаю блюдо по снимку\n"
        "📖 <b>Рецепты</b> — с уже готовым БЖУ\n"
        "📊 <b>Дневник</b> — сколько съел и осталось на день\n"
        "🐣 <b>Питомец</b> — расти тамагочи, ведя дневник\n\n"
        "Начни с кнопки <b>«👤 Профиль»</b> — рассчитаю твою норму 🔥"
    )


def help_text() -> str:
    return (
        "🤖 <b>Как со мной работать</b>\n\n"
        "👤 <b>Профиль</b> — рассчитаю норму калорий и БЖУ\n"
        "🔍 <b>Продукт</b> — пришли «название + граммы», например:\n"
        "    <code>гречка 150</code>  ·  <code>куриная грудка 200</code>\n"
        "📷 <b>Фото еды</b> — отправь фото тарелки, посчитаю калории\n"
        "📖 <b>Рецепты</b> — 35 блюд с БЖУ на порцию\n"
        "📊 <b>Дневник</b> — съеденное за день и остаток до нормы\n"
        "🐣 <b>Питомец</b> — тамагочи, который растёт от твоего дневника\n"
        "⚙️ <b>Сброс</b> — очистить дневник за сегодня\n\n"
        "⌨️ Команды: /profile · /food · /photo · /recipes · /today · /pet · /norma · /help"
    )


def food_card(item: dict) -> str:
    return (
        f"🍽 <b>{esc(item['name'].capitalize())}</b>\n"
        f"Порция: <b>{fmt(item['grams'])} г</b>\n"
        "➖➖➖➖➖➖➖➖\n"
        f"🔥 Калории: <b>{fmt(item['k'])} ккал</b>\n"
        f"🥩 Белки: <b>{fmt(item['p'])} г</b>\n"
        f"🧈 Жиры: <b>{fmt(item['f'])} г</b>\n"
        f"🍚 Углеводы: <b>{fmt(item['c'])} г</b>"
    )


def search_result(matches, grams) -> str:
    return (
        "🔎 <b>Нашёл несколько вариантов</b>\n"
        "Выбери подходящий 👇"
    )


def photo_card(items: list[dict]) -> str:
    total = {"p": 0.0, "f": 0.0, "c": 0.0, "k": 0.0}
    lines = ["📷 <b>Что я увидел на фото</b>\n"]
    for i, it in enumerate(items, 1):
        for key in total:
            total[key] += it.get(key, 0) or 0
        lines.append(
            f"{i}. <b>{esc(it['name'].capitalize())}</b> — {fmt(it['grams'])} г\n"
            f"    🔥 {fmt(it['k'])} ккал  ·  {_macros(it['p'], it['f'], it['c'])}"
        )
    lines.append("\n➖➖➖➖➖➖➖➖")
    lines.append(
        f"<b>ИТОГО:</b> 🔥 <b>{fmt(total['k'])} ккал</b>\n"
        f"Белки {fmt(total['p'])} · Жиры {fmt(total['f'])} · Углеводы {fmt(total['c'])}"
    )
    lines.append("\nЧто добавить в дневник? 👇")
    return "\n".join(lines)


def norm_card(profile: dict, t: dict) -> str:
    gender = "мужчина" if profile["gender"] == "m" else "женщина"
    goal = GOALS.get(profile["goal"], ("—", 0, 0, 0))[0]
    act = ACTIVITY.get(profile["activity"], ("—", 0))[0]
    return (
        "📐 <b>Твоя норма на день</b>\n\n"
        f"🔥 Калории: <b>{t['calories']} ккал</b>\n"
        f"🥩 Белки: <b>{t['protein']} г</b>\n"
        f"🧈 Жиры: <b>{t['fat']} г</b>\n"
        f"🍚 Углеводы: <b>{t['carbs']} г</b>\n"
        "➖➖➖➖➖➖➖➖\n"
        f"👤 {gender}, {fmt(profile['age'])} лет · {fmt(profile['height'])} см · "
        f"{fmt(profile['weight'])} кг\n"
        f"{act}\n"
        f"{goal}\n"
        f"⚙️ Базовый обмен: {t['bmr']} ккал · с нагрузкой: {t['tdee']} ккал\n\n"
        "Открой <b>«📊 Дневник»</b> — покажу, сколько ещё можно съесть 😉"
    )


def diary_card(rows: list[dict], t: dict, targets: dict | None) -> str:
    lines = ["📊 <b>Дневник за сегодня</b>", "➖➖➖➖➖➖➖➖"]
    for r in rows:
        g = f" · {fmt(r['grams'])} г" if r["grams"] else ""
        lines.append(
            f"• {esc(r['name'].capitalize())}{g} — <b>{fmt(r['calories'])} ккал</b>"
        )
    lines.append("➖➖➖➖➖➖➖➖")
    if targets:
        lines.append(f"🔥 Калории   {bar(t['calories'], targets['calories'])} "
                     f"<b>{fmt(t['calories'])}</b> / {targets['calories']}")
        lines.append(f"🥩 Белки    {bar(t['protein'], targets['protein'])} "
                     f"<b>{fmt(t['protein'])}</b> / {targets['protein']} г")
        lines.append(f"🧈 Жиры     {bar(t['fat'], targets['fat'])} "
                     f"<b>{fmt(t['fat'])}</b> / {targets['fat']} г")
        lines.append(f"🍚 Углеводы {bar(t['carbs'], targets['carbs'])} "
                     f"<b>{fmt(t['carbs'])}</b> / {targets['carbs']} г")
        rest = targets["calories"] - t["calories"]
        lines.append("")
        if rest > 0:
            lines.append(f"Осталось на день: <b>{fmt(rest)} ккал</b> — можно ещё 🎉")
        elif rest > -1:
            lines.append("Ты ровно в норме ✅")
        else:
            lines.append(f"⚠️ Превышение на <b>{fmt(-rest)} ккал</b>")
    else:
        lines.append(f"🔥 Итого: <b>{fmt(t['calories'])} ккал</b> · "
                     f"{_macros(t['protein'], t['fat'], t['carbs'])}\n")
        lines.append("Заполни «👤 Профиль», чтобы видеть свою норму и прогресс.")
    return "\n".join(lines)


def recipe_card(r: dict) -> str:
    return (
        f"🍽 <b>{esc(r['n'])}</b>\n"
        f"Порций: <b>{r.get('s', 1)}</b>\n\n"
        "На одну порцию:\n"
        f"🔥 <b>{fmt(r['k'])} ккал</b>  ·  {_macros(r['p'], r['f'], r['c'])}\n"
        "➖➖➖➖➖➖➖➖\n"
        f"<i>{esc(r.get('d', ''))}</i>"
    )


def recipe_list(n: int) -> str:
    return (
        f"📖 <b>Рецепты с БЖУ</b> — {n} шт.\n"
        "Выбери блюдо, покажу состав на порцию 👇"
    )


def pet_intro() -> str:
    return (
        "🐣 <b>Знакомься — твой фитнес-тамагочи!</b>\n\n"
        "Он растёт, когда ты ведёшь дневник:\n"
        "• 🍽 записываешь еду — капает опыт;\n"
        "• 🎯 попадаешь в норму калорий и белка — большой бонус;\n"
        "• 🔥 ведёшь дневник несколько дней подряд — стрик;\n"
        "• 🥚→🐣→🐥→🐔→🦅→🐲 — эволюция за уровни.\n\n"
        "Как его зовут? Напиши имя одним сообщением 👇"
    )


def pet_card(name: str, s: dict) -> str:
    import pet as pet_mod

    lines = [f"{s['emoji']} <b>{esc(name)}</b> · ур. {s['level']} "
             f"<i>({s['title']})</i>",
             f"{bar(s['xp_into'], s['xp_need'])} "
             f"<b>{s['xp_into']}</b> / {s['xp_need']} XP",
             "",
             f"{s['mood'][0]} <i>{esc(s['mood'][1])}</i>",
             f"🔥 Дней подряд: <b>{s['streak']}</b>  ·  "
             f"🏆 Рекорд: <b>{s['best']}</b>",
             "",
             "<b>Сегодня</b>"]
    t, target = s["today"], s["target"]
    if target:
        lines.append(f"🔥 {bar(t['calories'], target['calories'])} "
                     f"<b>{fmt(t['calories'])}</b> / {target['calories']} ккал")
        lines.append(f"🥩 {bar(t['protein'], target['protein'])} "
                     f"<b>{fmt(t['protein'])}</b> / {target['protein']} г")
    else:
        lines.append(f"🔥 Съедено: <b>{fmt(t['calories'])} ккал</b>")

    nxt = [(lvl, e) for lvl, e, _ in pet_mod.STAGES if lvl > s["level"]]
    if nxt:
        lines.append("")
        lines.append(f"<i>Следующая форма: {nxt[0][1]} на ур. {nxt[0][0]}</i>")

    lines.append("")
    lines.append("Покорми меня: напиши «гречка 150» 🍽")
    return "\n".join(lines)
