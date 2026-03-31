# -*- coding: utf-8 -*-
"""
eyetrackingbadanie_code.py  –  Badanie eye-trackingowe (Tobii X3-120 + PsychoPy)

Opis:
  • Kalibracja eye-trackera na pierwszej (wybranej) recenzji z pliku JSON
  • Próby (trials): losowo wybrane recenzje prezentowane jako tekst
  • Uczestnik ocenia każdą recenzję jako pozytywną (→) lub negatywną (←)
  • Dane wzroku zapisywane binarnie do folderu /output (120 Hz)
  • Wyjście ESC w dowolnym momencie

Wymagania:
  • Python 3.x (Windows) z zainstalowanym PsychoPy
  • Tobii Pro SDK zainstalowany systemowo
    LUB lokalnie w folderze ./x3-120 SDK/64/  (wymaga tobii_research_interop.pyd)
  • Pliki w tym samym folderze:
      - selected_reviews_data.json
      - IBMPlexMono-Regular.ttf
      - config.txt (tworzony automatycznie przy pierwszym uruchomieniu)

Konfiguracja (config.txt):
  CALIBRATION_REVIEW_ID = ID recenzji używanej do kalibracji
  N_TRIALS              = liczba prób (ALL = wszystkie dostępne)
  BG_BRIGHTNESS         = jasność tła (0.0–1.0)
  FIXATION_TOLERANCE    = tolerancja fiksacji (ułamek ekranu, np. 0.03)
  FIXATION_DURATION     = wymagany czas fiksacji w sekundach (np. 0.6)
"""

# ─────────────────────────────────────────────────────────────────────────────
#  PARAMETRY DOMYŚLNE (nadpisywane przez config.txt)
# ─────────────────────────────────────────────────────────────────────────────
JSON_DB            = "selected_reviews_data.json"
FONT               = "IBM Plex Mono"
FSIZE              = 34
LINE_SP            = 2
TL, BR             = (0.12, 0.18), (0.90, 0.99)   # obszar tekstu (frakcja ekranu)

FIX_DUR            = 0.60    # czas trwania fiksacji [s]
FIX_TOL            = 0.03    # tolerancja fiksacji (frakcja ekranu)
FIX_TIMEOUT        = 5.0     # maksymalny czas oczekiwania na fiksację [s]

CALIB_DUR          = 0.50    # czas zbierania próbek na punkt kalibracji [s]
CALIB_TOL          = 0.15    # tolerancja dla punktu kalibracji
CALIB_TIMEOUT      = 5.0     # timeout dla fixacji kalibracyjnej [s]
CALIB_MAX_RETRIES  = 3       # max liczba powtórzeń collect_data

SAVE_LIMIT         = 1000    # maks. liczba plików binarnych

# ─────────────────────────────────────────────────────────────────────────────
#  IMPORTY
# ─────────────────────────────────────────────────────────────────────────────
import ctypes
import math
import os
import json
import random
import struct
import threading
import queue
import time
import sys
import logging as pylog
from logging.handlers import RotatingFileHandler

import pyglet
from psychopy import visual, event, core, monitors, logging

# ── Global ESC kill-switch ────────────────────────────────────────────────────
event.globalKeys.add(key='escape', func=os._exit, func_args=(1,))

# ── Windows DPI Awareness ────────────────────────────────────────────────────
for _fn in ("SetProcessDpiAwareness", "SetProcessDPIAware"):
    try:
        getattr(
            ctypes.windll.shcore if _fn.endswith("Awareness") else ctypes.windll.user32,
            _fn
        )(1)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  LOGGING  (rotujące pliki 5 MB × 5 + konsola)
# ─────────────────────────────────────────────────────────────────────────────
HERE     = os.path.abspath(os.path.dirname(__file__))
LOG_PATH = os.path.join(HERE, "badanie_debug.log")

_rot = RotatingFileHandler(
    LOG_PATH, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
)
_rot.setFormatter(pylog.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
))
_console = pylog.StreamHandler()
_console.setFormatter(pylog.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
))
pylog.basicConfig(level=pylog.INFO, handlers=[_rot, _console])
pylog.info("=== Badanie uruchomione ===")


