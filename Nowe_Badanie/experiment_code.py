# -*- coding: utf-8 -*-
"""
experiment_code.py  –  Badanie czytelności recenzji z eye-trackingiem (v2)
==========================================================================

CO NOWEGO vs poprzednia wersja:
  • Ekran zbierania danych uczestnika (ID, wiek, płeć)
  • Ekran instrukcji przed eksperymentem
  • Faza ĆWICZENIOWA (3 próby, bez wymagania fiksacji)
  • Eksport danych do CSV (obok binarnego .bin)
  • Czytelny ekran końcowy z podziękowaniem
  • Osobne plik logu CSV na uczestnika (participant_XXX.csv)

Przepływ:
  1. Ekran tytułowy
  2. Dane uczestnika (ID, wiek, płeć)
  3. Kalibracja eye-trackera
  4. Instrukcja zadania
  5. Faza ćwiczeniowa (3 losowe próby)
  6. Faza główna (N_TRIALS prób)
  7. Ekran końcowy z podziękowaniem

Sterowanie:
  ←  Lewy strzałek  = recenzja NEGATYWNA
  →  Prawy strzałek = recenzja POZYTYWNA
  ESC               = przerwij w dowolnym momencie

Wymagania:
  • PsychoPy (APP from desktop\\PsychoPy\\pythonw.exe)
  • Tobii Pro SDK (tobii_research_interop.pyd w SDK lub instalacja systemowa)
  • Pliki w tym samym folderze:
      selected_reviews_data.json
      IBMPlexMono-Regular.ttf
  • Folder ../x3-120 SDK/64/ (SDK Tobii – jeden folder wyżej, wspólny)
"""

# ─────────────────────────────────────────────────────────────────────────────
#  PARAMETRY  (nadpisywane przez config.txt)
# ─────────────────────────────────────────────────────────────────────────────
JSON_DB           = "selected_reviews_data.json"
FONT              = "IBM Plex Mono"
FSIZE             = 34
LINE_SP           = 2
TL, BR            = (0.10, 0.15), (0.92, 0.98)

FIX_DUR           = 0.60
FIX_TOL           = 0.03
FIX_TIMEOUT       = 5.0

CALIB_DUR         = 0.50
CALIB_TOL         = 0.15
CALIB_TIMEOUT     = 5.0
CALIB_MAX_RETRIES = 3

N_PRACTICE        = 3       # liczba prób ćwiczeniowych
SAVE_LIMIT        = 1000

# ─────────────────────────────────────────────────────────────────────────────
#  IMPORTY
# ─────────────────────────────────────────────────────────────────────────────
import ctypes, csv, math, os, json, random, struct, threading, queue, time, sys
import logging as pylog
from logging.handlers import RotatingFileHandler
from datetime import datetime

import pyglet
from psychopy import visual, event, core, monitors, logging

# ── ESC = natychmiastowe wyjście ──────────────────────────────────────────────
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
#  LOGGING
# ─────────────────────────────────────────────────────────────────────────────
HERE     = os.path.abspath(os.path.dirname(__file__))
LOG_PATH = os.path.join(HERE, "output", "experiment_debug.log")

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
pylog.info("=== Eksperyment v2 uruchomiony ===")


def _log_exc(msg):
    pylog.exception(msg)
    for h in pylog.root.handlers:
        h.flush()


def _log(msg, *args):
    pylog.info(msg, *args)
    for h in pylog.root.handlers:
        h.flush()


# ─────────────────────────────────────────────────────────────────────────────
#  BINARNY ZAPIS DANYCH (wątek)
# ─────────────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(HERE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _next_bin(prefix="data"):
    for i in range(SAVE_LIMIT):
        fn = os.path.join(OUTPUT_DIR, f"{prefix}{i:03d}.bin")
        if not os.path.exists(fn):
            return fn
    raise RuntimeError(f"Brak wolnych slotów dla {prefix}*.bin")


