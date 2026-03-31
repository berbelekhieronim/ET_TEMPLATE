#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_placeholders.py
Generates placeholder product images for testing without real product photos.
Run once before the experiment:  python generate_placeholders.py
Replace the generated files with real product photos at any time.
"""

import os

PRODUCTS = [
    ("granola_premium",    "Baton Granolowy\nPremium",          (220, 185, 100)),
    ("date_bar",           "Baton Daktylowy\nNaturalny",         (139,  90,  43)),
    ("strawberry_yogurt",  "Jogurt Owocowy\nTruskawkowy",        (255, 160, 180)),
    ("natural_kefir",      "Kefir Naturalny\nz Witaminami",      (210, 235, 255)),
    ("choco_cereals",      "Płatki Śniadaniowe\nChoco-Stars",    ( 90,  55,  25)),
    ("oat_flakes",         "Płatki Owsiane\nGórskie",            (215, 190, 150)),
    ("protein_bar_mango",  "Batonik Proteinowy\nMango-Kokos",    (255, 170,  40)),
    ("fig_oat_bar",        "Baton Owsiany\nz Figami",            (170, 120,  70)),
    ("mango_smoothie",     "Smoothie Tropical\nPremium",         (255, 210,  50)),
    ("beet_juice",         "Sok z Kiszonych\nBuraków",           (180,  35,  75)),
    ("bbq_chips",          "Chipsy BBQ\n\"Naturalne\"",          (210, 100,  50)),
    ("corn_wafers",        "Wafle Kukurydziane\nPełnoziarniste", (255, 230, 140)),
    ("choco_cream",        "Krem Kakaowo-\nOrzechowy Premium",   ( 55,  28,   8)),
    ("almond_butter",      "Masło Migdałowe\n100% Naturalne",    (205, 165,  95)),
    ("tropical_muesli",    "Musli Tropikalne\nFit&Fun",          (255, 200, 110)),
    ("millet_instant",     "Kasza Jaglana\nBłyskawiczna",        (240, 225, 160)),
    ("fit_cookies",        "Ciastka Owsiane\n\"Zdrowe Wypieki\"", (195, 165, 125)),
    ("sesame_honey",       "Sezamki Tradycyjne\nz Miodem",       (220, 185,  75)),
    ("bio_energy",         "Drink Energetyczny\n\"Bio Nature\"", ( 45, 195,  90)),
    ("coconut_water",      "Woda Kokosowa\nNaturalna",           (215, 242, 255)),
]

IMG_W, IMG_H = 600, 400


def _try_pil(filename, label, bg_color):
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    img = Image.new("RGB", (IMG_W, IMG_H), color=bg_color)
    draw = ImageDraw.Draw(img)
    # border
    draw.rectangle([4, 4, IMG_W - 5, IMG_H - 5], outline=(80, 80, 80), width=3)
    # product icon placeholder (simple oval)
    icon_color = tuple(max(0, c - 50) for c in bg_color)
    draw.ellipse([IMG_W // 2 - 80, IMG_H // 2 - 80,
                  IMG_W // 2 + 80, IMG_H // 2 + 80],
                 fill=icon_color)
    # label text
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x = (IMG_W - tw) // 2
    text_y = IMG_H - th - 25
    draw.rectangle([text_x - 6, text_y - 4, text_x + tw + 6, text_y + th + 4],
                   fill=(255, 255, 255, 200))
    draw.text((text_x, text_y), label, font=font, fill=(30, 30, 30), align="center")
    img.save(filename)


def _try_pgm(filename, bg_color):
    """Minimal PGM fallback – grayscale, no text."""
    gray = int(0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2])
    pgm_path = filename.replace(".jpg", ".pgm")
    with open(pgm_path, "wb") as f:
        f.write(f"P5\n{IMG_W} {IMG_H}\n255\n".encode())
        f.write(bytes([gray] * (IMG_W * IMG_H)))
    print(f"  (PGM fallback – PIL not available): {pgm_path}")


def main():
    os.makedirs("images", exist_ok=True)
    pil_ok = True
    try:
        import PIL  # noqa: F401
    except ImportError:
        pil_ok = False
        print("PIL not installed – generating PGM grayscale placeholders.")
        print("Install Pillow for colour JPEGs:  pip install Pillow")

    for pid, label, color in PRODUCTS:
        path = os.path.join("images", f"{pid}.jpg")
        if os.path.exists(path):
            print(f"  skip (exists): {path}")
            continue
        if pil_ok:
            try:
                _try_pil(path, label, color)
                print(f"  created: {path}")
                continue
            except Exception as e:
                print(f"  PIL error ({e}), using PGM fallback")
        _try_pgm(path, color)

    print("\nDone. Replace images/ files with real product photos before the study.")


if __name__ == "__main__":
    main()
