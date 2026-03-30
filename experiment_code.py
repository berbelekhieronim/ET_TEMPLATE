# -*- coding: utf-8 -*-
"""
with_eye_tracking.py  –  3-trial demo, exits on Esc

• Uses Tobii-style calibration (show target → wait for fixation → collect_data)
• Detailed binary + text logging with Tobii timestamps for every event
• Throttled gaze logging
• Early-exit on Esc
• All tunable parameters at the top

Modifications:
1. Writer thread is now joined on shutdown and has exception handling.
2. Gaze logging throttled to 1 line per 1200 samples.
3. Busy-wait loops remain but include comments on how to replace them.
4. RotatingFileHandler prevents the text log from growing without bounds.
5. Calibration-event logging now records the actual centroid.
6. Each calibration letter now blinks once in red on a gray background.
7. Raw-sample visualization: highlights only the best letter per target in its unique color and plots all gaze samples for that letter, then waits for Space.
8. After calibration, logs all CalibrationResult metrics.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  PARAMS
# ─────────────────────────────────────────────────────────────────────────────
JSON_DB              = "review_word_centroids.json"
FONT                 = "IBM Plex Mono"
FSIZE                = 34
LINE_SP              = 2
TL, BR               = (0.12, 0.18), (0.90, 0.99)
N_TRIALS             = 25

FIX_DUR              = 0.50
FIX_TOL              = 0.05
FIX_TIMEOUT          = 5.0

CALIB_DUR            = 0.20
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
pylog.basicConfig(level=pylog.INFO, handlers=[_rot])
pylog.info("=== Script started ===")
def _log_exc(msg): pylog.exception(msg)

# ─────────────────────────────────────────────────────────────────────────────
#  Binary gaze/event logger with safe shutdown
# ─────────────────────────────────────────────────────────────────────────────
def _next_bin():
    for i in range(SAVE_LIMIT):
        fn = os.path.join(HERE, f"data{i:03d}.bin")
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
TOBII = {"connected": False, "error": None}
et = None
try:
    import tobii_research as tr
    trackers = tr.find_all_eyetrackers()
    if trackers:
        et = trackers[0]
        pylog.info("Connected to %s (%s)", et.serial_number, et.model)
        if 1200.0 in et.get_all_gaze_output_frequencies():
            et.set_gaze_output_frequency(1200.0)
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

# Set monitor index (0 = primary, 1 = secondary, etc.)
SCREEN_INDEX = 1

mon = monitors.Monitor("scr")
mon.setSizePix((1920, 1080))
mon.save()

# Create a window on the specified screen
win = visual.Window(
    size=(1920, 1080),
    fullscr=True,
    monitor=mon,
    units="pix",
    color=[1, 1, 1],
    screen=SCREEN_INDEX #brightness
)

# Store screen resolution
SCR_W, SCR_H = win.size

pyglet.font.load(FONT, FSIZE)
_FONT = pyglet.font.load(FONT, FSIZE)
gw = lambda ch: _FONT.get_glyphs(ch)[0].advance
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
#  Gaze data callback (1/1200)
# ─────────────────────────────────────────────────────────────────────────────
last_gaze = {"valid": False, "x": math.nan, "y": math.nan}
_ctr = 0
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
            if _ctr % 1200 == 0:
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
    """
    pylog.info(">>> CALIBRATION: start")

    # abort shortcut ---------------------------------------------------------
    if abort_if_escape():
        pylog.info(">>> CALIBRATION: aborted immediately (ESC)")
        return

    # layout -----------------------------------------------------------------
    pylog.info("layout: finding longest row …")
    longest = max(db, key=lambda r: sum(len(w["word"]) for w in r["words"]))
    words_plain = [w["word"] for w in longest["words"]]

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
        for wi, wdat in enumerate(longest["words"]):
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
        pylog.info(f"blink: point {idx} → red ON")
        letter_stims[li].color = red; letter_stims[li].bold = True
        win.flip(); core.wait(0.2)

        letter_stims[li].color = gray; letter_stims[li].bold = False
        win.flip(); core.wait(0.1)

        letter_stims[li].color = red; letter_stims[li].bold = True
        win.flip(); core.wait(0.25)
        # remains red
        pylog.info(f"blink: point {idx} finished (red holds)")

    # main loop --------------------------------------------------------------
    prev_li = None
    best_letters = []
    for idx, (nx, ny, wi, (cx, cy)) in enumerate(targets, start=1):
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
            pylog.info(f"tracker: fixation window for point {idx}")
            start, fix0 = core.getTime(), None
            while core.getTime() - start < CALIB_TIMEOUT:
                if abort_if_escape():
                    break
                if _gaze_on_target(nx, ny, CALIB_TOL):
                    fix0 = fix0 or core.getTime()
                    if core.getTime() - fix0 >= CALIB_DUR:
                        break
                else:
                    fix0 = None
                core.wait(0.003)
            pylog.info(f"tracker: collect_data for point {idx}")
            for rep in range(CALIB_MAX_RETRIES + 1):
                st = calib.collect_data(cx, cy)
                pylog.info(f"tracker: collect_data rep{rep} → {st}")
                if st == tr.CALIBRATION_STATUS_SUCCESS:
                    break
                core.wait(0.3)
        else:
            core.wait(0.25)  # lightweight pause
            pylog.info(f"loop: no-tracker pause after point {idx}")

    # ── finalise tracker -------------------------------------------------------
    if tracker_on:
        try:
            res = calib.compute_and_apply()
            pylog.info("compute_and_apply → %s", res.status)
            calib.leave_calibration_mode()
        except Exception:
            _log_exc("compute_and_apply error")
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
        win.color = [1, 1, 1]
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

        # show it and wait for operator to press SPACE
        win.flip()
        event.waitKeys(keyList=["space"])
        pylog.info("Calibration finished")

    # clean-up ---------------------------------------------------------------
    for stim in letter_stims:
        stim.autoDraw = False  # hide calibration letters

    win.color = [1, 1, 1]  # plain white background
    win.flip(clearBuffer=True)  # show it immediately
    
    pylog.info(">>> CALIBRATION: finished")