_STRUCT = struct.Struct("d7f")
_BUF_N  = 5000
_q      = queue.Queue()
_stop_w = threading.Event()
DATA_PATH = None   # zostanie ustawiony po zebraniu ID uczestnika


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
        _log_exc("Wątek zapisu binarnego uległ awarii")


def push_event(code, *params):
    ts = time.time()
    try:
        ts = tr.get_system_time_stamp() * 1e-6
    except Exception:
        pass
    vals = [float(p) for p in params]
    vals += [math.nan] * (6 - len(vals))
    _q.put((ts, float(code), *vals))


# ─────────────────────────────────────────────────────────────────────────────
#  CSV ZAPIS WYNIKÓW
# ─────────────────────────────────────────────────────────────────────────────
csv_rows   = []   # bufor wyników, zapisany na końcu
start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_csv(participant_id, age, gender):
    """Zapisuje wyniki prób do pliku CSV uczestnika."""
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(
        OUTPUT_DIR, f"participant_{participant_id}_{ts_str}.csv"
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "participant_id", "age", "gender", "session_start",
            "phase", "trial_num", "review_id", "rating",
            "response", "correct", "rt_s"
        ])
        writer.writeheader()
        for row in csv_rows:
            row["participant_id"] = participant_id
            row["age"]            = age
            row["gender"]         = gender
            row["session_start"]  = start_time
            writer.writerow(row)
    _log("CSV zapisany: %s", csv_path)
    return csv_path


# ─────────────────────────────────────────────────────────────────────────────
#  TOBII X3-120
# ─────────────────────────────────────────────────────────────────────────────
# Szukaj SDK lokalnie (jeden folder wyżej) lub w systemie
X3_SDK_PATH = os.path.join(HERE, "..", "x3-120 SDK", "64")
X3_SDK_PATH = os.path.normpath(X3_SDK_PATH)
if os.path.exists(X3_SDK_PATH) and X3_SDK_PATH not in sys.path:
    sys.path.insert(0, X3_SDK_PATH)
    _log("Dodano X3-120 SDK do ścieżki: %s", X3_SDK_PATH)

TOBII = {"connected": False, "error": None}
et    = None

try:
    import tobii_research as tr
    _log("Tobii SDK załadowany: %s", tr.__version__)
    trackers = tr.find_all_eyetrackers()
    if trackers:
        et = trackers[0]
        _log("Połączono: %s S/N=%s", et.model, et.serial_number)
        avail = et.get_all_gaze_output_frequencies()
        freq  = 120.0 if 120.0 in avail else max(avail, default=60.0)
        et.set_gaze_output_frequency(freq)
        _log("Częstotliwość: %s Hz", freq)
        time.sleep(0.1)
        TOBII.update(connected=True, serial=et.serial_number,
                     model=et.model, freq=freq)
    else:
        _log("Brak eye-trackera — tryb bez trackera")
except Exception as exc:
    _log_exc("Błąd inicjalizacji Tobii")
    TOBII["error"] = str(exc)
    print(f"\nBŁĄD Tobii: {exc}\nUruchom debug_import.py\n")

# ─────────────────────────────────────────────────────────────────────────────
#  WCZYTANIE DANYCH I KONFIGURACJI
# ─────────────────────────────────────────────────────────────────────────────
pyglet.font.add_file(os.path.join(HERE, "IBMPlexMono-Regular.ttf"))
logging.console.setLevel(logging.ERROR)

with open(os.path.join(HERE, JSON_DB), encoding="utf-8") as fh:
    db = json.load(fh)

CONFIG_FILE = os.path.join(HERE, "config.txt")

# Parametry z wartościami domyślnymi
CALIBRATION_REVIEW_ID = db[0]["id"]
N_TRIALS              = "ALL"
BG_BRIGHTNESS         = 0.95

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as cf:
        cf.write(
            "# Konfiguracja eksperymentu v2\n#\n"
            f"CALIBRATION_REVIEW_ID={db[0]['id']}\n"
            "N_TRIALS=ALL\n"
            "BG_BRIGHTNESS=0.95\n"
            "FIXATION_TOLERANCE=0.03\n"
            "FIXATION_DURATION=0.6\n"
        )
    _log("Utworzono config.txt")

