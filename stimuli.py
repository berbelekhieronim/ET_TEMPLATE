#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stimuli.py – stimulus definitions for the food-choice eye-tracking experiment.

UWAGA BADAWCZA / RESEARCH NOTE:
W tym eksperymencie zdjęcia produktów są prawdziwe lub realistyczne,
ale składy prezentowane pod nimi są eksperymentalnie przypisanym tekstem
i nie muszą odpowiadać rzeczywistemu składowi produktu.
Składy zostały przypisane celowo w celach badawczych – do badania wpływu
atrakcyjności wizualnej opakowania na decyzje zakupowe.
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


@dataclass
class Product:
    product_id: str
    name: str
    image_path: str              # relative path under images/
    ingredients: List[str]       # EXPERIMENTAL – see note above
    health_profile: str          # 'good' | 'bad'  (for analysis; not shown to participant)


@dataclass
class ProductPair:
    pair_id: int
    product_a: Product           # will be randomised to left / right
    product_b: Product


@dataclass
class TrialConfig:
    trial_number: int
    pair: ProductPair
    left_product: Product
    right_product: Product


# ─────────────────────────────────────────────────────────────────────────────
#  10 product pairs
#  Manipulation: visually attractive ≠ better ingredients (and vice versa)
# ─────────────────────────────────────────────────────────────────────────────

