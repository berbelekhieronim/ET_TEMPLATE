#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.py – PsychoPy visual helpers: screens, questionnaire, product cards.

All coordinates assume:  units='pix', size=(1920,1080), origin at centre.
Tobii normalised coords are converted via utils.tobii_to_psychopy().
"""

import os
import time
from typing import List, Dict, Optional, Tuple

from psychopy import visual, event, core  # type: ignore

from utils import SCR_W, SCR_H

# ─────────────────────────────────────────────────────────────────────────────
#  Colours & typography
# ─────────────────────────────────────────────────────────────────────────────

BG_COLOR   = (0.92, 0.92, 0.92)   # PsychoPy RGB  (–1 … +1)
FG_COLOR   = (-0.8, -0.8, -0.8)   # near-black
CARD_COLOR = (0.98, 0.98, 0.98)   # card background
CARD_BORDER= (0.6,  0.6,  0.6)
ACCENT     = (-0.2, 0.3, -0.2)    # dark green for headers
BTN_BG     = (0.2,  0.2,  0.2)
BTN_FG     = (1.0,  1.0,  1.0)
SEL_COLOR  = (0.0,  0.5,  0.0)    # selected-option highlight (green)

FONT = "Arial"
TITLE_SIZE  = 42
BODY_SIZE   = 32
SMALL_SIZE  = 26
BTN_SIZE    = 30
CARD_NAME_SZ= 30
INGR_SIZE   = 24
INGR_LEAD   = 34   # line height for ingredients

# Layout
HALF = SCR_W // 2
CARD_W = 840
CARD_H = 920
IMG_W  = 620
IMG_H  = 370
IMG_Y_OFFSET  =  130     # image centre y from card centre
TEXT_Y_OFFSET = -200     # ingredient text centre y from card centre
NAME_Y_OFFSET =  420     # product name y from card centre
TRIAL_CTR_Y   =  490     # trial counter y from screen centre

LEFT_CX  = -(HALF // 2)      # ≈ –480
RIGHT_CX =   HALF // 2       # ≈  +480


# ─────────────────────────────────────────────────────────────────────────────
#  Window creation
# ─────────────────────────────────────────────────────────────────────────────

def create_window(fullscreen: bool = True,
                  screen: int = 0) -> visual.Window:
    win = visual.Window(
        size=(SCR_W, SCR_H),
        fullscr=fullscreen,
        screen=screen,
        units="pix",
        color=BG_COLOR,
        colorSpace="rgb",
        allowGUI=False,
    )
    win.mouseVisible = False
    return win


# ─────────────────────────────────────────────────────────────────────────────
#  Generic helpers
# ─────────────────────────────────────────────────────────────────────────────

def _text(win, text, pos=(0, 0), height=BODY_SIZE, color=FG_COLOR,
          bold=False, wrap=SCR_W - 200, align="center") -> visual.TextStim:
    return visual.TextStim(
        win, text=text, font=FONT, pos=pos, height=height, color=color,
        colorSpace="rgb", bold=bold, wrapWidth=wrap, alignText=align,
    )


def _rect(win, pos, w, h, fill=CARD_COLOR, border=CARD_BORDER,
          border_w=2) -> visual.Rect:
    return visual.Rect(
        win, pos=pos, width=w, height=h,
        fillColor=fill, lineColor=border, lineWidth=border_w,
        colorSpace="rgb",
    )


def show_text_screen(win: visual.Window, text: str,
                     subtext: str = "",
                     button_label: str = "Dalej →",
                     key: str = "space") -> None:
    """Full-screen message with a 'button' at the bottom."""
    elems = [_text(win, text, pos=(0, 80), height=TITLE_SIZE,
                   bold=True, color=FG_COLOR)]
    if subtext:
        elems.append(_text(win, subtext, pos=(0, -30), height=BODY_SIZE))

    btn = _rect(win, (0, -420), 320, 60, fill=BTN_BG, border=BTN_BG)
    btn_lbl = _text(win, button_label, pos=(0, -420), height=BTN_SIZE,
                    color=BTN_FG)

    for e in elems:
        e.draw()
    btn.draw()
    btn_lbl.draw()
    win.flip()
    event.waitKeys(keyList=[key, "escape"])


# ─────────────────────────────────────────────────────────────────────────────
#  Questionnaire
# ─────────────────────────────────────────────────────────────────────────────

QUESTIONS = [
    {
        "id": "q1_diet",
        "text": "Czy byłeś/aś lub jesteś na diecie?",
        "options": ["tak", "nie"],
    },
    {
        "id": "q2_ingredients",
        "text": "Czy przed zakupem produktu zwracasz uwagę na jego skład?",
        "options": ["nigdy", "rzadko", "czasami", "często", "zawsze"],
    },
    {
        "id": "q3_healthy",
        "text": "Czy starasz się wybierać zdrowsze produkty spożywcze?",
        "options": ["nigdy", "rzadko", "czasami", "często", "zawsze"],
    },
    {
        "id": "q4_importance",
        "text": "Jak ważny jest dla Ciebie skład produktu podczas zakupów?",
        "options": [
            "1 – zupełnie nieważny", "2", "3",
            "4", "5 – bardzo ważny",
        ],
    },
    {
        "id": "q5_earth",
        "text": "Czy uważasz, że Ziemia jest płaska?",
        "options": [
            "zdecydowanie nie", "raczej nie",
            "trudno powiedzieć", "raczej tak", "zdecydowanie tak",
        ],
        "note": "(pytanie kontrolne)",
    },
]


def run_questionnaire(win: visual.Window) -> Dict[str, Dict]:
    """
    Shows each question on a separate screen.
    Returns dict: {question_id: {"text": ..., "answer": ...}}
    Participant must select an option before proceeding.
    """
    mouse = event.Mouse(win=win)
    answers: Dict[str, Dict] = {}

    for q in QUESTIONS:
        selected_idx: Optional[int] = None
        option_rects: List[Tuple[visual.Rect, visual.TextStim]] = []

        while True:
            win.color = BG_COLOR

            # Question text
            note = q.get("note", "")
            qtxt = _text(win,
                         q["text"] + (f"  {note}" if note else ""),
                         pos=(0, 250), height=BODY_SIZE, bold=True,
                         wrap=SCR_W - 160)

            # Option buttons
            n = len(q["options"])
            opt_h = 54
            spacing = 66
            start_y = 120 - (n // 2) * spacing

            option_rects = []
            for i, opt in enumerate(q["options"]):
                oy = start_y + i * spacing
                is_sel = (i == selected_idx)
                bg = SEL_COLOR if is_sel else (0.85, 0.85, 0.85)
                bdr = SEL_COLOR if is_sel else CARD_BORDER
                r = _rect(win, (0, oy), 600, opt_h, fill=bg, border=bdr,
                          border_w=3 if is_sel else 1)
                lbl = _text(win, opt, pos=(0, oy), height=SMALL_SIZE,
                            color=BTN_FG if is_sel else FG_COLOR)
                option_rects.append((r, lbl))

            # "Dalej" button  – only active when something is selected
            can_proceed = selected_idx is not None
            btn_bg = BTN_BG if can_proceed else (0.5, 0.5, 0.5)
            btn = _rect(win, (0, -350), 280, 56, fill=btn_bg, border=btn_bg)
            btn_lbl = _text(win, "Dalej →", pos=(0, -350), height=BTN_SIZE,
                            color=BTN_FG)

            # Draw
            qtxt.draw()
            for r, lbl in option_rects:
                r.draw(); lbl.draw()
            btn.draw(); btn_lbl.draw()
            win.flip()

            # Input
            mouse.clickReset()
            core.wait(0.05)
            buttons, _ = mouse.getPressed(getTime=True)

            if buttons[0]:
                mx, my = mouse.getPos()
                for i, (r, _) in enumerate(option_rects):
                    rx, ry = r.pos
                    hw, hh = r.width / 2, r.height / 2
                    if abs(mx - rx) <= hw and abs(my - ry) <= hh:
                        selected_idx = i
                        break

                # Check "Dalej" click
                bx, by = btn.pos
                bhw, bhh = btn.width / 2, btn.height / 2
                if (can_proceed
                        and abs(mx - bx) <= bhw
                        and abs(my - by) <= bhh):
                    answers[q["id"]] = {
                        "text": q["text"],
                        "answer": q["options"][selected_idx],
                    }
                    core.wait(0.1)
                    break

            keys = event.getKeys(keyList=["escape"])
            if keys:
                raise SystemExit(0)

    return answers


# ─────────────────────────────────────────────────────────────────────────────
#  Product card drawing
# ─────────────────────────────────────────────────────────────────────────────

def _build_ingredients_text(ingredients: List[str]) -> str:
    lines = ["Skład:", ""]
    for item in ingredients:
        lines.append(f"  {item}")
    return "\n".join(lines)


def draw_product_card(
    win: visual.Window,
    product,
    cx: float,
    image_stim: Optional[visual.ImageStim] = None,
    placeholder_color=(0.6, 0.6, 0.6),
) -> None:
    """Draw one product card centred at (cx, 0) screen pixels."""
    card_pos = (cx, 0)

    # Card background
    _rect(win, card_pos, CARD_W, CARD_H).draw()

    # Product name
    _text(win, product.name,
          pos=(cx, NAME_Y_OFFSET),
          height=CARD_NAME_SZ, bold=True,
          color=FG_COLOR, wrap=CARD_W - 40).draw()

    # Product image or placeholder
    img_pos = (cx, IMG_Y_OFFSET)
    if image_stim is not None:
        image_stim.draw()
    else:
        _rect(win, img_pos, IMG_W, IMG_H,
              fill=placeholder_color,
              border=CARD_BORDER).draw()
        _text(win, "[zdjęcie produktu]",
              pos=img_pos, height=SMALL_SIZE,
              color=(0.9, 0.9, 0.9)).draw()

    # Ingredients block
    ingr_text = _build_ingredients_text(product.ingredients)
    _text(win, ingr_text,
          pos=(cx, TEXT_Y_OFFSET),
          height=INGR_SIZE,
          color=FG_COLOR,
          wrap=CARD_W - 60,
          align="left").draw()


def load_image_stim(
    win: visual.Window,
    image_path: str,
    cx: float,
    size: Tuple[int, int] = (IMG_W, IMG_H),
) -> Optional[visual.ImageStim]:
    """Load image, return None if file missing."""
    if not os.path.exists(image_path):
        return None
    try:
        return visual.ImageStim(
            win, image=image_path,
            pos=(cx, IMG_Y_OFFSET),
            size=size,
        )
    except Exception as e:
        print(f"[ui] Could not load image '{image_path}': {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Trial screen
# ─────────────────────────────────────────────────────────────────────────────

def run_trial_screen(
    win: visual.Window,
    trial_config,
    trial_total: int = 10,
) -> Tuple[str, float]:
    """
    Displays two product cards side by side.
    Left-click → 'left', Right-click → 'right'.
    Returns (chosen_side, reaction_time_ms).
    """
    mouse = event.Mouse(win=win)
    clock = core.Clock()

    # Pre-load images
    img_left  = load_image_stim(win, trial_config.left_product.image_path,  LEFT_CX)
    img_right = load_image_stim(win, trial_config.right_product.image_path, RIGHT_CX)

    # Trial-counter text
    counter_text = _text(
        win,
        f"Próba {trial_config.trial_number} z {trial_total}",
        pos=(0, TRIAL_CTR_Y),
        height=SMALL_SIZE,
        color=FG_COLOR,
    )
    # Instruction reminder at the bottom
    hint = _text(
        win,
        "Lewy przycisk myszy = produkt po lewej   |   Prawy przycisk myszy = produkt po prawej",
        pos=(0, -490),
        height=22,
        color=(0.0, 0.0, 0.0),
    )

    # Show fixation cross briefly
    fix_h = visual.Line(win, start=(-25, 0), end=(25, 0),
                        lineColor=FG_COLOR, lineWidth=3)
    fix_v = visual.Line(win, start=(0, -25), end=(0, 25),
                        lineColor=FG_COLOR, lineWidth=3)
    fix_h.draw(); fix_v.draw(); win.flip()
    core.wait(0.8)

    # Main trial loop
    mouse.clickReset()
    win.color = BG_COLOR
    clock.reset()

    while True:
        counter_text.draw()
        draw_product_card(win, trial_config.left_product,  LEFT_CX,
                          image_stim=img_left)
        draw_product_card(win, trial_config.right_product, RIGHT_CX,
                          image_stim=img_right)
        hint.draw()
        win.flip()

        buttons, times = mouse.getPressed(getTime=True)
        if buttons[0]:          # left button
            rt = times[0] * 1000
            break
        if buttons[2]:          # right button
            rt = times[2] * 1000
            break

        keys = event.getKeys(["escape"])
        if keys:
            raise SystemExit(0)

    chosen = "left" if buttons[0] else "right"

    # Brief feedback flash
    feedback_text = (
        "← Wybrano lewy produkt" if chosen == "left"
        else "Wybrano prawy produkt →"
    )
    _text(win, feedback_text, pos=(0, 0), height=BODY_SIZE,
          color=ACCENT, bold=True).draw()
    win.flip()
    core.wait(0.5)
    win.flip()
    core.wait(0.3)   # ISI

    return chosen, rt


# ─────────────────────────────────────────────────────────────────────────────
#  Calibration screen wrapper (delegates to tracker)
# ─────────────────────────────────────────────────────────────────────────────

def run_calibration_screen(win: visual.Window, tracker) -> bool:
    show_text_screen(
        win,
        "Kalibracja eye trackera",
        subtext=(
            "Za chwilę rozpocznie się kalibracja.\n"
            "Patrz na pojawiające się punkty na ekranie.\n\n"
            "Naciśnij SPACJĘ, aby rozpocząć."
        ),
    )
    win.color = BG_COLOR
    win.flip()
    return tracker.calibrate(win)