try:
    with open(CONFIG_FILE, encoding="utf-8") as cf:
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
                    pass
            elif key == "N_TRIALS":
                N_TRIALS = "ALL" if val.upper() in ("ALL", "") else max(1, int(val))
            elif key == "BG_BRIGHTNESS":
                BG_BRIGHTNESS = max(0.0, min(1.0, float(val)))
            elif key == "FIXATION_TOLERANCE":
                FIX_TOL = max(0.01, min(0.2, float(val)))
            elif key == "FIXATION_DURATION":
                FIX_DUR = max(0.1, min(5.0, float(val)))
except Exception as e:
    _log("Błąd config.txt: %s — domyślne wartości", e)

BG_COLOR = [BG_BRIGHTNESS * 2 - 1] * 3

calibration_review = None
trial_reviews      = []
for review in db:
    if review["id"] == CALIBRATION_REVIEW_ID:
        calibration_review = review
    else:
        trial_reviews.append(review)

if calibration_review is None:
    calibration_review = db[0]
    trial_reviews      = db[1:]

total_available = len(trial_reviews)
if N_TRIALS == "ALL":
    N_TRIALS = total_available
else:
    N_TRIALS = min(N_TRIALS, total_available)

_log("Kalibracja: ID=%s | Pula prób: %d | N_TRIALS=%d",
     calibration_review["id"], total_available, N_TRIALS)

# ─────────────────────────────────────────────────────────────────────────────
#  OKNO PSYCHOPY
# ─────────────────────────────────────────────────────────────────────────────
mon = monitors.Monitor("scr")
mon.setSizePix((1920, 1080))
mon.save()

win = visual.Window(
    size=(1920, 1080), fullscr=True, monitor=mon,
    units="pix", color=BG_COLOR, screen=0
)
win.mouseVisible = False
SCR_W, SCR_H = win.size

pyglet.font.load(FONT, FSIZE)
_FONT    = pyglet.font.load(FONT, FSIZE)
space_adv = None  # inicjalizowane poniżej po załadowaniu czcionki


def gw(ch):
    try:
        glyphs = _FONT.get_glyphs(ch)
        return glyphs[0].advance if glyphs else FSIZE * 0.6
    except Exception:
        return FSIZE * 0.6


space_adv = gw(" ")
line_h    = FSIZE * LINE_SP

# ─────────────────────────────────────────────────────────────────────────────
#  POMOCNICZE FUNKCJE WYŚWIETLANIA
# ─────────────────────────────────────────────────────────────────────────────
ABORT = False


def abort_if_escape():
    global ABORT
    if not ABORT and event.getKeys(["escape"]):
        ABORT = True
        _log("Przerwanie ESC")
    return ABORT


def show_text_screen(text, wait_key=("space",), key_hint="SPACJA = dalej"):
    """Wyświetla ekran z wyśrodkowanym tekstem i czeka na klawisz."""
    win.color = BG_COLOR
    visual.TextStim(
        win, text=text, font=FONT, height=36, color=[-1, -1, -1],
        alignText="center", wrapWidth=SCR_W * 0.75
    ).draw()
    if key_hint:
        visual.TextStim(
            win, text=key_hint, font=FONT, height=26, color=[0.2, 0.2, 0.2],
            pos=(0, -SCR_H / 2 + 60)
        ).draw()
    win.flip()
    event.clearEvents(eventType="keyboard")
    key = event.waitKeys(keyList=list(wait_key) + ["escape"])
    if key and "escape" in key:
        abort_if_escape()
    return key[0] if key else None


