import json
import re
from functools import lru_cache

from config import PRODUCTS_PATH, RECIPES_PATH

ACTIVITY = {
    1: ("🪑 Минимальная (сидячая работа)", 1.20),
    2: ("🚶 Лёгкая (1–3 тренировки в неделю)", 1.375),
    3: ("🏃 Средняя (3–5 тренировок в неделю)", 1.55),
    4: ("🏋️ Высокая (6–7 тренировок в неделю)", 1.725),
    5: ("🔥 Очень высокая (тяжёлая работа + тренировки)", 1.90),
}

GOALS = {
    "lose": ("🔥 Похудение", 0.82, 2.0, 0.25),
    "keep": ("⚖️ Поддержка", 1.00, 1.6, 0.28),
    "gain": ("💪 Набор массы", 1.12, 1.8, 0.30),
}


@lru_cache(maxsize=1)
def load_products() -> tuple:
    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


@lru_cache(maxsize=1)
def load_recipes() -> tuple:
    with open(RECIPES_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


def norm(s: str) -> str:
    return s.lower().replace("ё", "е").strip()


def calc_targets(gender: str, age: int, height: float, weight: float,
                 activity: int, goal: str) -> dict:
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "m" else -161)
    tdee = bmr * ACTIVITY[activity][1]
    _, coef, protein_per_kg, fat_ratio = GOALS[goal]
    calories = round(tdee * coef)
    protein = round(weight * protein_per_kg)
    fat = round(calories * fat_ratio / 9)
    carbs = round((calories - protein * 4 - fat * 9) / 4)
    carbs = max(carbs, 30)
    return {
        "bmr": round(bmr), "tdee": round(tdee),
        "calories": calories, "protein": protein, "fat": fat, "carbs": carbs,
    }


def search_products(query: str, limit: int = 8) -> list[tuple[int, dict]]:
    products = load_products()
    q = norm(query)
    toks = [t for t in re.split(r"[^a-zа-я0-9]+", q) if t and not t.isdigit()]
    if not q:
        return []
    exact, partial = [], []
    for i, p in enumerate(products):
        n = norm(p["n"])
        if q == n:
            exact.append((i, p))
            continue
        if q in n or (len(n) >= 4 and n in q):
            partial.append((i, p, len(n)))
            continue
        if toks and all(
            len(t) <= 2 or t in n or (len(t) >= 5 and n.startswith(t[:5]))
            for t in toks
        ):
            partial.append((i, p, len(n)))
    partial.sort(key=lambda x: x[2])
    return exact + [(i, p) for i, p, _ in partial[:limit]]


def best_db_match(name: str) -> dict | None:
    n = norm(name)
    for p in load_products():
        pn = norm(p["n"])
        if n == pn:
            return p
        # совпадение должно покрывать бо́льшую часть названия,
        # иначе «майонез» совпал бы с «салатом с майонезом»
        if pn in n and len(pn) >= max(5, int(0.5 * len(n))):
            return p
        if len(pn) >= 8 and n.startswith(pn):
            return p
    return None


def scale(prod: dict, grams: float) -> dict:
    k = grams / 100.0
    return {
        "p": prod["p"] * k,
        "f": prod["f"] * k,
        "c": prod["c"] * k,
        "k": prod["k"] * k,
    }


def portion(name: str, grams: float, p: float, f: float, c: float, k: float) -> dict:
    return {"name": name, "grams": grams, "p": p, "f": f, "c": c, "k": k}


def fmt(x) -> str:
    x = float(x)
    if abs(x - round(x)) < 0.05:
        return str(int(round(x)))
    return f"{x:.1f}".replace(".", ",")