def _log_exc(msg):
    pylog.exception(msg)
    for h in pylog.root.handlers:
        h.flush()


def _log(msg, *args):
    """Log + natychmiastowy flush (zapobiega utracie danych przy awarii)."""
    pylog.info(msg, *args)
    for h in pylog.root.handlers:
        h.flush()


# ─────────────────────────────────────────────────────────────────────────────
#  BINARNY ZAPIS DANYCH (wątek zapisu)
# ─────────────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(HERE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _next_bin():
    for i in range(SAVE_LIMIT):
        fn = os.path.join(OUTPUT_DIR, f"badanie{i:03d}.bin")
        if not os.path.exists(fn):
            return fn
    raise RuntimeError("Wszystkie pliki badanie000–badanie999 istnieją!")


DATA_PATH = _next_bin()
_STRUCT   = struct.Struct("d7f")   # timestamp + 7 float
_BUF_N    = 5000                   # bufor przed zapisem
_q        = queue.Queue()
_stop_w   = threading.Event()


def _writer():
    buf = bytearray()
    try:
        with open(DATA_PATH, "wb") as fh:
            while not (_stop_w.is_set() and _q.empty()):
                try:
                    rec = _q.get(timeout=0.1)
                except queue.Empty:
                    continue
                buf += _STRUCT.pack(*rec)
                if len(buf) // _STRUCT.size >= _BUF_N:
                    fh.write(buf)
                    buf.clear()
            if buf:
                fh.write(buf)
    except Exception:
        _log_exc("Wątek zapisu uległ awarii")


_log_thread = threading.Thread(target=_writer, daemon=False)
_log_thread.start()


def push_event(code, *params):
    """Wstaw zdarzenie do kolejki binarnego zapisu."""
    ts = time.time()
    try:
        ts = tr.get_system_time_stamp() * 1e-6
    except Exception:
        pass
    vals = [float(p) for p in params]
    vals += [math.nan] * (6 - len(vals))
    _q.put((ts, float(code), *vals))


# ─────────────────────────────────────────────────────────────────────────────
#  POŁĄCZENIE Z TOBII X3-120
# ─────────────────────────────────────────────────────────────────────────────
# Próba załadowania lokalnego SDK (./x3-120 SDK/64/) przed systemowym
X3_SDK_PATH = os.path.join(HERE, "x3-120 SDK", "64")
if os.path.exists(X3_SDK_PATH) and X3_SDK_PATH not in sys.path:
    sys.path.insert(0, X3_SDK_PATH)
    _log("Dodano lokalny X3-120 SDK do ścieżki: %s", X3_SDK_PATH)

TOBII = {"connected": False, "error": None}
et = None

try:
    import tobii_research as tr
    _log("Tobii Research SDK załadowany, wersja: %s", tr.__version__)

    trackers = tr.find_all_eyetrackers()
    if trackers:
        et = trackers[0]
        _log("Połączono z %s (S/N: %s)", et.model, et.serial_number)

        # Ustaw 120 Hz jeśli dostępne
        available_freqs = et.get_all_gaze_output_frequencies()
        _log("Dostępne częstotliwości: %s", available_freqs)
        if 120.0 in available_freqs:
            et.set_gaze_output_frequency(120.0)
            _log("Ustawiono 120 Hz")
        elif available_freqs:
            et.set_gaze_output_frequency(max(available_freqs))
            _log("Ustawiono %s Hz (max dostępne)", max(available_freqs))

        time.sleep(0.1)
        TOBII.update(
            connected=True,
            serial=et.serial_number,
            model=et.model,
            freq=et.get_gaze_output_frequency(),
        )
    else:
        pylog.warning("Nie znaleziono eye-trackera. Tryb symulacji.")

except Exception as exc:
    _log_exc("Błąd inicjalizacji Tobii")
    TOBII["error"] = str(exc)
    print("\n" + "=" * 65)
    print("BŁĄD: Nie można zainicjować eye-trackera Tobii!")
    print(f"Szczegóły: {exc}")
    print("Uruchom debug_import.py dla pełnej diagnostyki.")
    print("=" * 65 + "\n")

