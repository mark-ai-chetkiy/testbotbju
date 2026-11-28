"""Собирает первый вертикальный ролик для TikTok: фото еды → расчёт БЖУ.

Запуск: python3 tools/make_tiktok_video.py
Нужен Pillow, imageio-ffmpeg и macOS say (голос Milena).
"""
import os
import re
import shutil
import subprocess
import tempfile

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tiktok", "01_photo_to_bju.mp4")

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
AIFF = "/tmp/tiktok_voice.aiff"
M4A = "/tmp/tiktok_voice.m4a"
VOICE = ("Сфотографировал обед и получил БЖУ без таблиц. "
         "Открыл мини-приложение, нажал рассчитать по фото. "
         "ИИ оценил порцию и посчитал белки, жиры и углеводы. "
         "Один клик, и всё уже в дневнике. Ссылка в био.")

W, H = 720, 1280
FPS = 30

GREEN = "#0e9f6e"
GREEN_DARK = "#0a2c22"
BG = "#f3f6f2"
CARD = "#ffffff"
LINE = "#e0e9e2"
TEXT = "#10231c"
MUTED = "#64756d"
SOFT = "#e8f6ef"
ACCENT_SOFT = "#d9f3e6"

F_REG = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
F_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
font = lambda size, bold=False: ImageFont.truetype(F_BOLD if bold else F_REG, size)


