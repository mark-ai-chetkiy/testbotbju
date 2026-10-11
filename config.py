import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
PORT = int(os.getenv("PORT", "8000"))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "bju.db"))

PRODUCTS_PATH = os.path.join(BASE_DIR, "data", "products.json")
RECIPES_PATH = os.path.join(BASE_DIR, "data", "recipes.json")