def collect_text_input(prompt, max_len=20, allowed=None):
    """
    Ekran tekstowy z wpisywaną odpowiedzią uczestnika.
    Zwraca wpisany tekst po naciśnięciu Enter.
    """
    text_buf = ""
    while True:
        win.color = BG_COLOR
        visual.TextStim(
            win, text=prompt, font=FONT, height=38, color=[-1, -1, -1],
            alignText="center", pos=(0, 80), wrapWidth=SCR_W * 0.75
        ).draw()
        # pole odpowiedzi
        display = text_buf + "|"
        visual.TextStim(
            win, text=display, font=FONT, height=42, color=[-0.6, -0.6, 0.8],
            alignText="center", pos=(0, -40)
        ).draw()
        visual.TextStim(
            win, text="Enter = zatwierdź  |  Backspace = usuń",
            font=FONT, height=24, color=[0.2, 0.2, 0.2],
            pos=(0, -SCR_H / 2 + 60)
        ).draw()
        win.flip()

        keys = event.waitKeys(
            keyList=(
                [str(i) for i in range(10)]
                + list("abcdefghijklmnopqrstuvwxyz")
                + ["backspace", "return", "escape", "space",
                   "period", "minus", "underscore"]
            )
        )
        if not keys:
            continue
        k = keys[0]
        if k == "escape":
            abort_if_escape()
            return ""
        elif k == "return":
            if text_buf:
                return text_buf
        elif k == "backspace":
            text_buf = text_buf[:-1]
        elif k == "space":
            if len(text_buf) < max_len:
                text_buf += " "
        else:
            if len(text_buf) < max_len:
                if allowed is None or k in allowed:
                    text_buf += k
    return text_buf


# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACK WZROKU
# ─────────────────────────────────────────────────────────────────────────────
last_gaze  = {"valid": False, "x": math.nan, "y": math.nan}
_gaze_ctr  = 0
_LOG_EVERY = 120