# ─────────────────────────────────────────────────────────────────────────────
#  WCZYTANIE DANYCH I KONFIGURACJI
# ─────────────────────────────────────────────────────────────────────────────
pyglet.font.add_file(os.path.join(HERE, "IBMPlexMono-Regular.ttf"))
logging.console.setLevel(logging.ERROR)

with open(os.path.join(HERE, JSON_DB), encoding="utf-8") as fh:
    db = json.load(fh)

CONFIG_FILE = os.path.join(HERE, "config.txt")

# Tworzenie domyślnego config.txt jeśli brak
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as cf:
        cf.write(
            "# Plik konfiguracyjny dla eyetrackingbadanie_code.py\n"
            "#\n"
            "# ID recenzji używanej do kalibracji\n"
            f"CALIBRATION_REVIEW_ID={db[0]['id']}\n\n"
            "# Liczba prób (ALL = wszystkie)\n"
            "N_TRIALS=ALL\n\n"
            "# Jasność tła (0=czarne, 1=białe)\n"
            "BG_BRIGHTNESS=0.95\n\n"
            "# Tolerancja fiksacji (ułamek ekranu)\n"
            "FIXATION_TOLERANCE=0.03\n\n"
            "# Wymagany czas fiksacji [sekundy]\n"
            "FIXATION_DURATION=0.6\n"
        )
    _log("Utworzono domyślny config.txt")

# Odczyt config.txt
CALIBRATION_REVIEW_ID = db[0]["id"]
N_TRIALS              = "ALL"
BG_BRIGHTNESS         = 0.95

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as cf:
        for line in cf:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()

            if key == "CALIBRATION_REVIEW_ID":
                try:
                    CALIBRATION_REVIEW_ID = int(val)
                except ValueError:
                    pylog.warning("Nieprawidłowe CALIBRATION_REVIEW_ID: %s", val)

            elif key == "N_TRIALS":
                if val.upper() == "ALL" or not val:
                    N_TRIALS = "ALL"
                else:
                    try:
                        N_TRIALS = max(1, int(val))
                    except ValueError:
                        pylog.warning("Nieprawidłowe N_TRIALS: %s", val)

            elif key == "BG_BRIGHTNESS":
                try:
                    BG_BRIGHTNESS = max(0.0, min(1.0, float(val)))
                except ValueError:
                    pylog.warning("Nieprawidłowe BG_BRIGHTNESS: %s", val)

            elif key == "FIXATION_TOLERANCE":
                try:
                    FIX_TOL = max(0.01, min(0.2, float(val)))
                except ValueError:
                    pylog.warning("Nieprawidłowe FIXATION_TOLERANCE: %s", val)

            elif key == "FIXATION_DURATION":
                try:
                    FIX_DUR = max(0.1, min(5.0, float(val)))
                except ValueError:
                    pylog.warning("Nieprawidłowe FIXATION_DURATION: %s", val)

except Exception as e:
    pylog.error("Błąd odczytu config.txt: %s — używam wartości domyślnych", e)

# PsychoPy używa zakresu koloru od -1 do 1
BG_COLOR = [BG_BRIGHTNESS * 2 - 1] * 3
_log("Kolor tła: %s (jasność=%.2f)", BG_COLOR, BG_BRIGHTNESS)

# ── Podział recenzji na kalibracyjną i próby ──────────────────────────────────
calibration_review = None
trial_reviews = []

for review in db:
    if review["id"] == CALIBRATION_REVIEW_ID:
        calibration_review = review
    else:
        trial_reviews.append(review)

if calibration_review is None:
    pylog.warning(
        "Nie znaleziono recenzji ID=%s do kalibracji, używam pierwszej.",
        CALIBRATION_REVIEW_ID
    )
    calibration_review = db[0]
    trial_reviews      = db[1:]

_log("Kalibracja: recenzja ID=%s", calibration_review["id"])
_log("Pula prób: %d recenzji", len(trial_reviews))

total_available = len(trial_reviews)
if N_TRIALS == "ALL":
    N_TRIALS = total_available
    _log("Uruchomione zostaną WSZYSTKIE próby: %d", N_TRIALS)