def gradient(top: str, bottom: str) -> Image.Image:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    a = tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(bottom[i:i + 2], 16) for i in (1, 3, 5))
    for y in range(H):
        k = y / (H - 1)
        c = tuple(round(a[i] * (1 - k) + b[i] * k) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


BG_HOOK = gradient("#0d3529", GREEN_DARK)
BG_CTA = gradient(GREEN, "#077353")


def center_text(d, y, text, f, fill, x=W // 2):
    d.text((x, y), text, font=f, fill=fill, anchor="mm")


def rounded(d, box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(d, x, y, text, f, fill=SOFT, color=GREEN, pad_x=18, pad_y=9):
    box = d.textbbox((0, 0), text, font=f)
    w = box[2] - box[0] + pad_x * 2
    h = box[3] - box[1] + pad_y * 2
    rounded(d, (x, y, x + w, y + h), h // 2, fill)
    d.text((x + pad_x, y + pad_y - box[1]), text, font=f, fill=color)
    return w


def plate(d, cx, cy, r, scale=1.0):
    r = int(r * scale)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#ffffff", outline="#cfdbd3", width=4)
    d.ellipse((cx - r + 26, cy - r + 26, cx + r - 26, cy + r - 26), fill="#f6e6bf")
    d.ellipse((cx - r + 70, cy - r + 70, cx + r - 70, cy + r - 70), fill="#fff8e6")
    d.ellipse((cx + 18, cy - 8, cx + r - 34, cy + r - 60), fill="#6fa832")


def phone(img, caption=None):
    d = ImageDraw.Draw(img)
    if caption:
        center_text(d, 92, caption, font(20, True), GREEN)
    rounded(d, (98, 186, 638, 1046), 44, "#d5e1d9")
    rounded(d, (88, 170, 628, 1030), 44, CARD, LINE, 2)
    rounded(d, (88, 170, 628, 306), 44, GREEN)
    d.rectangle((88, 214, 628, 306), fill=GREEN)
    center_text(d, 222, "БЖУ и Зал", font(34, True), "#ffffff")
    center_text(d, 272, "БЖУ · дневник · тренировки", font(17), "#d6f2e6")
    return d


def progress_bar(d, x, y, w, h, pct, fill=GREEN, bg=LINE):
    rounded(d, (x, y, x + w, y + h), h // 2, bg)
    if pct > 0:
        rounded(d, (x, y, x + max(h, int(w * min(1, pct))), y + h), h // 2, fill)


def hook(p, t):
    img = BG_HOOK.copy()
    d = ImageDraw.Draw(img)
    plate(d, 360, 880, 180, 1 + 0.02 * (p - 0.5))
    center_text(d, 250, "Сфотографировал", font(52, True), "#ffffff")
    center_text(d, 330, "обед —", font(52, True), "#ffffff")
    center_text(d, 420, "получил БЖУ", font(58, True), "#8ce9c2")
    center_text(d, 530, "Без таблиц и ручного счёта", font(26), "#d6f2e6")
    pill(d, 290, 610, "ФОТО → БЖУ ЗА 10 СЕК", font(20, True), "#ffffff", GREEN_DARK, 22, 12)
    center_text(d, 1180, "Смотри до конца", font(22), "#bfe2d1")
    return img


def step_photo(p, t):
    img = Image.new("RGB", (W, H), BG)
    d = phone(img, "ШАГ 1 · ФОТО ТАРЕЛКИ")
    rounded(d, (120, 350, 596, 590), 24, CARD, LINE, 2)
    d.text((148, 382), "Найти продукт", font=font(22, True), fill=TEXT)
    rounded(d, (148, 430, 568, 496), 14, BG, LINE, 1)
    d.text((168, 452), "гречка, курица, творог", font=font(19), fill=MUTED)
    pulse = 1 + 0.015 * __import__("math").sin(t * 9)
    x0, x1 = 148, 568
    cx = (x0 + x1) / 2
    w = int((x1 - x0) * pulse)
    rounded(d, (cx - w / 2, 510, cx + w / 2, 580), 16, GREEN)
    center_text(d, 545, "Рассчитать по фото", font(22, True), "#ffffff", int(cx))
    plate(d, 358, 800, 150)
    center_text(d, 990, "Тарелка выбрана", font(24, True), TEXT)
    return img


def step_loading(p, t):
    img = Image.new("RGB", (W, H), BG)
    d = phone(img, "ШАГ 2 · ИИ СЧИТАЕТ")
    rounded(d, (120, 350, 596, 730), 24, CARD, LINE, 2)
    import math
    a0 = int(t * 420) % 360
    d.arc((298, 420, 418, 540), start=a0, end=a0 + 280, fill=GREEN, width=12)
    center_text(d, 600, "Анализирую фото…", font(28, True), TEXT)
    progress_bar(d, 160, 660, 396, 16, min(1, p * 1.05))
    center_text(d, 712, "Оценка порции и БЖУ", font(20), MUTED)
    return img


def step_result(p, t):
    img = Image.new("RGB", (W, H), BG)
    d = phone(img, "ШАГ 3 · ГОТОВЫЙ БЖУ")
    rounded(d, (120, 336, 596, 900), 24, CARD, LINE, 2)
    d.text((150, 370), "Что увидел ИИ", font=font(28, True), fill=TEXT)
    d.text((150, 420), "Проверь порции — ИИ может ошибаться", font=font(17), fill=MUTED)
    d.line((150, 462, 566, 462), fill=LINE, width=2)
    d.text((150, 492), "Яйцо вареное с зеленью", font=font(25, True), fill=TEXT)
    d.text((150, 536), "60 г · ИИ-оценка порции", font=font(19), fill=MUTED)
    pill(d, 150, 590, "Б 7,8 г", font(21, True))
    pill(d, 320, 590, "Ж 6 г", font(21, True))
    pill(d, 150, 654, "У 0,5 г", font(21, True))
    pill(d, 320, 654, "88 ккал", font(21, True), GREEN, "#ffffff")
    btn_fill = GREEN if p < 0.75 else "#0b8a60"
    rounded(d, (150, 740, 566, 818), 18, btn_fill)
    center_text(d, 779, "Добавить всё в дневник", font(22, True), "#ffffff")
    center_text(d, 960, "Всё посчитано автоматически", font(24), GREEN)
    return img


def step_diary(p, t):
    img = Image.new("RGB", (W, H), BG)
    d = phone(img, "ШАГ 4 · УЖЕ В ДНЕВНИКЕ")
    rounded(d, (120, 340, 596, 850), 24, CARD, LINE, 2)
    d.text((150, 374), "Сегодня", font=font(22, True), fill=MUTED)
    d.text((150, 418), "88 ккал", font=font(52, True), fill=TEXT)
    progress_bar(d, 150, 510, 416, 18, 0.18)
    d.line((150, 570, 566, 570), fill=LINE, width=2)
    d.text((150, 600), "Яйцо вареное с зеленью", font=font(24, True), fill=TEXT)
    d.text((150, 644), "60 г · Б 7,8 / Ж 6 / У 0,5", font=font(19), fill=MUTED)
    rounded(d, (150, 706, 566, 784), 18, ACCENT_SOFT)
    center_text(d, 745, "Добавлено в дневник", font(23, True), GREEN)
    center_text(d, 918, "Серия: 1 день · Завтра продолжим", font(22), MUTED)
    return img


def cta(p, t):
    img = BG_CTA.copy()
    d = ImageDraw.Draw(img)
    plate(d, 360, 260, 120)
    center_text(d, 500, "Открой мини-приложение", font(44, True), "#ffffff")
    center_text(d, 590, "и считай БЖУ по фото", font(34), "#d7f6e9")
    rounded(d, (160, 700, 560, 800), 26, "#ffffff")
    center_text(d, 750, "Ссылка в био", font(38, True), GREEN_DARK)
    d.line((360, 830, 360, 910), fill="#ffffff", width=10)
    d.polygon([(320, 890), (400, 890), (360, 940)], fill="#ffffff")
    center_text(d, 1030, "@GymTamagotchi_bot", font(24), "#d7f6e9")
    center_text(d, 1110, "БЖУ и Зал", font(26, True), "#ffffff")
    return img


SEGMENTS = [
    (0.0, 2.2, hook),
    (2.2, 4.8, step_photo),
    (4.8, 7.5, step_loading),
    (7.5, 11.3, step_result),
    (11.3, 13.0, step_diary),
    (13.0, None, cta),
]

FADE = 0.35


def render_frame(t, duration):
    segs = [(a, b if b is not None else duration, f) for a, b, f in SEGMENTS]
    for i, (start, end, fn) in enumerate(segs):
        if t <= end or i == len(segs) - 1:
            p = max(0, min(1, (t - start) / (end - start)))
            img = fn(p, t)
            if i > 0 and t - start < FADE:
                prev = segs[i - 1][2](1.0, start)
                img = Image.blend(prev, img, (t - start) / FADE)
            elif i < len(segs) - 1 and end - t < FADE:
                nxt = segs[i + 1][2](0.0, end)
                img = Image.blend(img, nxt, 1 - (end - t) / FADE)
            return img
    return segs[-1][2](1.0, t)


def prepare_audio() -> float:
    if not os.path.exists(M4A):
        subprocess.run(["say", "-v", "Milena", "-r", "165", "-o", AIFF, VOICE], check=True)
        subprocess.run([FFMPEG, "-y", "-i", AIFF, "-c:a", "aac", "-b:a", "128k", M4A],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = subprocess.run([FFMPEG, "-i", M4A], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        raise RuntimeError("Не удалось определить длительность аудио")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    duration = prepare_audio()
    tmp = tempfile.mkdtemp(prefix="tiktok_frames_")
    try:
        total = int(duration * FPS)
        for n in range(total):
            t = n / FPS
            frame = render_frame(t, duration)
            frame.save(os.path.join(tmp, f"f{n:05d}.png"))
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        subprocess.run([
            FFMPEG, "-y", "-framerate", str(FPS),
            "-i", os.path.join(tmp, "f%05d.png"),
            "-i", M4A,
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            "-movflags", "+faststart", OUT,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Готово: {OUT} ({duration:.1f} с)")


if __name__ == "__main__":
    main()