if TOBII["connected"]:
    def _gaze_cb(g):
        global _gaze_ctr
        try:
            lx = ly = rx = ry = lp = rp = math.nan
            valid = False
            if g["left_gaze_point_validity"]:
                lx, ly = g["left_gaze_point_on_display_area"]
                valid  = True
            if g["right_gaze_point_validity"]:
                rx, ry = g["right_gaze_point_on_display_area"]
                valid  = True
            if g["left_pupil_validity"]:
                lp = g["left_pupil_diameter"]
            if g["right_pupil_validity"]:
                rp = g["right_pupil_diameter"]
            push_event(0.0, lx, ly, rx, ry, lp, rp)
            if _gaze_ctr % _LOG_EVERY == 0:
                pylog.info("Wzrok #%d valid=%s L=(%.3f,%.3f)",
                           _gaze_ctr, valid, lx, ly)
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
    """5-punktowa kalibracja na tekście recenzji kalibracyjnej."""
    _log(">>> KALIBRACJA start")
    if abort_if_escape():
        return

    words_plain = [w["word"] for w in calibration_review["word_centroids"]]
    box_w = (BR[0] - TL[0]) * SCR_W
    tlx   = TL[0] * SCR_W
    tly   = TL[1] * SCR_H

    # zawijanie tekstu
    lines, cur, acc = [], [], 0
    for w in words_plain:
        adv = sum(gw(c) for c in w) + space_adv
        if cur and acc + adv > box_w:
            lines.append(cur); cur, acc = [w], adv
        else:
            cur.append(w); acc += adv
    if cur:
        lines.append(cur)

    # indeksowanie liter
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

    GRAY  = [0.4] * 3; RED = [1, -1, -1]; GREEN = [-1, 1, -1]

    letter_stims = []
    for ch, x, y, em, _ in letter_info:
        stim = visual.TextStim(
            win, text=ch, font=FONT, height=FSIZE, color=GRAY,
            pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
        )
        stim.autoDraw = True
        letter_stims.append(stim)
    win.flip()

    tracker_on = TOBII.get("connected", False)
    calib = None
    if tracker_on:
        try:
            calib = tr.ScreenBasedCalibration(et)
            calib.enter_calibration_mode()
        except Exception:
            _log_exc("Błąd trybu kalibracji")
            tracker_on = False

    # 5 punktów kalibracyjnych
    default_targets = [
        (0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)
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

    def blink(li, idx):
        letter_stims[li].color = RED; letter_stims[li].bold = True
        win.flip(); core.wait(0.20)
        letter_stims[li].color = GRAY; letter_stims[li].bold = False
        win.flip(); core.wait(0.10)
        letter_stims[li].color = RED; letter_stims[li].bold = True
        win.flip(); core.wait(0.25)

    prev_li      = None
    best_letters = []

    for idx, (nx, ny, wi, (cx, cy)) in enumerate(targets, 1):
        if abort_if_escape():
            break
        if prev_li is not None:
            letter_stims[prev_li].color = GRAY
            letter_stims[prev_li].bold  = False
            win.flip()
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
            t0 = core.getTime(); fix0 = None; fixation_ok = False
            event.clearEvents(eventType="keyboard")
            while core.getTime() - t0 < CALIB_TIMEOUT:
                if abort_if_escape():
                    break
                if event.getKeys(keyList=["space"]):
                    _log("Pkt %d pominięty (Spacja)", idx); break
                if _gaze_on_target(nx, ny, CALIB_TOL):
                    fix0 = fix0 or core.getTime()
                    if core.getTime() - fix0 >= CALIB_DUR:
                        fixation_ok = True; break
                else:
                    fix0 = None
                core.wait(0.003)
            _log("Pkt %d: fiksacja=%s", idx, fixation_ok)
            for rep in range(CALIB_MAX_RETRIES + 1):
                try:
                    st = calib.collect_data(cx, cy)
                    if st == tr.CALIBRATION_STATUS_SUCCESS:
                        break
                except Exception as e:
                    _log("collect_data rep%d: %s", rep, e)
                core.wait(0.3)
        else:
            core.wait(0.25)

    # oblicz i zastosuj kalibrację + wizualizacja
    if tracker_on and calib is not None:
        try:
            res = calib.compute_and_apply()
            _log("compute_and_apply → %s", res.status)
            calib.leave_calibration_mode()

            # wizualizacja próbek
            win.color = BG_COLOR; win.flip(clearBuffer=True)
            for idx2, (ch, x, y, em, _) in enumerate(letter_info):
                is_c = idx2 in best_letters
                visual.TextStim(
                    win, text=ch, font=FONT, height=FSIZE,
                    color=RED if is_c else GRAY, bold=is_c,
                    pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
                ).draw()
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
                        win, radius=6, edges=16, fillColor=GREEN, lineColor=GREEN,
                        pos=(gx * SCR_W - SCR_W / 2, SCR_H / 2 - gy * SCR_H)
                    ).draw()
            visual.TextStim(
                win, text="Wyniki kalibracji  |  SPACJA = kontynuuj",
                font=FONT, height=28, color=[-1, -1, -1], bold=True,
                pos=(0, -SCR_H / 2 + 50)
            ).draw()
            win.flip()
            event.clearEvents(eventType="keyboard")
            t_w = core.getTime()
            while core.getTime() - t_w < 20.0:
                if event.getKeys(keyList=["space", "escape"]):
                    break
                core.wait(0.05)
                if abort_if_escape():
                    break
        except Exception as e:
            _log("Błąd compute_and_apply: %s", e)
            _log_exc("Szczegóły")
            try:
                calib.leave_calibration_mode()
            except Exception:
                pass

    for stim in letter_stims:
        stim.autoDraw = False
    win.color = BG_COLOR; win.flip(clearBuffer=True)
    _log(">>> KALIBRACJA zakończona")