else:
    if N_TRIALS > total_available:
        pylog.warning("N_TRIALS=%d > dostępne=%d, używam wszystkich", N_TRIALS, total_available)
        N_TRIALS = total_available
    _log("Liczba prób: %d", N_TRIALS)

# ─────────────────────────────────────────────────────────────────────────────
#  OKNO PSYCHOPY
# ─────────────────────────────────────────────────────────────────────────────
SCREEN_INDEX = 0

mon = monitors.Monitor("scr")
mon.setSizePix((1920, 1080))
mon.save()

win = visual.Window(
    size=(1920, 1080),
    fullscr=True,
    monitor=mon,
    units="pix",
    color=BG_COLOR,
    screen=SCREEN_INDEX
)
win.mouseVisible = False
SCR_W, SCR_H = win.size

# ── Czcionka monospace (IBM Plex Mono) ────────────────────────────────────────
pyglet.font.load(FONT, FSIZE)
_FONT = pyglet.font.load(FONT, FSIZE)


def gw(ch):
    """Szerokość glifów z fallbackiem dla brakujących znaków."""
    try:
        glyphs = _FONT.get_glyphs(ch)
        if glyphs:
            return glyphs[0].advance
        pylog.warning("Brakujący glif U+%04X, używam przybliżenia", ord(ch))
        return FSIZE * 0.6
    except Exception as e:
        pylog.error("Błąd glifów dla '%s': %s", ch, e)
        return FSIZE * 0.6


space_adv = gw(" ")
line_h    = FSIZE * LINE_SP

# ─────────────────────────────────────────────────────────────────────────────
#  POMOCNICZE
# ─────────────────────────────────────────────────────────────────────────────
ABORT = False


def abort_if_escape():
    global ABORT
    if not ABORT and event.getKeys(["escape"]):
        ABORT = True
        _log("Przerwanie przez ESC")
    return ABORT


# ── Callback wzroku ──────────────────────────────────────────────────────────
last_gaze   = {"valid": False, "x": math.nan, "y": math.nan}
_gaze_ctr   = 0
_LOG_EVERY  = 120   # log co 1 sekundę przy 120 Hz

if TOBII["connected"]:
    def _gaze_cb(g):
        global _gaze_ctr
        try:
            lx = ly = rx = ry = lp = rp = math.nan
            valid = False
            if g["left_gaze_point_validity"]:
                lx, ly = g["left_gaze_point_on_display_area"]
                valid = True
            if g["right_gaze_point_validity"]:
                rx, ry = g["right_gaze_point_on_display_area"]
                valid = True
            if g["left_pupil_validity"]:
                lp = g["left_pupil_diameter"]
            if g["right_pupil_validity"]:
                rp = g["right_pupil_diameter"]

            push_event(0.0, lx, ly, rx, ry, lp, rp)

            if _gaze_ctr % _LOG_EVERY == 0:
                pylog.info(
                    "Wzrok #%d valid=%s L=(%.3f,%.3f) P=(%.3f,%.3f)",
                    _gaze_ctr, valid, lx, ly, rx, ry
                )
            _gaze_ctr += 1

            if valid:
                gx, gy = (lx, ly) if not math.isnan(lx) else (rx, ry)
                last_gaze.update(valid=True, x=gx, y=gy)
            else:
                last_gaze["valid"] = False
        except Exception:
            _log_exc("Wyjątek w callbacku wzroku")

    et.subscribe_to(tr.EYETRACKER_GAZE_DATA, _gaze_cb, as_dictionary=True)
    _log("Zasubskrybowano strumień wzroku")


def _gaze_on_target(nx, ny, tol):
    if not last_gaze["valid"]:
        return False
    return math.hypot(last_gaze["x"] - nx, last_gaze["y"] - ny) <= tol


