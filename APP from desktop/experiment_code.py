# -*- coding: utf-8 -*-
"""
with_eye_tracking.py  –  Configurable trial count with eye-tracking support

• Uses FIRST review from JSON for calibration (Tobii-style: show target → wait for fixation → collect_data)
• Trials are selected from REMAINING reviews (all except first) in random order
• Reads number of trials from config.txt file (created automatically if missing)
  - Set N_TRIALS=ALL or leave empty to run all remaining reviews
  - Set N_TRIALS=25 (or any number) to run specific number of trials
• Binary data files saved to /output subdirectory (auto-created)
• Detailed binary + text logging with Tobii timestamps for every event
• Throttled gaze logging
• Early-exit on Esc
• All tunable parameters at the top

Modifications:
1. Writer thread is now joined on shutdown and has exception handling.
2. Gaze logging throttled to 1 line per 120 samples (for 120 Hz eye tracker).
3. Busy-wait loops remain but include comments on how to replace them.
4. RotatingFileHandler prevents the text log from growing without bounds.
5. Calibration-event logging now records the actual centroid.
6. Each calibration letter now blinks once in red on a gray background.
7. Raw-sample visualization: highlights only the best letter per target in its unique color and plots all gaze samples for that letter, then waits for Space.
8. After calibration, logs all CalibrationResult metrics.
9. Number of trials read from config.txt file (auto-created with defaults).
10. First review is reserved for calibration; trials use remaining reviews only.
11. Binary data files saved to /output subdirectory for better organization.
12. Robust logging with immediate flush to disk to prevent data loss on crash.
13. Timeout handling for all calibration steps to prevent infinite hangs.
14. Comprehensive error handling with try-except blocks around critical sections.
15. Added console logging in addition to file logging for real-time monitoring.
16. Configurable fixation cross tolerance and duration for better control of inter-trial fixation requirements.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  PARAMS
# ─────────────────────────────────────────────────────────────────────────────
JSON_DB              = "selected_reviews_data.json"
FONT                 = "IBM Plex Mono"
FSIZE                = 34
LINE_SP              = 2
TL, BR               = (0.12, 0.18), (0.90, 0.99)

FIX_DUR              = 0.50    # Default, overridden by config
FIX_TOL              = 0.05    # Default, overridden by config
FIX_TIMEOUT          = 5.0

CALIB_DUR            = 0.50    # Increased for X3-120 (120 Hz) to collect more samples
CALIB_TOL            = 0.15
CALIB_TIMEOUT        = 5.0
CALIB_MAX_RETRIES    = 3

SAVE_LIMIT           = 1000

# ─────────────────────────────────────────────────────────────────────────────
#  Imports + DPI Awareness
# ─────────────────────────────────────────────────────────────────────────────
import ctypes, math, os, json, random, struct, threading, queue, time
import logging as pylog
from logging.handlers import RotatingFileHandler
import pyglet
from psychopy import visual, event, core, monitors, logging

import os
from psychopy import event

# make ESC an *unconditional* kill-switch (bypasses core.quit or any handlers)
event.globalKeys.add(
    key='escape',
    func=os._exit,
    func_args=(1,)    # exit code 1
)


# Windows DPI Awareness
for fn in ("SetProcessDpiAwareness", "SetProcessDPIAware"):
    try:
        getattr(
            ctypes.windll.shcore if fn.endswith("Awareness") else ctypes.windll.user32,
            fn
        )(1)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  Logging setup (rotating, 5 MB × 5)
# ─────────────────────────────────────────────────────────────────────────────
HERE     = os.path.abspath(os.path.dirname(__file__))
LOG_PATH = os.path.join(HERE, "experiment_debug.log")

_rot = RotatingFileHandler(
    LOG_PATH, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
)
_rot.setFormatter(pylog.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
))
# Add console handler for immediate visibility
_console = pylog.StreamHandler()
_console.setFormatter(pylog.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
))
pylog.basicConfig(level=pylog.INFO, handlers=[_rot, _console])
pylog.info("=== Script started ===")

def _log_exc(msg): 
    pylog.exception(msg)
    for handler in pylog.root.handlers:
        handler.flush()

def _log_and_flush(msg, *args):
    """Log with immediate flush to ensure message is written."""
    pylog.info(msg, *args)
    for handler in pylog.root.handlers:
        handler.flush()

# ─────────────────────────────────────────────────────────────────────────────
#  Binary gaze/event logger with safe shutdown
# ─────────────────────────────────────────────────────────────────────────────
# Create output directory if it doesn't exist
OUTPUT_DIR = os.path.join(HERE, "output")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    pylog.info(f"Created output directory: {OUTPUT_DIR}")

def _next_bin():
    for i in range(SAVE_LIMIT):
        fn = os.path.join(OUTPUT_DIR, f"data{i:03d}.bin")
        if not os.path.exists(fn):
            return fn
    raise RuntimeError("All data000–data999 exist")

DATA_PATH = _next_bin()
_STRUCT   = struct.Struct("d7f")
_BUF_N    = 5000
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
        _log_exc("Writer thread crashed")

_log_thread = threading.Thread(target=_writer, daemon=False)
_log_thread.start()

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
#  Tobii eye-tracker connection
# ─────────────────────────────────────────────────────────────────────────────
# Add X3-120 SDK to Python path (use local SDK instead of system installation)
import sys
X3_SDK_PATH = os.path.join(HERE, "x3-120 SDK", "64")
if os.path.exists(X3_SDK_PATH) and X3_SDK_PATH not in sys.path:
    sys.path.insert(0, X3_SDK_PATH)
    pylog.info(f"Added X3-120 SDK to path: {X3_SDK_PATH}")

TOBII = {"connected": False, "error": None}
et = None
try:
    import tobii_research as tr
    trackers = tr.find_all_eyetrackers()
    if trackers:
        et = trackers[0]
        pylog.info("Connected to %s (%s)", et.serial_number, et.model)
        
        # Set frequency - prefer 120 Hz for X3-120, or use highest available
        available_freqs = et.get_all_gaze_output_frequencies()
        pylog.info("Available frequencies: %s", available_freqs)
        
        if 120.0 in available_freqs:
            et.set_gaze_output_frequency(120.0)
            pylog.info("Set frequency to 120 Hz (X3-120 native)")
        elif available_freqs:
            target_freq = max(available_freqs)
            et.set_gaze_output_frequency(target_freq)
            pylog.info("Set frequency to %s Hz (highest available)", target_freq)
        time.sleep(0.1)
        
        TOBII.update(
            connected=True,
            serial=et.serial_number,
            model=et.model,
            freq=et.get_gaze_output_frequency(),
        )
    else:
        pylog.warning("No eye-tracker found")
except Exception as exc:
    _log_exc("Error initializing Tobii eye-tracker")
    TOBII["error"] = str(exc)

# ─────────────────────────────────────────────────────────────────────────────
#  PsychoPy window & fonts
# ─────────────────────────────────────────────────────────────────────────────
pyglet.font.add_file(os.path.join(HERE, "IBMPlexMono-Regular.ttf"))
logging.console.setLevel(logging.ERROR)

with open(os.path.join(HERE, JSON_DB), encoding="utf-8") as fh:
    db = json.load(fh)

# Read configuration from config file
CONFIG_FILE = os.path.join(HERE, "config.txt")

# Create default config if it doesn't exist
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as cf:
        cf.write(f"# Configuration file for experiment_code.py\n")
        cf.write(f"# \n")
        cf.write(f"# Review ID to use for calibration\n")
        cf.write(f"# Specify the exact review ID from the JSON file\n")
        cf.write(f"# This review will be excluded from the trial pool\n")
        cf.write(f"#\n")
        cf.write(f"CALIBRATION_REVIEW_ID={db[0]['id']}\n\n")
        cf.write(f"# Number of trials to run from the available reviews\n")
        cf.write(f"# (Calibration review is excluded from trials)\n")
        cf.write(f"#\n")
        cf.write(f"# Options:\n")
        cf.write(f"#   N_TRIALS=ALL    - Run all available reviews (default)\n")
        cf.write(f"#   N_TRIALS=25     - Run 25 random trials\n")
        cf.write(f"#   N_TRIALS=50     - Run 50 random trials\n")
        cf.write(f"#   etc.\n")
        cf.write(f"#\n")
        cf.write(f"# Trials are always selected in RANDOM order from remaining reviews\n\n")
        cf.write(f"N_TRIALS=ALL\n\n")
        cf.write(f"# Background brightness (0 = black, 1 = white)\n")
        cf.write(f"# Recommended: 0.95 for comfortable reading\n")
        cf.write(f"#\n")
        cf.write(f"BG_BRIGHTNESS=0.95\n\n")
        cf.write(f"# Fixation cross tolerance (distance from center, as fraction of screen)\n")
        cf.write(f"# Smaller values = stricter fixation required\n")
        cf.write(f"# Recommended range: 0.025 - 0.04 (2.5% - 4% of screen)\n")
        cf.write(f"# Default was 0.05 (too liberal), new default: 0.03\n")
        cf.write(f"#\n")
        cf.write(f"FIXATION_TOLERANCE=0.03\n\n")
        cf.write(f"# Fixation duration required (seconds)\n")
        cf.write(f"# How long subject must maintain gaze on fixation cross\n")
        cf.write(f"# Recommended range: 0.5 - 0.8 seconds\n")
        cf.write(f"# Default was 0.50s, new default: 0.6s\n")
        cf.write(f"#\n")
        cf.write(f"FIXATION_DURATION=0.6\n")
    pylog.info(f"Created default config file: {CONFIG_FILE}")

# Read config file for calibration review ID, N_TRIALS, BG_BRIGHTNESS, and fixation parameters
CALIBRATION_REVIEW_ID = db[0]['id']  # Default to first review
N_TRIALS = None  # Will be set after we know trial pool size
BG_BRIGHTNESS = 0.95  # Default: light gray for comfortable reading

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as cf:
        for line in cf:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            
            if line.startswith("CALIBRATION_REVIEW_ID="):
                value = line.split("=", 1)[1].strip()
                try:
                    CALIBRATION_REVIEW_ID = int(value)
                    pylog.info(f"Config: Calibration review ID = {CALIBRATION_REVIEW_ID}")
                except ValueError:
                    pylog.warning(f"Invalid CALIBRATION_REVIEW_ID '{value}', using first review")
                    CALIBRATION_REVIEW_ID = db[0]['id']
            
            elif line.startswith("N_TRIALS="):
                value = line.split("=", 1)[1].strip()
                if value.upper() == "ALL" or value == "":
                    N_TRIALS = "ALL"
                else:
                    try:
                        N_TRIALS = int(value)
                        if N_TRIALS <= 0:
                            pylog.warning(f"Invalid N_TRIALS={N_TRIALS}, using ALL")
                            N_TRIALS = "ALL"
                    except ValueError:
                        pylog.warning(f"Invalid N_TRIALS value '{value}', using ALL")
                        N_TRIALS = "ALL"
            
            elif line.startswith("BG_BRIGHTNESS="):
                value = line.split("=", 1)[1].strip()
                try:
                    BG_BRIGHTNESS = float(value)
                    if BG_BRIGHTNESS < 0 or BG_BRIGHTNESS > 1:
                        pylog.warning(f"BG_BRIGHTNESS={BG_BRIGHTNESS} out of range [0,1], clamping")
                        BG_BRIGHTNESS = max(0, min(1, BG_BRIGHTNESS))
                    pylog.info(f"Config: Background brightness = {BG_BRIGHTNESS}")
                except ValueError:
                    pylog.warning(f"Invalid BG_BRIGHTNESS value '{value}', using default 0.95")
                    BG_BRIGHTNESS = 0.95
            
            elif line.startswith("FIXATION_TOLERANCE="):
                value = line.split("=", 1)[1].strip()
                try:
                    FIX_TOL = float(value)
                    if FIX_TOL < 0.01 or FIX_TOL > 0.2:
                        pylog.warning(f"FIXATION_TOLERANCE={FIX_TOL} out of reasonable range [0.01,0.2], clamping")
                        FIX_TOL = max(0.01, min(0.2, FIX_TOL))
                    pylog.info(f"Config: Fixation tolerance = {FIX_TOL}")
                except ValueError:
                    pylog.warning(f"Invalid FIXATION_TOLERANCE value '{value}', using default 0.03")
            
            elif line.startswith("FIXATION_DURATION="):
                value = line.split("=", 1)[1].strip()
                try:
                    FIX_DUR = float(value)
                    if FIX_DUR < 0.1 or FIX_DUR > 5.0:
                        pylog.warning(f"FIXATION_DURATION={FIX_DUR} out of reasonable range [0.1,5.0], clamping")
                        FIX_DUR = max(0.1, min(5.0, FIX_DUR))
                    pylog.info(f"Config: Fixation duration = {FIX_DUR}s")
                except ValueError:
                    pylog.warning(f"Invalid FIXATION_DURATION value '{value}', using default 0.6s")
except Exception as e:
    pylog.error(f"Error reading config file: {e}, using defaults")
    CALIBRATION_REVIEW_ID = db[0]['id']
    N_TRIALS = "ALL"
    BG_BRIGHTNESS = 0.95

# Convert BG_BRIGHTNESS (0-1) to PsychoPy color range (-1 to 1)
BG_COLOR = [BG_BRIGHTNESS * 2 - 1] * 3
pylog.info(f"Background color set to {BG_COLOR} (brightness={BG_BRIGHTNESS})")

# Separate calibration review from trial reviews based on ID
calibration_review = None
trial_reviews = []

for review in db:
    if review['id'] == CALIBRATION_REVIEW_ID:
        calibration_review = review
    else:
        trial_reviews.append(review)

# Verify we found the calibration review
if calibration_review is None:
    pylog.warning(f"Calibration review ID {CALIBRATION_REVIEW_ID} not found, using first review")
    calibration_review = db[0]
    trial_reviews = db[1:]
    CALIBRATION_REVIEW_ID = db[0]['id']

pylog.info(f"Using review {CALIBRATION_REVIEW_ID} for calibration")
pylog.info(f"Trial pool contains {len(trial_reviews)} reviews")

# Now set N_TRIALS based on available trial reviews
total_available = len(trial_reviews)
if N_TRIALS == "ALL":
    N_TRIALS = total_available
    pylog.info(f"Config: Running ALL {N_TRIALS} trials")
else:
    if N_TRIALS > total_available:
        pylog.warning(f"N_TRIALS={N_TRIALS} exceeds available {total_available}, using all")
        N_TRIALS = total_available
    else:
        pylog.info(f"Config: Running {N_TRIALS} trials")

# Set monitor index (0 = primary, 1 = secondary, etc.)
# Changed to 0 (primary screen) for compatibility
SCREEN_INDEX = 0

mon = monitors.Monitor("scr")
mon.setSizePix((1920, 1080))
mon.save()

# Create a window on the specified screen
win = visual.Window(
    size=(1920, 1080),
    fullscr=True,
    monitor=mon,
    units="pix",
    color=BG_COLOR,
    screen=SCREEN_INDEX #brightness
)

# Hide mouse cursor to reduce distraction
win.mouseVisible = False

# Store screen resolution
SCR_W, SCR_H = win.size

pyglet.font.load(FONT, FSIZE)
_FONT = pyglet.font.load(FONT, FSIZE)

# Robust glyph width function with fallback for missing characters
def gw(ch):
    """Get glyph advance width for a character, with fallback for missing glyphs."""
    try:
        glyphs = _FONT.get_glyphs(ch)
        if glyphs:
            return glyphs[0].advance
        else:
            # Fallback: use average character width
            pylog.warning(f"Missing glyph for character '{ch}' (U+{ord(ch):04X}), using fallback")
            return FSIZE * 0.6  # Approximate monospace width
    except Exception as e:
        pylog.error(f"Error getting glyph for '{ch}': {e}, using fallback")
        return FSIZE * 0.6

space_adv, line_h = gw(" "), FSIZE * LINE_SP

# ─────────────────────────────────────────────────────────────────────────────
#  Early-exit helper
# ─────────────────────────────────────────────────────────────────────────────
ABORT = False
def abort_if_escape():
    global ABORT
    if not ABORT and event.getKeys(["escape"]):
        ABORT = True
        pylog.info("Early-exit requested (Esc)")
    return ABORT

# ─────────────────────────────────────────────────────────────────────────────
#  Gaze data callback (frequency depends on eye tracker model)
# ─────────────────────────────────────────────────────────────────────────────
last_gaze = {"valid": False, "x": math.nan, "y": math.nan}
_ctr = 0
_log_interval = 120  # Log every second at 120 Hz (adjust if different frequency)
if TOBII["connected"]:
    def _gaze_cb(g):
        global _ctr
        try:
            lx=ly=rx=ry=lp=rp=math.nan; valid=False
            if g["left_gaze_point_validity"]:
                lx,ly=g["left_gaze_point_on_display_area"]; valid=True
            if g["right_gaze_point_validity"]:
                rx,ry=g["right_gaze_point_on_display_area"]; valid=True
            if g["left_pupil_validity"]: lp=g["left_pupil_diameter"]
            if g["right_pupil_validity"]: rp=g["right_pupil_diameter"]
            push_event(0.0, lx, ly, rx, ry, lp, rp)
            if _ctr % _log_interval == 0:
                pylog.info(f"Gaze #{_ctr} valid={valid} L=({lx:.3f},{ly:.3f}) R=({rx:.3f},{ry:.3f})")
            _ctr += 1
            if valid:
                gx,gy = (lx,ly) if not math.isnan(lx) else (rx,ry)
                last_gaze.update(valid=True, x=gx, y=gy)
            else:
                last_gaze["valid"] = False
        except Exception:
            _log_exc("Exception inside gaze callback")
    et.subscribe_to(tr.EYETRACKER_GAZE_DATA, _gaze_cb, as_dictionary=True)
    pylog.info("Subscribed to gaze data stream")

# ─────────────────────────────────────────────────────────────────────────────
#  Calibration
# ─────────────────────────────────────────────────────────────────────────────
def _gaze_on_target(nx, ny, tol):
    if not last_gaze["valid"]:
        return False
    return math.hypot(last_gaze["x"]-nx, last_gaze["y"]-ny) <= tol


def perform_calibration():
    """
    Fast-blink five-point calibration with verbose debug logging.

    • Red highlight remains until the next target; previous target is cleared
      when the new one begins.
    • Runs tracker-only logic (fixation, collect, quality screen) **only**
      when a Tobii is actually connected, so it cannot stall in no-tracker
      mode.
    • Every logical step logs to `pylog.info()`, making it trivial to see
      where execution stops if it does stall.
    • Includes timeouts and error handling to prevent hangs.
    """
    _log_and_flush(">>> CALIBRATION: start")

    # abort shortcut ---------------------------------------------------------
    if abort_if_escape():
        _log_and_flush(">>> CALIBRATION: aborted immediately (ESC)")
        return

    # layout -----------------------------------------------------------------
    _log_and_flush("layout: using calibration review")
    calib_review = calibration_review  # Use the first review from JSON
    words_plain = [w["word"] for w in calib_review["word_centroids"]]

    box_w = (BR[0] - TL[0]) * SCR_W
    tlx, tly = TL[0] * SCR_W, TL[1] * SCR_H
    lines, cur, acc = [], [], 0
    for w in words_plain:
        adv = sum(gw(c) for c in w) + space_adv
        if cur and acc + adv > box_w:
            lines.append(cur); cur, acc = [w], adv
        else:
            cur.append(w); acc += adv
    if cur:
        lines.append(cur)
    pylog.info(f"layout: wrapped into {len(lines)} line(s)")

    # index letters ----------------------------------------------------------
    pylog.info("layout: indexing letters …")
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
            x += space_adv; w_idx += 1
    for li, (_, _, _, _, wi) in enumerate(letter_info):
        w2idx.setdefault(wi, []).append(li)
    pylog.info(f"layout: total letters = {len(letter_info)}")

    # stimuli ----------------------------------------------------------------
    pylog.info("stimuli: building TextStim objects …")
    gray, red, green = [0.4] * 3, [1, -1, -1], [-1, 1, -1]
    letter_stims = []
    for ch, x, y, em, _ in letter_info:
        stim = visual.TextStim(
            win, text=ch, font=FONT, height=FSIZE, color=gray,
            pos=(x - SCR_W / 2 + em / 2, SCR_H / 2 - y - FSIZE / 2)
        )
        stim.autoDraw = True
        letter_stims.append(stim)
    win.flip()
    pylog.info("stimuli: first grey frame shown")

    # tracker setup ----------------------------------------------------------
    tracker_on = TOBII.get("connected", False)
    if tracker_on:
        pylog.info("tracker: Tobii detected → entering calibration mode")
        calib = tr.ScreenBasedCalibration(et)
        try:
            status = calib.enter_calibration_mode()
            pylog.info(f"tracker: enter_calibration_mode → {status}")
        except Exception:
            _log_exc("tracker: enter_calibration_mode failed – disabling tracker path")
            tracker_on = False
    else:
        pylog.info("tracker: no Tobii, running no-tracker path")

    # choose five default targets -------------------------------------------
    defaults = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1),
                (0.1, 0.9), (0.9, 0.9)]
    targets = []
    pylog.info("targets: mapping to nearest letters …")
    for nx, ny in defaults:
        best, pick = float("inf"), None
        for wi, wdat in enumerate(calib_review["word_centroids"]):
            for li, (cx, cy) in enumerate(wdat["centroids"]):
                if not wdat["word"][li].isalpha():
                    continue
                d2 = (cx - nx) ** 2 + (cy - ny) ** 2
                if d2 < best:
                    best, pick = d2, (wi, (cx, cy))
        targets.append((nx, ny, *pick))
    pylog.info(f"targets: chosen {len(targets)} letters")

    # blink helper -----------------------------------------------------------
    def blink(li, idx):
        _log_and_flush(f"blink: point {idx} → red ON")
        letter_stims[li].color = red; letter_stims[li].bold = True
        win.flip(); core.wait(0.2)

        letter_stims[li].color = gray; letter_stims[li].bold = False
        win.flip(); core.wait(0.1)

        letter_stims[li].color = red; letter_stims[li].bold = True
        win.flip(); core.wait(0.25)
        # remains red
        _log_and_flush(f"blink: point {idx} finished (red holds)")

    # main loop --------------------------------------------------------------
    _log_and_flush(f"Starting calibration loop with {len(targets)} target points")
    
    prev_li = None
    best_letters = []
    for idx, (nx, ny, wi, (cx, cy)) in enumerate(targets, start=1):
        _log_and_flush(f"=== Calibration point {idx}/{len(targets)} starting ===")
        if abort_if_escape():
            pylog.info(">>> CALIBRATION: aborted mid-loop (ESC)")
            break

        # clear previous highlight
        if prev_li is not None:
            letter_stims[prev_li].color = gray
            letter_stims[prev_li].bold  = False
            win.flip()
            pylog.info(f"loop: cleared previous point {idx-1}")

        # select & blink current target
        best_li = min(
            w2idx[wi],
            key=lambda li: ((letter_info[li][1] + letter_info[li][3] / 2)
                            - cx * SCR_W) ** 2 +
                           ((letter_info[li][2] + FSIZE / 2)
                            - cy * SCR_H) ** 2
        )
        best_letters.append(best_li)
        blink(best_li, idx)
        prev_li = best_li

        # tracker-specific fixation + collect
        if tracker_on:
            _log_and_flush(f"tracker: fixation window for point {idx}")
            start, fix0 = core.getTime(), None
            fixation_achieved = False
            manual_skip = False
            
            # Clear keyboard events before starting
            event.clearEvents(eventType='keyboard')
            
            while core.getTime() - start < CALIB_TIMEOUT:
                if abort_if_escape():
                    break
                
                # Check for Space key to skip this point
                keys = event.getKeys(keyList=['space'])
                if keys:
                    manual_skip = True
                    _log_and_flush(f"tracker: point {idx} SKIPPED by experimenter (Space pressed)")
                    break
                
                if _gaze_on_target(nx, ny, CALIB_TOL):
                    fix0 = fix0 or core.getTime()
                    if core.getTime() - fix0 >= CALIB_DUR:
                        fixation_achieved = True
                        break
                else:
                    fix0 = None
                core.wait(0.003)
            
            if manual_skip:
                _log_and_flush(f"tracker: skipping data collection for point {idx}")
            elif not fixation_achieved:
                _log_and_flush(f"tracker: TIMEOUT waiting for fixation on point {idx} after {CALIB_TIMEOUT}s")
            elif not fixation_achieved:
                _log_and_flush(f"tracker: TIMEOUT waiting for fixation on point {idx} after {CALIB_TIMEOUT}s")
            else:
                _log_and_flush(f"tracker: fixation achieved for point {idx}")
            
            # Only collect data if not manually skipped
            if not manual_skip:
                _log_and_flush(f"tracker: collect_data for point {idx}")
                collect_success = False
                for rep in range(CALIB_MAX_RETRIES + 1):
                    try:
                        st = calib.collect_data(cx, cy)
                        _log_and_flush(f"tracker: collect_data rep{rep} → {st}")
                        if st == tr.CALIBRATION_STATUS_SUCCESS:
                            collect_success = True
                            break
                    except Exception as e:
                        _log_and_flush(f"tracker: collect_data rep{rep} EXCEPTION: {e}")
                    core.wait(0.3)
                
                if not collect_success:
                    _log_and_flush(f"tracker: WARNING - Failed to collect data for point {idx} after {CALIB_MAX_RETRIES+1} attempts")
        else:
            core.wait(0.25)  # lightweight pause
            pylog.info(f"loop: no-tracker pause after point {idx}")

    # ── finalise tracker -------------------------------------------------------
    if tracker_on:
        _log_and_flush("tracker: computing and applying calibration")
        try:
            res = calib.compute_and_apply()
            _log_and_flush("compute_and_apply → %s", res.status)
            calib.leave_calibration_mode()
            _log_and_flush("tracker: left calibration mode")
        except Exception as e:
            _log_and_flush(f"compute_and_apply CRITICAL ERROR: {e}")
            _log_exc("compute_and_apply error")
            try:
                calib.leave_calibration_mode()
                _log_and_flush("tracker: left calibration mode after error")
            except:
                pass
            return

        # ── INSERT THE DISPERSION & VISUALIZATION BLOCK HERE ───────────────────

        # ── Compute average dispersion using cp.position_on_display_area ───────
        ds_means = []
        for cp in res.calibration_points:
            # target coords come from this attribute (normalized 0–1)
            tx, ty = cp.position_on_display_area

            # collect distances from every valid sample
            dists = []
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
        pylog.info("Average calibration dispersion = %.4f norm units", avg_disp)

        # ── Visualize calibration letters on white with samples ────────────────
        # clear to white background
        win.color = BG_COLOR
        win.flip(clearBuffer=True)

        gray = [0.4, 0.4, 0.4]
        red = [1.0, -1.0, -1.0]
        green = [-1.0, 1.0, -1.0]

        # draw every letter: red if in best_letters, else gray
        for idx, (ch, x, y, em, _) in enumerate(letter_info):
            is_calib = idx in best_letters
            visual.TextStim(
                win,
                text=ch,
                font=FONT,
                height=FSIZE,
                color=red if is_calib else gray,
                bold=True if is_calib else False,
                pos=(
                    x - SCR_W / 2 + em / 2,
                    SCR_H / 2 - y - FSIZE / 2
                )
            ).draw()

        # overlay raw gaze samples in green
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
                px = gx * SCR_W - SCR_W / 2
                py = SCR_H / 2 - gy * SCR_H
                visual.Circle(
                    win,
                    radius=6,
                    edges=16,
                    fillColor=green,
                    lineColor=green,
                    pos=(px, py)
                ).draw()

        # Add instruction text at the bottom of the screen
        visual.TextStim(
            win,
            text="Press SPACE to continue (or ESC to abort)",
            font=FONT,
            height=30,
            color=[-1, -1, -1],
            pos=(0, -SCR_H / 2 + 50),
            bold=True
        ).draw()

        # show it and wait for operator to press SPACE (with timeout)
        win.flip()
        _log_and_flush("Waiting for SPACE to continue (or ESC to abort, 20s timeout)...")
        
        # Clear any stale keyboard events
        event.clearEvents(eventType='keyboard')
        
        # Use manual timeout loop for better control
        start_wait = core.getTime()
        keys_pressed = None
        while core.getTime() - start_wait < 20.0:
            keys_pressed = event.getKeys(keyList=["space", "escape"])
            if keys_pressed:
                break
            core.wait(0.05)  # Check every 50ms
            if abort_if_escape():
                break
        
        if keys_pressed and "escape" in keys_pressed:
            _log_and_flush("Calibration visualization aborted by user")
        elif not keys_pressed:
            _log_and_flush("Calibration visualization timed out after 20s, continuing automatically")
        else:
            _log_and_flush("Calibration visualization completed - SPACE pressed")

    # clean-up ---------------------------------------------------------------
    for stim in letter_stims:
        stim.autoDraw = False  # hide calibration letters

    win.color = BG_COLOR  # light gray background
    win.flip(clearBuffer=True)  # show it immediately
    
    _log_and_flush(">>> CALIBRATION: finished")



try:
    perform_calibration()
except Exception as e:
    _log_and_flush(f"CRITICAL: Calibration crashed with exception: {e}")
    _log_exc("Calibration exception details")
    # Try to recover window state
    try:
        win.color = BG_COLOR
        win.flip(clearBuffer=True)
    except:
        pass
    # Show error message to user
    try:
        visual.TextStim(
            win, 
            text=f"Calibration error occurred.\nCheck experiment_debug.log for details.\n\nPress ESC to exit.",
            font=FONT, height=30, color=[-1, -1, -1],
            alignText="center", wrapWidth=(BR[0]-TL[0])*SCR_W
        ).draw()
        win.flip()
        event.waitKeys(keyList=["escape"])
    except:
        pass
    ABORT = True

# ─────────────────────────────────────────────────────────────────────────────
#  Trials (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
if not ABORT:
    # Use calibration review (first review) for fixation cross position
    fx_rel = calibration_review["word_centroids"][0]["centroids"][0]
    fx_x = fx_rel[0] * SCR_W - SCR_W/2
    fx_y = SCR_H/2 - fx_rel[1] * SCR_H
    h_line = visual.Line(win, start=(fx_x-30, fx_y), end=(fx_x+30, fx_y),
                         lineColor=[-1, -1, -1], lineWidth=5)
    v_line = visual.Line(win, start=(fx_x, fx_y-30), end=(fx_x, fx_y+30),
                         lineColor=[-1, -1, -1], lineWidth=5)

    # Sample from trial_reviews (all reviews EXCEPT the first one used for calibration)
    sel = random.sample(trial_reviews, N_TRIALS)
    n_tot = n_cor = 0
    trial_correctness = []  # Track correctness of each trial

    for t_idx, rec in enumerate(sel, 1):
        if abort_if_escape(): break

        rid = rec["id"]
        # Robust rating conversion: handle both "2" and "2.0" formats
        try:
            rating = int(float(rec["rating"]))
        except (ValueError, TypeError) as e:
            pylog.error(f"Invalid rating for review {rid}: {rec.get('rating')} - {e}")
            rating = 3  # Default to neutral rating
        words = [w["word"] for w in rec["word_centroids"]]
        pylog.info("Trial %d – review %s (rating=%d)", t_idx, rid, rating)

        # ─────────────────────────────────────────────────────────────────────────
        #  Fixation cross with dimmed background
        # ─────────────────────────────────────────────────────────────────────────
        # draw the 15%-opaque black overlay
        visual.Rect(
            win=win,
            width=SCR_W * 2, height=SCR_H * 2,
            units='pix',
            fillColor=[-1, -1, -1], lineColor=None,
            opacity=0.05
        ).draw()
        # now draw your horizontal & vertical lines on top
        h_line.draw()
        v_line.draw()
        # flip once to show dimmer + cross together
        win.flip()
        # begin your fixation timer as before
        t0 = core.getTime()
        while True:
            if abort_if_escape(): break
            elapsed = core.getTime() - t0
            if elapsed >= FIX_TIMEOUT:
                pylog.info(f"Fixation timeout ({FIX_TIMEOUT:.1f}s)")
                break
            if elapsed >= FIX_DUR and TOBII["connected"] and last_gaze["valid"]:
                dx = last_gaze["x"] - fx_rel[0]
                dy = last_gaze["y"] - fx_rel[1]
                if math.hypot(dx, dy) <= FIX_TOL:
                    break
            elif elapsed >= FIX_DUR:
                break
            core.wait(0.005)

        # ─────────────────────────────────────────────────────────────────────────────
        #  Draw review text with dim overlay
        # ─────────────────────────────────────────────────────────────────────────────
        # compute box metrics and split words into lines as before
        box_w, tlx, tly = (BR[0] - TL[0]) * SCR_W, TL[0] * SCR_W, TL[1] * SCR_H
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

        # draw the 15%-opaque black “dimmer” over the whole window
        visual.Rect(
            win=win,
            width=SCR_W * 2, height=SCR_H * 2,
            units='pix',
            fillColor=[-1, -1, -1], lineColor=None,
            opacity=0.05
        ).draw()

        # draw every line of review text on top of the dimmer
        for row, line_words in enumerate(lines):
            y = tly + row * line_h
            x = tlx
            for w in line_words:
                for ch in w:
                    em = gw(ch)
                    visual.TextStim(
                        win=win,
                        text=ch,
                        font=FONT,
                        height=FSIZE,
                        color=[-1, -1, -1],
                        pos=(
                            x - SCR_W / 2 + em / 2,
                            SCR_H / 2 - y - FSIZE / 2
                        )
                    ).draw()
                    x += em
                x += space_adv

        # now flip *once* to show overlay + text together
        win.flip()

        push_event(1.0, float(rid), float(rating), float(t_idx))
        key = event.waitKeys(keyList=["left", "right", "escape"])[0]
        if key == "escape": abort_if_escape(); break

        n_tot += 1
        correct = ((key=="left" and rating not in (4,5)) or (key=="right" and rating not in (1,2)))
        n_cor += int(correct)
        trial_correctness.append(correct)  # Store correctness for this trial
        push_event(2.0, 0.0 if key=="left" else 1.0)
        pylog.info("Trial %d response: %s (correct=%s)", t_idx, key, correct)

    if not ABORT and n_tot:
        pct = round(100 * n_cor / n_tot)
        
        # Randomly select one trial to check correctness
        random_trial_correct = random.choice(trial_correctness)
        random_result = "TAK" if random_trial_correct else "NIE"
        
        visual.TextStim(win, text=f"Twój wynik ogółem: {pct} %\n\nPoprawna odpowiedź w wylosowanym trialu: {random_result}",
                        font=FONT, height=40, color=[-1, -1, -1],
                        alignText="center", wrapWidth=(BR[0]-TL[0])*SCR_W
        ).draw()
        win.color = BG_COLOR; win.flip()
        event.waitKeys(keyList=["escape"]); abort_if_escape()

# ─────────────────────────────────────────────────────────────────────────────
#  Shutdown
# ─────────────────────────────────────────────────────────────────────────────
pylog.info("Shutdown sequence")
if TOBII["connected"]:
    try:
        et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, _gaze_cb)
        pylog.info("Unsubscribed from gaze data")
    except Exception:
        _log_exc("Error unsubscribing gaze data")

_stop_w.set()
_log_thread.join()

win.close(); core.quit()
pylog.info("Binary log saved to output/%s", os.path.basename(DATA_PATH))
if not ABORT and 'n_tot' in locals() and n_tot:
    pylog.info("Accuracy %d/%d = %.1f%%", n_cor, n_tot, 100*n_cor/n_tot)
pylog.info("TOBII_STATUS: %s", TOBII)
pylog.info("=== Script ended ===\n")

print("Binary log: output/" + os.path.basename(DATA_PATH))
