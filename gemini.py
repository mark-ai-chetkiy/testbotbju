import base64
import json
import re

import aiohttp

from config import GEMINI_API_KEY, GEMINI_MODEL

URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
       "{model}:generateContent?key={key}")

PROMPT = (
    "Ты — нутрициолог. Определи блюда и продукты на фото. "
    "Оцени вес каждой порции в граммах и посчитай БЖУ и калорийность "
    "ИМЕННО на этот вес (не на 100 г). "
    'Верни ТОЛЬКО строгий JSON-массив вида: '
    '[{"name": "название блюда", "grams": 250, "protein": 30, "fat": 15, '
    '"carbs": 40, "calories": 470}] '
    "Без пояснений, без markdown, только JSON."
)


async def recognize(image_bytes: bytes, mime: str = "image/jpeg") -> list[dict]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Не задан GEMINI_API_KEY в .env")
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inlineData": {"mimeType": mime, "data":
                    base64.b64encode(image_bytes).decode()}},
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }
    url = URL.format(model=GEMINI_MODEL, key=GEMINI_API_KEY)
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                msg = data.get("error", {}).get("message", f"HTTP {resp.status}")
                raise RuntimeError(f"Ошибка Gemini: {msg}")
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            text = "\n".join(p["text"] for p in parts if p.get("text"))
    return _parse(text)


def _parse(text: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in items:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        try:
            out.append({
                "name": str(it["name"])[:80],
                "grams": float(it.get("grams") or 100),
                "protein": float(it.get("protein") or 0),
                "fat": float(it.get("fat") or 0),
                "carbs": float(it.get("carbs") or 0),
                "calories": float(it.get("calories") or 0),
            })
        except (TypeError, ValueError):
            continue
    return out