# ─────────────────────────────────────────────────────────────────────────────
#  PRÓBA (jedna)
# ─────────────────────────────────────────────────────────────────────────────
def run_trial(rec, t_idx, phase, require_fixation, fx_rel):
    """
    Wykonuje jedną próbę.
    phase            : "cwiczeniowa" | "glowna"
    require_fixation : czy wymagać fiksacji na krzyżyku
    fx_rel           : (x_norm, y_norm) pozycja krzyżyk fiksacyjnego
    Zwraca słownik z wynikami lub None jeśli przerwano.
    """
    rid    = rec["id"]
    try:
        rating = int(float(rec["rating"]))
    except (ValueError, TypeError):
        rating = 3

    words = [w["word"] for w in rec["word_centroids"]]

    # ── Krzyżyk fiksacyjny ────────────────────────────────────────────────────
    fx_x = fx_rel[0] * SCR_W - SCR_W / 2
    fx_y = SCR_H / 2 - fx_rel[1] * SCR_H
    h_ln = visual.Line(win, start=(fx_x - 30, fx_y), end=(fx_x + 30, fx_y),
                       lineColor=[-1, -1, -1], lineWidth=5)
    v_ln = visual.Line(win, start=(fx_x, fx_y - 30), end=(fx_x, fx_y + 30),
                       lineColor=[-1, -1, -1], lineWidth=5)

    visual.Rect(win=win, width=SCR_W * 2, height=SCR_H * 2, units="pix",
                fillColor=[-1, -1, -1], lineColor=None, opacity=0.05).draw()
    h_ln.draw(); v_ln.draw()
    win.flip()

    t0 = core.getTime()
    while True:
        if abort_if_escape():
            return None
        elapsed = core.getTime() - t0
        if elapsed >= FIX_TIMEOUT:
            break
        if elapsed >= FIX_DUR:
            if require_fixation and TOBII["connected"] and last_gaze["valid"]:
                if math.hypot(last_gaze["x"] - fx_rel[0],
                              last_gaze["y"] - fx_rel[1]) <= FIX_TOL:
                    break
            else:
                break
        core.wait(0.005)

    if ABORT:
        return None

    # ── Prezentacja tekstu ────────────────────────────────────────────────────
    box_w = (BR[0] - TL[0]) * SCR_W
    tlx   = TL[0] * SCR_W
    tly   = TL[1] * SCR_H

    lines, cur, acc = [], [], 0
    for w in words:
        wpx = sum(gw(c) for c in w) + space_adv
        if cur and acc + wpx > box_w:
            lines.append(cur); cur, acc = [w], wpx
        else:
            cur.append(w); acc += wpx
    if cur:
        lines.append(cur)

    visual.Rect(win=win, width=SCR_W * 2, height=SCR_H * 2, units="pix",
                fillColor=[-1, -1, -1], lineColor=None, opacity=0.05).draw()
    for row, line_words in enumerate(lines):
        y = tly + row * line_h
        x = tlx
        for w in line_words:
            for ch in w:
                em = gw(ch)
                visual.TextStim(
                    win, text=ch, font=FONT, height=FSIZE, color=[-1, -1, -1],
                    pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
                ).draw()
                x += em
            x += space_adv

    # etykieta fazy ćwiczeniowej
    if phase == "cwiczeniowa":
        visual.TextStim(
            win, text=f"ĆWICZENIE {t_idx}",
            font=FONT, height=26, color=[0.0, 0.3, 0.8], bold=True,
            pos=(0, SCR_H / 2 - 40)
        ).draw()

    win.flip()
    push_event(1.0, float(rid), float(rating), float(t_idx))

    # ── Odpowiedź ─────────────────────────────────────────────────────────────
    t_resp = core.getTime()
    key    = event.waitKeys(keyList=["left", "right", "escape"])
    rt     = round(core.getTime() - t_resp, 4)

    if not key or "escape" in key:
        abort_if_escape()
        return None

    resp    = key[0]
    correct = (
        (resp == "left"  and rating not in (4, 5)) or
        (resp == "right" and rating not in (1, 2))
    )
    push_event(2.0, 0.0 if resp == "left" else 1.0)

    # ── Informacja zwrotna (tylko faza ćwiczeniowa) ──────────────────────────
    if phase == "cwiczeniowa":
        fb_text = "Poprawnie! ✓" if correct else "Niepoprawnie ✗"
        fb_col  = [-1, 0.6, -1] if correct else [0.8, -1, -1]
        visual.TextStim(
            win, text=fb_text, font=FONT, height=50, color=fb_col, bold=True,
            pos=(0, 0)
        ).draw()
        win.color = BG_COLOR
        win.flip()
        core.wait(0.8)

    return {
        "phase":     phase,
        "trial_num": t_idx,
        "review_id": rid,
        "rating":    rating,
        "response":  resp,
        "correct":   int(correct),
        "rt_s":      rt,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GŁÓWNY PRZEBIEG EKSPERYMENTU
# ─────────────────────────────────────────────────────────────────────────────

# ── 1. Ekran tytułowy ─────────────────────────────────────────────────────────
show_text_screen(
    "BADANIE CZYTELNOŚCI RECENZJI\n\nBadanie eksperymentalne\nUniwersytet SWPS",
    key_hint="SPACJA = rozpocznij"
)
if ABORT:
    raise SystemExit

# ── 2. Dane uczestnika ────────────────────────────────────────────────────────
PARTICIPANT_ID = collect_text_input(
    "Podaj identyfikator uczestnika\n(np. inicjały + rok urodzenia):",
    max_len=10,
    allowed=list("abcdefghijklmnopqrstuvwxyz0123456789")
)
if ABORT or not PARTICIPANT_ID:
    raise SystemExit
PARTICIPANT_ID = PARTICIPANT_ID.upper()

AGE = collect_text_input(
    "Podaj swój wiek:", max_len=3,
    allowed=list("0123456789")
)
if ABORT:
    raise SystemExit

# wybór płci
show_text_screen(
    "Wybierz płeć:\n\nK  =  kobieta          M  =  mężczyzna          I  =  inna",
    wait_key=("k", "m", "i"),
    key_hint=""
)
gender_key = event.waitKeys(keyList=["k", "m", "i", "escape"])
GENDER = {"k": "kobieta", "m": "mezczyzna", "i": "inna"}.get(
    gender_key[0] if gender_key else "i", "inna"
)

_log("Uczestnik: ID=%s wiek=%s płeć=%s", PARTICIPANT_ID, AGE, GENDER)

# ── ustaw plik binarny z uczestnikiem w nazwie ────────────────────────────────
DATA_PATH = os.path.join(
    OUTPUT_DIR,
    f"data_{PARTICIPANT_ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
)
_log_thread = threading.Thread(target=_writer, daemon=False)
_log_thread.start()

# ── 3. Kalibracja ────────────────────────────────────────────────────────────
show_text_screen(
    "KALIBRACJA\n\n"
    "Za chwilę zostanie wyświetlony tekst.\n"
    "Proszę patrzeć na migające czerwone litery\n"
    "i nie ruszać głową.",
    key_hint="SPACJA = rozpocznij kalibrację"
)
if ABORT:
    raise SystemExit

try:
    perform_calibration()
except Exception as e:
    _log("Błąd kalibracji: %s", e)
    _log_exc("Szczegóły")
    show_text_screen(
        f"Błąd kalibracji.\nSprawdź plik output/experiment_debug.log\n\n{e}",
        wait_key=("escape",), key_hint=""
    )
    raise SystemExit

if ABORT:
    raise SystemExit

# ── 4. Instrukcja zadania ─────────────────────────────────────────────────────
show_text_screen(
    "INSTRUKCJA\n\n"
    "Na ekranie pojawi się recenzja produktu.\n"
    "Przeczytaj ją uważnie, a następnie oceń:\n\n"
    "←  Strzałka LEWO  =  recenzja NEGATYWNA\n"
    "→  Strzałka PRAWO =  recenzja POZYTYWNA\n\n"
    "Najpierw wykonasz 3 próby ćwiczeniowe z informacją zwrotną.",
    key_hint="SPACJA = dalej"
)
if ABORT:
    raise SystemExit

# ── 5. Faza ćwiczeniowa ───────────────────────────────────────────────────────
fx_rel = calibration_review["word_centroids"][0]["centroids"][0]

practice_pool = random.sample(trial_reviews, min(N_PRACTICE, len(trial_reviews)))
show_text_screen(
    "ĆWICZENIA\n\n3 próby ćwiczeniowe — po każdej zobaczysz wynik.",
    key_hint="SPACJA = rozpocznij"
)
if ABORT:
    raise SystemExit

for p_idx, rec in enumerate(practice_pool, 1):
    if ABORT:
        break
    result = run_trial(
        rec, p_idx, phase="cwiczeniowa",
        require_fixation=False, fx_rel=fx_rel
    )
    if result:
        csv_rows.append(result)

if ABORT:
    raise SystemExit

# ── 6. Faza główna ────────────────────────────────────────────────────────────
show_text_screen(
    "FAZA GŁÓWNA\n\n"
    f"Teraz rozpocznie się właściwa część badania ({N_TRIALS} prób).\n"
    "Informacja zwrotna nie będzie wyświetlana.\n\n"
    "Pamiętaj:\n"
    "←  LEWO  =  NEGATYWNA       →  PRAWO  =  POZYTYWNA",
    key_hint="SPACJA = rozpocznij"
)
if ABORT:
    raise SystemExit

main_pool = random.sample(trial_reviews, N_TRIALS)
n_tot = n_cor = 0

for t_idx, rec in enumerate(main_pool, 1):
    if ABORT:
        break
    result = run_trial(
        rec, t_idx, phase="glowna",
        require_fixation=True, fx_rel=fx_rel
    )
    if result:
        csv_rows.append(result)
        n_tot += 1
        n_cor += result["correct"]
        push_event(1.0, float(result["review_id"]), float(result["rating"]),
                   float(t_idx))

# ── 7. Ekran końcowy ──────────────────────────────────────────────────────────
if not ABORT and n_tot:
    pct = round(100 * n_cor / n_tot)
    random_result = "TAK" if random.choice(
        [r for r in csv_rows if r["phase"] == "glowna"]
    )["correct"] else "NIE"

    show_text_screen(
        f"DZIĘKUJEMY ZA UDZIAŁ W BADANIU!\n\n"
        f"Uczestnik: {PARTICIPANT_ID}\n"
        f"Trafność (faza główna): {pct}%\n\n"
        f"Wylosowana próba — odpowiedź poprawna: {random_result}\n\n"
        "Dane zostały zapisane.",
        wait_key=("escape", "space"),
        key_hint="ESC lub SPACJA = zakończ"
    )

# ─────────────────────────────────────────────────────────────────────────────
#  ZAPIS DANYCH I ZAMKNIĘCIE
# ─────────────────────────────────────────────────────────────────────────────
_log("Zapisywanie CSV …")
try:
    csv_out = save_csv(PARTICIPANT_ID, AGE, GENDER)
    _log("CSV: %s", csv_out)
except Exception as e:
    _log("Błąd zapisu CSV: %s", e)

if TOBII["connected"]:
    try:
        et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, _gaze_cb)
        _log("Anulowano subskrypcję gaze")
    except Exception:
        _log_exc("Błąd unsubscribe")

_stop_w.set()
_log_thread.join()
_log("Wątek zapisu binarnego zakończony")

win.close()
core.quit()

_log("Dane binarne: %s", DATA_PATH)
if not ABORT and n_tot:
    _log("Trafność: %d/%d = %.1f%%", n_cor, n_tot, 100 * n_cor / n_tot)
_log("Status Tobii: %s", TOBII)
_log("=== Eksperyment v2 zakończony ===\n")
print(f"Dane: output/  |  Uczestnik: {PARTICIPANT_ID}")