# ─────────────────────────────────────────────────────────────────────────────
#  KALIBRACJA
# ─────────────────────────────────────────────────────────────────────────────
def perform_calibration():
    """
    Kalibracja 5-punktowa z wizualizacją wyników.

    Każdy punkt kalibracji odpowiada literze z tekstu recenzji kalibracyjnej.
    Litera miga na czerwono → uczestnik fiksuje wzrok → zbieranie danych.
    Po kalibracji pokazywany jest wykres próbek (zielone kółka) na tle tekstu.
    Spacja = zatwierdź i przejdź dalej | ESC = przerwij badanie.
    """
    _log(">>> KALIBRACJA: start")

    if abort_if_escape():
        return

    # ── Układ tekstu ──────────────────────────────────────────────────────────
    words_plain = [w["word"] for w in calibration_review["word_centroids"]]
    box_w  = (BR[0] - TL[0]) * SCR_W
    tlx    = TL[0] * SCR_W
    tly    = TL[1] * SCR_H

    lines, cur, acc = [], [], 0
    for w in words_plain:
        adv = sum(gw(c) for c in w) + space_adv
        if cur and acc + adv > box_w:
            lines.append(cur)
            cur, acc = [w], adv
        else:
            cur.append(w)
            acc += adv
    if cur:
        lines.append(cur)
    _log("Kalibracja: %d linii tekstu", len(lines))

    # ── Indeksowanie liter ────────────────────────────────────────────────────
    letter_info, w2idx = [], {}
    w_idx = 0
    for r, line in enumerate(lines):
        y = tly + r * line_h
        x = tlx
        for w in line:
            for ch in w:
                em = gw(ch)
                letter_info.append((ch, x, y, em, w_idx))
                x += em
            x += space_adv
            w_idx += 1
    for li, (*_, wi) in enumerate(letter_info):
        w2idx.setdefault(wi, []).append(li)
    _log("Kalibracja: %d liter", len(letter_info))

    # ── Stymulusy TextStim ────────────────────────────────────────────────────
    GRAY  = [0.4] * 3
    RED   = [1, -1, -1]
    GREEN = [-1, 1, -1]

    letter_stims = []
    for ch, x, y, em, _ in letter_info:
        stim = visual.TextStim(
            win, text=ch, font=FONT, height=FSIZE, color=GRAY,
            pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
        )
        stim.autoDraw = True
        letter_stims.append(stim)
    win.flip()

    # ── Tryb kalibracji trackera ──────────────────────────────────────────────
    tracker_on = TOBII.get("connected", False)
    calib = None
    if tracker_on:
        try:
            calib = tr.ScreenBasedCalibration(et)
            status = calib.enter_calibration_mode()
            _log("Wejście w tryb kalibracji: %s", status)
        except Exception:
            _log_exc("Błąd wejścia w tryb kalibracji — tryb bez trackera")
            tracker_on = False

    # ── Wybór 5 punktów kalibracyjnych ───────────────────────────────────────
    default_targets = [
        (0.5, 0.5), (0.1, 0.1), (0.9, 0.1),
        (0.1, 0.9), (0.9, 0.9)
    ]
    targets = []
    for nx, ny in default_targets:
        best_d, pick = float("inf"), None
        for wi, wdat in enumerate(calibration_review["word_centroids"]):
            for li, (cx, cy) in enumerate(wdat["centroids"]):
                if not wdat["word"][li].isalpha():
                    continue
                d2 = (cx - nx) ** 2 + (cy - ny) ** 2
                if d2 < best_d:
                    best_d, pick = d2, (wi, (cx, cy))
        targets.append((nx, ny, *pick))
    _log("Wybrano %d punktów kalibracji", len(targets))

    def blink(li, idx):
        """Błysk litery na czerwono — sygnał dla uczestnika."""
        _log("Blink: punkt %d — czerwony ON", idx)
        letter_stims[li].color = RED
        letter_stims[li].bold  = True
        win.flip(); core.wait(0.20)
        letter_stims[li].color = GRAY
        letter_stims[li].bold  = False
        win.flip(); core.wait(0.10)
        letter_stims[li].color = RED
        letter_stims[li].bold  = True
        win.flip(); core.wait(0.25)
        # litera pozostaje czerwona

    # ── Pętla punktów kalibracyjnych ─────────────────────────────────────────
    prev_li      = None
    best_letters = []

    for idx, (nx, ny, wi, (cx, cy)) in enumerate(targets, start=1):
        _log("=== Punkt kalibracji %d/%d ===", idx, len(targets))
        if abort_if_escape():
            break

        # wyczyść poprzedni punkt
        if prev_li is not None:
            letter_stims[prev_li].color = GRAY
            letter_stims[prev_li].bold  = False
            win.flip()

        # wybierz i mignij bieżącą literę
        best_li = min(
            w2idx[wi],
            key=lambda li: (
                (letter_info[li][1] + letter_info[li][3] / 2 - cx * SCR_W) ** 2
                + (letter_info[li][2] + FSIZE / 2 - cy * SCR_H) ** 2
            )
        )
        best_letters.append(best_li)
        blink(best_li, idx)
        prev_li = best_li

        if tracker_on:
            # czekaj na fiksację uczestnika
            t0 = core.getTime()
            fix0 = None
            fixation_ok = False
            manual_skip = False
            event.clearEvents(eventType="keyboard")

            while core.getTime() - t0 < CALIB_TIMEOUT:
                if abort_if_escape():
                    break
                if event.getKeys(keyList=["space"]):
                    manual_skip = True
                    _log("Punkt %d pominięty przez eksperymentatora (Spacja)", idx)
                    break
                if _gaze_on_target(nx, ny, CALIB_TOL):
                    fix0 = fix0 or core.getTime()
                    if core.getTime() - fix0 >= CALIB_DUR:
                        fixation_ok = True
                        break
                else:
                    fix0 = None
                core.wait(0.003)

            if not manual_skip:
                if not fixation_ok:
                    _log("TIMEOUT dla punktu %d (%.1fs)", idx, CALIB_TIMEOUT)

                # zbieranie danych kalibracyjnych
                _log("collect_data dla punktu %d", idx)
                for rep in range(CALIB_MAX_RETRIES + 1):
                    try:
                        st = calib.collect_data(cx, cy)
                        _log("collect_data rep%d → %s", rep, st)
                        if st == tr.CALIBRATION_STATUS_SUCCESS:
                            break
                    except Exception as e:
                        _log("collect_data rep%d WYJĄTEK: %s", rep, e)
                    core.wait(0.3)
        else:
            core.wait(0.25)

    # ── Obliczanie i stosowanie kalibracji ────────────────────────────────────
    if tracker_on and calib is not None:
        _log("Obliczanie i stosowanie kalibracji …")
        res = None
        try:
            res = calib.compute_and_apply()
            _log("compute_and_apply → %s", res.status)
            calib.leave_calibration_mode()
        except Exception as e:
            _log("compute_and_apply BŁĄD: %s", e)
            _log_exc("Szczegóły błędu kalibracji")
            try:
                calib.leave_calibration_mode()
            except Exception:
                pass

        # ── Wizualizacja próbek kalibracyjnych ───────────────────────────────
        if res is not None:
            # Oblicz średnią dyspersję
            ds_means = []
            for cp in res.calibration_points:
                tx, ty = cp.position_on_display_area
                dists  = []
                for samp in cp.calibration_samples:
                    if samp.left_eye.validity.endswith("valid_and_used"):
                        lx, ly = samp.left_eye.position_on_display_area
                        dists.append(math.hypot(lx - tx, ly - ty))
                    if samp.right_eye.validity.endswith("valid_and_used"):
                        rx, ry = samp.right_eye.position_on_display_area
                        dists.append(math.hypot(rx - tx, ry - ty))
                if dists:
                    ds_means.append(sum(dists) / len(dists))
            avg_disp = sum(ds_means) / len(ds_means) if ds_means else float("nan")
            _log("Średnia dyspersja kalibracji = %.4f (jednostki norm.)", avg_disp)

            # Rysuj literę: czerwona jeśli punkt kalibracji, szara pozostałe
            win.color = BG_COLOR
            win.flip(clearBuffer=True)

            for idx2, (ch, x, y, em, _) in enumerate(letter_info):
                is_calib = idx2 in best_letters
                visual.TextStim(
                    win, text=ch, font=FONT, height=FSIZE,
                    color=RED if is_calib else GRAY,
                    bold=is_calib,
                    pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
                ).draw()

            # Nałóż zielone kółka = próbki wzroku
            for cp in res.calibration_points:
                for samp in cp.calibration_samples:
                    coords = []
                    if samp.left_eye.validity.endswith("valid_and_used"):
                        coords.append(samp.left_eye.position_on_display_area)
                    if samp.right_eye.validity.endswith("valid_and_used"):
                        coords.append(samp.right_eye.position_on_display_area)
                    if not coords:
                        continue
                    gx = sum(c[0] for c in coords) / len(coords)
                    gy = sum(c[1] for c in coords) / len(coords)
                    visual.Circle(
                        win, radius=6, edges=16,
                        fillColor=GREEN, lineColor=GREEN,
                        pos=(gx * SCR_W - SCR_W / 2, SCR_H / 2 - gy * SCR_H)
                    ).draw()

            visual.TextStim(
                win, text="Dyspersja: {:.4f}  |  SPACJA = kontynuuj  |  ESC = przerwij".format(avg_disp),
                font=FONT, height=28, color=[-1, -1, -1], bold=True,
                pos=(0, -SCR_H / 2 + 50)
            ).draw()
            win.flip()

            _log("Oczekiwanie na SPACJĘ (max 20 s) …")
            event.clearEvents(eventType="keyboard")
            t_wait = core.getTime()
            while core.getTime() - t_wait < 20.0:
                if event.getKeys(keyList=["space", "escape"]):
                    break
                core.wait(0.05)
                if abort_if_escape():
                    break

    # ── Sprzątanie ────────────────────────────────────────────────────────────
    for stim in letter_stims:
        stim.autoDraw = False
    win.color = BG_COLOR
    win.flip(clearBuffer=True)
    _log(">>> KALIBRACJA: zakończona")


