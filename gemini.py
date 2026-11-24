import base64
import json
import logging
import re

import aiohttp

from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger("gemini")

URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
       "{model}:generateContent?key={key}")

# Если основная модель перегружена или недоступна, пробуем запасные.
FALLBACK_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash-lite",
    "gemini-3.5-pro",
    "gemini-3.8-pro",
)

PROMPT = (
    "Ты — нутрициолог. Определи блюда и продукты на фото. "
    "Оцени вес каждой порции в граммах и посчитай БЖУ и калорийность "
    "ИМЕННО на этот вес (не на 100 г). "
    'Верни ТОЛЬКО строгий JSON-массив вида: '
    '[{"name": "название блюда", "grams": 250, "protein": 30, "fat": 15, '
    '"carbs": 40, "calories": 470}] '
    "Без пояснений, без markdown, только JSON."
)


async def probe_models() -> list[dict]:
    """Временная диагностика: какие модели доступны для этого ключа."""
    payload = {
        "contents": [{"parts": [{"text": "Ответь одним словом: OK"}]}],
        "generationConfig": {"maxOutputTokens": 10},
    }
    models = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]
    timeout = aiohttp.ClientTimeout(total=30)
    out = []
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in models:
            try:
                items = await _generate(session, model, payload)
                out.append({"model": model, "ok": True, "answer": items[:1]})
            except Exception as exc:
                out.append({"model": model, "ok": False,
                            "error": str(exc)[:180]})
    return out


async def _generate(session: aiohttp.ClientSession, model: str,
                    payload: dict) -> list[dict]:
    url = URL.format(model=model, key=GEMINI_API_KEY)
    async with session.post(url, json=payload) as resp:
        data = await resp.json()
        if resp.status != 200:
            msg = data.get("error", {}).get("message", f"HTTP {resp.status}")
            raise RuntimeError(str(msg)[:200])
        parts = data["candidates"][0].get("content", {}).get("parts", [])
        text = "\n".join(p["text"] for p in parts if p.get("text"))
    return _parse(text)


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
    models = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]
    timeout = aiohttp.ClientTimeout(total=90)
    last_error = "неизвестная ошибка"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model in models:
            try:
                items = await _generate(session, model, payload)
                if items:
                    if model != GEMINI_MODEL:
                        log.info("Фото распознано моделью %s", model)
                    return items
                last_error = "модель вернула пустой результат"
            except Exception as exc:
                last_error = str(exc)
            log.warning("Модель %s не сработала: %s", model, last_error)
    raise RuntimeError("Сервис распознавания временно недоступен: " + last_error)


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