PRODUCT_PAIRS: List[ProductPair] = [

    ProductPair(
        pair_id=1,
        product_a=Product(
            product_id="granola_premium",
            name="Baton Granolowy Premium",
            image_path="images/granola_premium.jpg",
            ingredients=[
                "płatki owsiane",
                "syrop glukozowo-fruktozowy",
                "tłuszcz palmowy",
                "skrobia modyfikowana",
                "aromat identyczny z naturalnym",
                "barwnik E150c",
                "sól",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="date_bar",
            name="Baton Daktylowy Naturalny",
            image_path="images/date_bar.jpg",
            ingredients=[
                "daktyle (60%)",
                "orzechy nerkowca",
                "inulina",
                "błonnik z cykorii",
                "ekstrakt z aceroli",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=2,
        product_a=Product(
            product_id="strawberry_yogurt",
            name="Jogurt Owocowy Truskawkowy",
            image_path="images/strawberry_yogurt.jpg",
            ingredients=[
                "mleko odtłuszczone",
                "cukier",
                "aromat truskawkowy",
                "barwnik E120",
                "skrobia modyfikowana",
                "żelatyna",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="natural_kefir",
            name="Kefir Naturalny z Witaminami",
            image_path="images/natural_kefir.jpg",
            ingredients=[
                "mleko pełnotłuste",
                "żywe kultury bakterii",
                "lecytyna słonecznikowa",
                "witamina D3",
                "witamina B12",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=3,
        product_a=Product(
            product_id="choco_cereals",
            name="Płatki Śniadaniowe Choco-Stars",
            image_path="images/choco_cereals.jpg",
            ingredients=[
                "mąka pszenna",
                "cukier",
                "kakao niskotłuszczowe (3%)",
                "syrop glukozowy",
                "tłuszcz palmowy",
                "sól",
                "barwnik E150a",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="oat_flakes",
            name="Płatki Owsiane Górskie",
            image_path="images/oat_flakes.jpg",
            ingredients=[
                "płatki owsiane pełnoziarniste (100%)",
                "beta-glukan",
                "błonnik pokarmowy",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=4,
        product_a=Product(
            product_id="protein_bar_mango",
            name="Batonik Proteinowy Mango-Kokos",
            image_path="images/protein_bar_mango.jpg",
            ingredients=[
                "izolat białka sojowego",
                "syrop glukozowy",
                "tłuszcz kokosowy",
                "aromat mangowocy",
                "sukraloza",
                "acesulfam K",
                "lecytyna sojowa",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="fig_oat_bar",
            name="Baton Owsiany z Figami i Orzechami",
            image_path="images/fig_oat_bar.jpg",
            ingredients=[
                "płatki owsiane",
                "figi suszone (25%)",
                "orzechy włoskie",
                "miód",
                "erytrytol",
                "inulina",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=5,
        product_a=Product(
            product_id="mango_smoothie",
            name="Smoothie Tropical Premium",
            image_path="images/mango_smoothie.jpg",
            ingredients=[
                "woda",
                "puree z mango (18%)",
                "cukier",
                "koncentrat soku bananowego",
                "kwas cytrynowy",
                "aromat naturalny",
                "barwnik beta-karoten",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="beet_juice",
            name="Sok z Kiszonych Buraków z Imbirem",
            image_path="images/beet_juice.jpg",
            ingredients=[
                "burak kiszony (85%)",
                "imbir",
                "pektyny jabłkowe",
                "kwas mlekowy (fermentacja)",
                "likopen",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=6,
        product_a=Product(
            product_id="bbq_chips",
            name="Chipsy BBQ \"Naturalne\"",
            image_path="images/bbq_chips.jpg",
            ingredients=[
                "ziemniaki",
                "olej słonecznikowy",
                "aromat BBQ",
                "wzmacniacz smaku E621",
                "cukier",
                "sól",
                "barwnik E150c",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="corn_wafers",
            name="Wafle Kukurydziane Pełnoziarniste",
            image_path="images/corn_wafers.jpg",
            ingredients=[
                "mąka kukurydziana pełnoziarnista (95%)",
                "błonnik z cykorii",
                "sól morska",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=7,
        product_a=Product(
            product_id="choco_cream",
            name="Krem Kakaowo-Orzechowy Premium",
            image_path="images/choco_cream.jpg",
            ingredients=[
                "cukier",
                "tłuszcz palmowy",
                "orzechy laskowe (13%)",
                "kakao niskotłuszczowe (7,4%)",
                "odtłuszczone mleko w proszku",
                "lecytyna sojowa",
                "aromat waniliowy",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="almond_butter",
            name="Masło Migdałowe 100% Naturalne",
            image_path="images/almond_butter.jpg",
            ingredients=[
                "migdały (100%)",
                "witamina E (tokoferol naturalny)",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=8,
        product_a=Product(
            product_id="tropical_muesli",
            name="Musli Tropikalne Fit&Fun",
            image_path="images/tropical_muesli.jpg",
            ingredients=[
                "płatki owsiane",
                "cukier",
                "papaja kandyzowana",
                "ananas kandyzowany",
                "tłuszcz palmowy",
                "aromat naturalny",
                "barwnik E160b",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="millet_instant",
            name="Kasza Jaglana Błyskawiczna",
            image_path="images/millet_instant.jpg",
            ingredients=[
                "kasza jaglana (100%)",
                "spirulina",
                "krzemionka",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=9,
        product_a=Product(
            product_id="fit_cookies",
            name="Ciastka Owsiane \"Zdrowe Wypieki\"",
            image_path="images/fit_cookies.jpg",
            ingredients=[
                "mąka pszenna",
                "cukier",
                "tłuszcz roślinny utwardzony",
                "płatki owsiane (12%)",
                "skrobia modyfikowana",
                "proszek do pieczenia",
                "aromat maślanego",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="sesame_honey",
            name="Sezamki Tradycyjne z Miodem",
            image_path="images/sesame_honey.jpg",
            ingredients=[
                "sezam (70%)",
                "miód naturalny",
                "ksylitol",
            ],
            health_profile="good",
        ),
    ),

    ProductPair(
        pair_id=10,
        product_a=Product(
            product_id="bio_energy",
            name="Drink Energetyczny \"Bio Nature\"",
            image_path="images/bio_energy.jpg",
            ingredients=[
                "woda gazowana",
                "cukier",
                "ekstrakt guarany (0,4%)",
                "kwas fosforowy",
                "kofeina (32 mg/100ml)",
                "aromat naturalny",
                "barwnik E150d",
            ],
            health_profile="bad",
        ),
        product_b=Product(
            product_id="coconut_water",
            name="Woda Kokosowa Naturalna",
            image_path="images/coconut_water.jpg",
            ingredients=[
                "woda kokosowa (100%)",
                "elektrolity naturalne",
                "potas",
                "magnez",
            ],
            health_profile="good",
        ),
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Trial list builder
# ─────────────────────────────────────────────────────────────────────────────

def build_trial_list(pairs: List[ProductPair] = None,
                     n_trials: int = 10) -> List[TrialConfig]:
    """
    Build a randomised trial list.
    • Shuffles the order of pairs.
    • Randomly assigns which product goes left vs right for each pair,
      ensuring no consistent side-bias (independent coin flip per trial).
    """
    if pairs is None:
        pairs = PRODUCT_PAIRS

    selected = random.sample(pairs, min(n_trials, len(pairs)))
    random.shuffle(selected)

    trials = []
    for idx, pair in enumerate(selected, start=1):
        if random.random() < 0.5:
            left, right = pair.product_a, pair.product_b
        else:
            left, right = pair.product_b, pair.product_a
        trials.append(TrialConfig(
            trial_number=idx,
            pair=pair,
            left_product=left,
            right_product=right,
        ))
    return trials


# ─────────────────────────────────────────────────────────────────────────────
#  AOI definitions (Tobii normalised coords: 0-1, top-left origin)
# ─────────────────────────────────────────────────────────────────────────────

def get_aoi_definitions() -> Dict[str, Tuple[float, float, float, float]]:
    """
    Returns {aoi_name: (x_left, y_top, x_right, y_bottom)} in Tobii normalised coords.

    Layout (1920×1080):
      ┌──────────────────────────────────────────────────────────────────┐
      │  trial-counter bar  (full width, top 8%)                        │
      │  ┌──────────────────┐      ┌──────────────────┐                │
      │  │  LEFT CARD       │      │  RIGHT CARD       │                │
      │  │  name            │      │  name             │                │
      │  │  [image]         │      │  [image]          │                │
      │  │  Skład:          │      │  Skład:           │                │
      │  │  - item…         │      │  - item…          │                │
      │  └──────────────────┘      └──────────────────┘                │
      └──────────────────────────────────────────────────────────────────┘
    """
    return {
        "left_image":  (0.03, 0.12, 0.46, 0.56),
        "left_text":   (0.03, 0.59, 0.46, 0.96),
        "right_image": (0.54, 0.12, 0.97, 0.56),
        "right_text":  (0.54, 0.59, 0.97, 0.96),
        # optional name strip
        "left_name":   (0.03, 0.08, 0.46, 0.12),
        "right_name":  (0.54, 0.08, 0.97, 0.12),
    }
