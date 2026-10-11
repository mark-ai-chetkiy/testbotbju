import sqlite3
import threading
from datetime import date

from config import DB_PATH

_lock = threading.Lock()
_conn = None


def _get():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init_db():
    with _lock:
        c = _get()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS profile (
                user_id INTEGER PRIMARY KEY,
                gender TEXT, age INTEGER, height REAL, weight REAL,
                activity INTEGER, goal TEXT,
                calories INTEGER, protein INTEGER, fat INTEGER, carbs INTEGER
            );
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                day TEXT,
                name TEXT,
                grams REAL,
                protein REAL, fat REAL, carbs REAL, calories REAL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_diary_user_day ON diary(user_id, day);
            CREATE TABLE IF NOT EXISTS pets (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        c.commit()


def upsert_user(user_id: int, username: str | None):
    with _lock:
        c = _get()
        c.execute(
            "INSERT INTO users(user_id, username) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username),
        )
        c.commit()


def save_profile(user_id, gender, age, height, weight, activity, goal, cal, p, f, c):
    with _lock:
        con = _get()
        con.execute(
            "INSERT INTO profile VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET gender=excluded.gender, age=excluded.age, "
            "height=excluded.height, weight=excluded.weight, activity=excluded.activity, "
            "goal=excluded.goal, calories=excluded.calories, protein=excluded.protein, "
            "fat=excluded.fat, carbs=excluded.carbs",
            (user_id, gender, age, height, weight, activity, goal, cal, p, f, c),
        )
        con.commit()


def get_profile(user_id) -> dict | None:
    row = _get().execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def add_food(user_id, name, grams, p, f, c, cal):
    day = date.today().isoformat()
    with _lock:
        con = _get()
        con.execute(
            "INSERT INTO diary(user_id, day, name, grams, protein, fat, carbs, calories) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (user_id, day, name, grams, p, f, c, cal),
        )
        con.commit()


def get_today(user_id) -> list[dict]:
    day = date.today().isoformat()
    rows = _get().execute(
        "SELECT name, grams, protein, fat, carbs, calories FROM diary "
        "WHERE user_id=? AND day=? ORDER BY id",
        (user_id, day),
    ).fetchall()
    return [dict(r) for r in rows]


def clear_today(user_id):
    day = date.today().isoformat()
    with _lock:
        con = _get()
        con.execute("DELETE FROM diary WHERE user_id=? AND day=?", (user_id, day))
        con.commit()


def totals(rows: list[dict]) -> dict:
    t = {"protein": 0.0, "fat": 0.0, "carbs": 0.0, "calories": 0.0}
    for r in rows:
        for k in t:
            t[k] += r[k] or 0
    return t


def today_str() -> str:
    return date.today().isoformat()


def day_totals(user_id, day: str) -> dict:
    rows = _get().execute(
        "SELECT protein, fat, carbs, calories FROM diary "
        "WHERE user_id=? AND day=?",
        (user_id, day),
    ).fetchall()
    return totals([dict(r) for r in rows])


def all_diary(user_id) -> list[dict]:
    """Все записи дневника по дням (для расчёта стрика и опыта)."""
    rows = _get().execute(
        "SELECT day, protein, fat, carbs, calories FROM diary "
        "WHERE user_id=? ORDER BY day",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_pet(user_id) -> dict | None:
    row = _get().execute("SELECT * FROM pets WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def create_pet(user_id, name: str) -> dict:
    with _lock:
        con = _get()
        con.execute("INSERT OR IGNORE INTO pets(user_id, name) VALUES(?,?)",
                    (user_id, name))
        con.commit()
    return get_pet(user_id)


def set_pet_name(user_id, name: str):
    with _lock:
        con = _get()
        con.execute("INSERT INTO pets(user_id, name) VALUES(?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name",
                    (user_id, name))
        con.commit()