perform_calibration()

# ─────────────────────────────────────────────────────────────────────────────
#  Trials (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
if not ABORT:
    fx_rel = db[0]["words"][0]["centroids"][0]
    fx_x = fx_rel[0] * SCR_W - SCR_W/2
    fx_y = SCR_H/2 - fx_rel[1] * SCR_H
    h_line = visual.Line(win, start=(fx_x-30, fx_y), end=(fx_x+30, fx_y),
                         lineColor=[-1, -1, -1], lineWidth=5)
    v_line = visual.Line(win, start=(fx_x, fx_y-30), end=(fx_x, fx_y+30),
                         lineColor=[-1, -1, -1], lineWidth=5)

    sel = random.sample(db, N_TRIALS)
    n_tot = n_cor = 0

    for t_idx, rec in enumerate(sel, 1):
        if abort_if_escape(): break

        rid, rating = rec["id"], int(rec["rating"])
        words = [w["word"] for w in rec["words"]]
        pylog.info("Trial %d – review %s", t_idx, rid)

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
        push_event(2.0, 0.0 if key=="left" else 1.0)
        pylog.info("Trial %d response: %s (correct=%s)", t_idx, key, correct)

    if not ABORT and n_tot:
        pct = round(100 * n_cor / n_tot)
        visual.TextStim(win, text=f"Dziękujemy za udział!\nTwój wynik: {pct} %",
                        font=FONT, height=40, color=[-1, -1, -1],
                        alignText="center", wrapWidth=(BR[0]-TL[0])*SCR_W
        ).draw()
        win.color = [1, 1, 1]; win.flip()
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
pylog.info("Binary log saved as %s", os.path.basename(DATA_PATH))
if not ABORT and 'n_tot' in locals() and n_tot:
    pylog.info("Accuracy %d/%d = %.1f%%", n_cor, n_tot, 100*n_cor/n_tot)
pylog.info("TOBII_STATUS: %s", TOBII)
pylog.info("=== Script ended ===\n")

print("Binary log:", os.path.basename(DATA_PATH))