# ── Uruchomienie kalibracji ───────────────────────────────────────────────────
try:
    perform_calibration()
except Exception as e:
    _log("KRYTYCZNY BŁĄD kalibracji: %s", e)
    _log_exc("Szczegóły błędu kalibracji")
    try:
        win.color = BG_COLOR
        win.flip(clearBuffer=True)
        visual.TextStim(
            win,
            text="Kalibracja zakończyła się błędem.\nSprawdź badanie_debug.log.\n\nESC = wyjście",
            font=FONT, height=30, color=[-1, -1, -1],
            alignText="center", wrapWidth=(BR[0] - TL[0]) * SCR_W
        ).draw()
        win.flip()
        event.waitKeys(keyList=["escape"])
    except Exception:
        pass
    ABORT = True


# ─────────────────────────────────────────────────────────────────────────────
#  PRÓBY (TRIALS)
# ─────────────────────────────────────────────────────────────────────────────
if not ABORT:
    # Krzyżyk fiksacyjny — pozycja z pierwszego centroidu recenzji kalibracyjnej
    fx_rel = calibration_review["word_centroids"][0]["centroids"][0]
    fx_x   = fx_rel[0] * SCR_W - SCR_W / 2
    fx_y   = SCR_H / 2 - fx_rel[1] * SCR_H

    h_line = visual.Line(win, start=(fx_x - 30, fx_y), end=(fx_x + 30, fx_y),
                         lineColor=[-1, -1, -1], lineWidth=5)
    v_line = visual.Line(win, start=(fx_x, fx_y - 30), end=(fx_x, fx_y + 30),
                         lineColor=[-1, -1, -1], lineWidth=5)

    sel         = random.sample(trial_reviews, N_TRIALS)
    n_tot       = 0
    n_cor       = 0
    trial_results = []

    for t_idx, rec in enumerate(sel, start=1):
        if abort_if_escape():
            break

        rid    = rec["id"]
        try:
            rating = int(float(rec["rating"]))
        except (ValueError, TypeError):
            pylog.error("Nieprawidłowy rating dla ID=%s, domyślnie 3", rid)
            rating = 3

        words = [w["word"] for w in rec["word_centroids"]]
        _log("Próba %d – recenzja %s (ocena=%d)", t_idx, rid, rating)

        # ── Krzyżyk fiksacyjny ────────────────────────────────────────────────
        visual.Rect(
            win=win, width=SCR_W * 2, height=SCR_H * 2, units="pix",
            fillColor=[-1, -1, -1], lineColor=None, opacity=0.05
        ).draw()
        h_line.draw()
        v_line.draw()
        win.flip()

        t0 = core.getTime()
        while True:
            if abort_if_escape():
                break
            elapsed = core.getTime() - t0
            if elapsed >= FIX_TIMEOUT:
                _log("Timeout fiksacji (%.1fs)", FIX_TIMEOUT)
                break
            if elapsed >= FIX_DUR:
                if TOBII["connected"] and last_gaze["valid"]:
                    dx = last_gaze["x"] - fx_rel[0]
                    dy = last_gaze["y"] - fx_rel[1]
                    if math.hypot(dx, dy) <= FIX_TOL:
                        break
                else:
                    break
            core.wait(0.005)

        if ABORT:
            break

        # ── Prezentacja tekstu recenzji ───────────────────────────────────────
        box_w = (BR[0] - TL[0]) * SCR_W
        tlx   = TL[0] * SCR_W
        tly   = TL[1] * SCR_H

        lines, cur, acc = [], [], 0
        for w in words:
            wpx = sum(gw(c) for c in w) + space_adv
            if cur and acc + wpx > box_w:
                lines.append(cur)
                cur, acc = [w], wpx
            else:
                cur.append(w)
                acc += wpx
        if cur:
            lines.append(cur)

        visual.Rect(
            win=win, width=SCR_W * 2, height=SCR_H * 2, units="pix",
            fillColor=[-1, -1, -1], lineColor=None, opacity=0.05
        ).draw()

        for row, line_words in enumerate(lines):
            y = tly + row * line_h
            x = tlx
            for w in line_words:
                for ch in w:
                    em = gw(ch)
                    visual.TextStim(
                        win, text=ch, font=FONT, height=FSIZE,
                        color=[-1, -1, -1],
                        pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
                    ).draw()
                    x += em
                x += space_adv
        win.flip()

        push_event(1.0, float(rid), float(rating), float(t_idx))

        # ── Odpowiedź uczestnika ──────────────────────────────────────────────
        key = event.waitKeys(keyList=["left", "right", "escape"])[0]
        if key == "escape":
            abort_if_escape()
            break

        n_tot += 1
        correct = (
            (key == "left"  and rating not in (4, 5)) or
            (key == "right" and rating not in (1, 2))
        )
        n_cor += int(correct)
        trial_results.append(correct)
        push_event(2.0, 0.0 if key == "left" else 1.0)
        _log("Próba %d: %s (poprawna=%s)", t_idx, key, correct)

    # ── Ekran końcowy ─────────────────────────────────────────────────────────
    if not ABORT and n_tot:
        pct = round(100 * n_cor / n_tot)
        random_correct = random.choice(trial_results)
        random_result  = "TAK" if random_correct else "NIE"

        visual.TextStim(
            win,
            text=(
                f"Twój wynik: {pct}%\n\n"
                f"Poprawna odpowiedź w wylosowanym trialu: {random_result}"
            ),
            font=FONT, height=40, color=[-1, -1, -1],
            alignText="center", wrapWidth=(BR[0] - TL[0]) * SCR_W
        ).draw()
        win.color = BG_COLOR
        win.flip()
        event.waitKeys(keyList=["escape"])
        abort_if_escape()

# ─────────────────────────────────────────────────────────────────────────────
#  ZAMKNIĘCIE
# ─────────────────────────────────────────────────────────────────────────────
_log("Sekwencja zamknięcia")

if TOBII["connected"]:
    try:
        et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, _gaze_cb)
        _log("Anulowano subskrypcję danych wzroku")
    except Exception:
        _log_exc("Błąd anulowania subskrypcji")

_stop_w.set()
_log_thread.join()
_log("Wątek zapisu binarnego zakończony")

win.close()
core.quit()

_log("Dane binarne: output/%s", os.path.basename(DATA_PATH))
if not ABORT and "n_tot" in dir() and n_tot:
    _log("Trafność: %d/%d = %.1f%%", n_cor, n_tot, 100 * n_cor / n_tot)
_log("Status Tobii: %s", TOBII)
_log("=== Badanie zakończone ===\n")

print("Dane binarne zapisane: output/" + os.path.basename(DATA_PATH))
