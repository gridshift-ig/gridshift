"""Render a 1080x1080 branded Instagram headline card with Pillow.

Copyright-safe by default: brand gradient + headline text. If a story has an
APPROVED local background photo (story['bg_image']) it is used with a dark
overlay. Never auto-downloads publisher photos.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1080

BRAND = {
    "bg_top": (16, 18, 24),
    "bg_bottom": (32, 36, 48),
    "accent": (227, 30, 36),
    "accent_ev": (0, 200, 140),
    "accent_wagon": (240, 176, 48),
    "text": (255, 255, 255),
    "muted": (170, 176, 188),
    "name": "GRIDSHIFT",
}

_FONT_CANDIDATES = {
    "bold": ["/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"],
    "semibold": ["/usr/share/fonts/truetype/google-fonts/Poppins-SemiBold.ttf",
                 "/usr/share/fonts/truetype/lato/Lato-Semibold.ttf",
                 "C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "regular": ["/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
                "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
                "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"],
}


def _font(kind, size):
    for path in _FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient(top, bottom):
    base = Image.new("RGB", (SIZE, SIZE), top)
    grad = Image.new("L", (1, SIZE))
    for y in range(SIZE):
        grad.putpixel((0, y), int(255 * y / SIZE))
    grad = grad.resize((SIZE, SIZE))
    return Image.composite(Image.new("RGB", (SIZE, SIZE), bottom), base, grad)


def _photo_background(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((SIZE, SIZE))
    overlay = Image.new("L", (1, SIZE))
    for y in range(SIZE):
        overlay.putpixel((0, y), int(235 * (y / SIZE) ** 1.4))
    overlay = overlay.resize((SIZE, SIZE))
    return Image.composite(Image.new("RGB", (SIZE, SIZE), (8, 9, 12)), img, overlay)


def _fit_headline(draw, text, kind, max_width, start_size, min_size):
    for size in range(start_size, min_size - 1, -4):
        font = _font(kind, size)
        avg = draw.textlength("ABCDEFGHIJ abcdefghij", font=font) / 21
        wrap = max(8, int(max_width / avg))
        lines = textwrap.wrap(text, width=wrap)
        if len(lines) <= 5:
            widest = max((draw.textlength(ln, font=font) for ln in lines), default=0)
            if widest <= max_width:
                return font, lines, size
    return _font(kind, min_size), textwrap.wrap(text, width=22)[:6], min_size


def render_card(story, out_path, brand=None):
    b = {**BRAND, **(brand or {})}
    is_ev = bool(story.get("ev_performance"))
    is_wagon = bool(story.get("wagon")) and not is_ev
    accent = b["accent_ev"] if is_ev else (b["accent_wagon"] if is_wagon else b["accent"])

    if story.get("bg_image") and Path(story["bg_image"]).exists():
        canvas = _photo_background(story["bg_image"])
    else:
        canvas = _gradient(b["bg_top"], b["bg_bottom"])
    d = ImageDraw.Draw(canvas)
    M = 80

    d.rectangle([0, 0, SIZE, 12], fill=accent)
    d.text((M, 64), b["name"], font=_font("bold", 46), fill=b["text"])
    d.text((M, 122), "DAILY CAR NEWS - REVIEWS - EV PERFORMANCE - WAGONS",
           font=_font("semibold", 20), fill=b["muted"])

    src = story["source"].upper()
    bf = _font("semibold", 26)
    tw = d.textlength(src, font=bf)
    bx0 = SIZE - M - tw - 36
    d.rounded_rectangle([bx0, 70, SIZE - M, 116], radius=23, fill=accent)
    d.text((bx0 + 18, 78), src, font=bf, fill=(255, 255, 255))

    headline_top = 360
    if is_ev:
        rib = "EV PERFORMANCE"
        rf = _font("bold", 28)
        rw = d.textlength(rib, font=rf)
        d.rounded_rectangle([M, 300, M + rw + 76, 352], radius=26, fill=accent)
        bx, by = M + 26, 312
        d.polygon([(bx + 9, by), (bx - 3, by + 20), (bx + 6, by + 20),
                   (bx + 1, by + 32), (bx + 16, by + 11), (bx + 7, by + 11)], fill=(8, 9, 12))
        d.text((M + 48, 308), rib, font=rf, fill=(8, 9, 12))
        headline_top = 380
    elif is_wagon:
        rib = "WAGON WATCH"
        rf = _font("bold", 28)
        rw = d.textlength(rib, font=rf)
        d.rounded_rectangle([M, 300, M + rw + 44, 352], radius=26, fill=accent)
        d.text((M + 22, 308), rib, font=rf, fill=(8, 9, 12))
        headline_top = 380

    box_w = SIZE - 2 * M
    font, lines, size = _fit_headline(d, story["title"], "bold", box_w, 78, 42)
    line_h = int(size * 1.16)
    y = max(headline_top, SIZE - 300 - line_h * len(lines))
    for ln in lines:
        d.text((M, y), ln, font=font, fill=b["text"])
        y += line_h

    d.rectangle([M, SIZE - 150, M + 90, SIZE - 144], fill=accent)
    d.text((M, SIZE - 128), story.get("footer", "Full story - link in bio"),
           font=_font("semibold", 30), fill=b["text"])
    d.text((M, SIZE - 86), "Summary only - original article & photos belong to the source",
           font=_font("regular", 20), fill=b["muted"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=90)
    return out_path
