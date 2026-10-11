"""Геймификация: виртуальный питомец, который растёт от ведения дневника.

Ничего не храним лишнего: опыт, уровень, стрик и настроение считаются
из истории дневника на лету, поэтому состояние всегда честное.
"""
from datetime import date, timedelta

import db

# Эволюция: (минимальный уровень, эмодзи, название)
STAGES = [
    (1, "🥚", "Яйцо"),
    (3, "🐣", "Цыплёнок"),
    (5, "🐥", "Птенец"),
    (8, "🐤", "Птенец-крепыш"),
    (12, "🐔", "Взрослый"),
    (17, "🦅", "Орёл"),
    (22, "🐲", "Легенда"),
]

# Опыт за действия
XP_PER_ITEM = 5       # за каждую запись в дневнике
XP_DAY_NOPROFILE = 10  # день с едой, если профиль не заполнен
XP_CAL_HIT = 30       # калории в цель (85–115%)
XP_PROTEIN_HIT = 20   # белок ≥ 80% нормы
XP_PROTEIN_FULL = 10  # белок ≥ 100% нормы
XP_STREAK = 5         # за каждый день стрика (в конце, с потолком)
XP_STREAK_CAP = 50

DEFAULT_NAME = "Тёма"


def level_info(xp: int) -> tuple[int, int, int]:
    """Возвращает (уровень, опыт внутри уровня, сколько нужно до следующего)."""
    lvl, need, cum = 1, 100, 0
    while xp >= cum + need:
        cum += need
        lvl += 1
        need = 100 * lvl
    return lvl, xp - cum, need


def stage_for(level: int) -> tuple[str, str]:
    emoji, title = STAGES[0][1], STAGES[0][2]
    for min_lvl, e, t in STAGES:
        if level >= min_lvl:
            emoji, title = e, t
    return emoji, title


def _qualifies(tot: dict, target: dict | None) -> bool:
    if not tot or tot["calories"] <= 0:
        return False
    if not target:
        return True
    cal_ok = 0.85 * target["calories"] <= tot["calories"] <= 1.15 * target["calories"]
    prot_ok = tot["protein"] >= 0.7 * target["protein"]
    return cal_ok and prot_ok


def _group(rows: list[dict]) -> dict[str, dict]:
    days: dict[str, dict] = {}
    for r in rows:
        d = days.setdefault(r["day"], {"items": 0, **{k: 0.0 for k in
                                ("protein", "fat", "carbs", "calories")}})
        d["items"] += 1
        for k in ("protein", "fat", "carbs", "calories"):
            d[k] += r[k] or 0
    return days


def stats(user_id, target: dict | None) -> dict:
    """Считает опыт, уровень, стрик и сегодняшние показатели."""
    rows = db.all_diary(user_id)
    days = _group(rows)

    xp = 0
    for d in days.values():
        xp += XP_PER_ITEM * d["items"]
        if not target:
            xp += XP_DAY_NOPROFILE
            continue
        if 0.85 * target["calories"] <= d["calories"] <= 1.15 * target["calories"]:
            xp += XP_CAL_HIT
        if d["protein"] >= 0.8 * target["protein"]:
            xp += XP_PROTEIN_HIT
        if d["protein"] >= target["protein"] and d["calories"] <= 1.15 * target["calories"]:
            xp += XP_PROTEIN_FULL

    today = date.today()
    # текущий стрик: считаем назад от сегодня (или вчера, если сегодня ещё не закрыт)
    cur = today
    if not _qualifies(days.get(cur.isoformat(), {}), target):
        cur -= timedelta(days=1)
    streak = 0
    while cur.isoformat() in days and _qualifies(days[cur.isoformat()], target):
        streak += 1
        cur -= timedelta(days=1)

    # лучший стрик: максимальная серия подряд идущих дней
    best = 0
    run = 0
    prev = None
    for day_str in sorted(days):
        d = date.fromisoformat(day_str)
        if _qualifies(days[day_str], target):
            run = run + 1 if prev == d - timedelta(days=1) else 1
            best = max(best, run)
        else:
            run = 0
        prev = d

    xp += min(XP_STREAK * streak, XP_STREAK_CAP)

    level, into, need = level_info(xp)
    emoji, title = stage_for(level)
    tdy = days.get(today.isoformat(), {"items": 0, **{k: 0.0 for k in
                                    ("protein", "fat", "carbs", "calories")}})
    return {
        "xp": xp, "level": level, "xp_into": into, "xp_need": need,
        "emoji": emoji, "title": title,
        "streak": streak, "best": best,
        "today": tdy, "target": target,
        "mood": mood(tdy, target),
        "fed": tdy["items"] > 0,
    }


def mood(tdy: dict, target: dict | None) -> tuple[str, str]:
    """Возвращает (эмодзи, текст) настроения питомца на сегодня."""
    if tdy["items"] == 0:
        return "🥺", "Голодный — покорми меня, запиши еду!"
    if not target:
        return "🙂", "Сыт и доволен. Заполни профиль — и я начну следить за нормой!"
    ratio = tdy["calories"] / target["calories"] if target["calories"] else 1
    protein_ok = tdy["protein"] >= 0.8 * target["protein"]
    if ratio < 0.5:
        return "🥺", "Ещё мало еды — я не наелся"
    if ratio < 0.85:
        return "🙂", "Неплохо, но можно добрать калорий"
    if ratio <= 1.05 and protein_ok:
        return "😄", "Сыт, счастлив и в норме!"
    if ratio <= 1.15:
        return "😎", "Отличный день, держим курс"
    if ratio <= 1.35:
        return "😅", "Меня слегка перекормили"
    return "🤢", "Перекорм! Завтра полегче, ладно?"


def target_for(user_id) -> dict | None:
    from nutrition import calc_targets

    prof = db.get_profile(user_id)
    if not prof:
        return None
    return calc_targets(prof["gender"], prof["age"], prof["height"],
                        prof["weight"], prof["activity"], prof["goal"])


def reaction(user_id) -> str:
    """Короткая реакция питомца после записи еды."""
    p = db.get_pet(user_id)
    if not p:
        return ""
    s = stats(user_id, target_for(user_id))
    return f"{s['emoji']} <b>{p['name']}</b>: {s['mood'][1]} <i>(+{XP_PER_ITEM} XP)</i>"
