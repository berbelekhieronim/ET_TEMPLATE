#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tobii_integration.py – hardware abstraction layer for Tobii Pro X3-120.

Architecture:
  BaseTracker       – interface
  TobiiTracker      – real Tobii Pro SDK (Windows, tobii_research package)
  MockTracker       – headless simulation for development & testing

create_tracker(test_mode=False) returns the right implementation.

To swap in a different tracker device:
  1. Subclass BaseTracker.
  2. Implement all abstract methods.
  3. Update create_tracker().
"""

import math
import time
import random
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Callable


# ─────────────────────────────────────────────────────────────────────────────
#  Data type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GazeSample:
    timestamp: float          # seconds since experiment start
    trial_number: int
    gaze_x: float             # normalised 0-1, Tobii display-area convention (top-left origin)
    gaze_y: float
    left_validity: int        # 0 = invalid, 1 = valid
    right_validity: int
    left_pupil: Optional[float]   # mm
    right_pupil: Optional[float]


# ─────────────────────────────────────────────────────────────────────────────
#  Base interface
# ─────────────────────────────────────────────────────────────────────────────

class BaseTracker(ABC):

    @abstractmethod
    def connect(self) -> bool:
        """Return True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def calibrate(self, win) -> bool:
        """
        Run calibration procedure using the provided PsychoPy window.
        Return True if calibration succeeded or was skipped.
        """

    @abstractmethod
    def start_recording(self, trial_number: int) -> None:
        pass

    @abstractmethod
    def stop_recording(self) -> List[GazeSample]:
        """Stop recording and return collected samples for the current trial."""

    @abstractmethod
    def get_latest_gaze(self) -> Optional[GazeSample]:
        """Return the most recent gaze sample (used for fixation cross logic)."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Real Tobii Pro tracker (X3-120 and compatible)
# ─────────────────────────────────────────────────────────────────────────────

class TobiiTracker(BaseTracker):
    """
    Wraps tobii_research SDK.
    Requires:  pip install tobii-research   (or bundled SDK in x3-120 SDK/64/)
    """

    TARGET_FREQ_HZ = 120.0

    def __init__(self):
        self._tr = None          # tobii_research module
        self._et = None          # eye tracker device
        self._connected = False
        self._recording = False
        self._current_trial = 0
        self._buffer: List[GazeSample] = []
        self._lock = threading.Lock()
        self._latest: Optional[GazeSample] = None
        self._t0 = 0.0           # reference timestamp for relative times

    # ── connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            import tobii_research as tr
            self._tr = tr
        except ImportError:
            print("[TobiiTracker] tobii_research not importable – run in test mode.")
            return False

        trackers = self._tr.find_all_eyetrackers()
        if not trackers:
            print("[TobiiTracker] No eye trackers found.")
            return False

        self._et = trackers[0]
        print(f"[TobiiTracker] Connected: {self._et.model} S/N {self._et.serial_number}")

        avail = self._et.get_all_gaze_output_frequencies()
        if self.TARGET_FREQ_HZ in avail:
            self._et.set_gaze_output_frequency(self.TARGET_FREQ_HZ)
        elif avail:
            self._et.set_gaze_output_frequency(max(avail))
        freq = self._et.get_gaze_output_frequency()
        print(f"[TobiiTracker] Frequency: {freq} Hz")

        self._connected = True
        self._t0 = time.time()
        return True

    def disconnect(self) -> None:
        if self._recording:
            self.stop_recording()
        if self._et and self._tr:
            try:
                self._et.unsubscribe_from(self._tr.EYETRACKER_GAZE_DATA,
                                          self._gaze_callback)
            except Exception:
                pass
        self._connected = False
        self._et = None
        print("[TobiiTracker] Disconnected.")

    # ── calibration ──────────────────────────────────────────────────────────

    def calibrate(self, win) -> bool:
        """
        Five-point screen-based calibration using PsychoPy window.
        Tobii normalised target positions: centre + four corners.
        """
        if not self._connected or not self._et:
            return False

        from psychopy import visual, event, core  # type: ignore

        tr = self._tr
        calib = tr.ScreenBasedCalibration(self._et)
        try:
            calib.enter_calibration_mode()
        except Exception as e:
            print(f"[TobiiTracker] enter_calibration_mode failed: {e}")
            return False

        points = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)]
        scr_w, scr_h = win.size

        for nx, ny in points:
            px = nx * scr_w - scr_w / 2
            py = -(ny * scr_h - scr_h / 2)
            dot = visual.Circle(win, radius=15, fillColor="red",
                                lineColor="red", pos=(px, py))
            dot.draw(); win.flip(); core.wait(0.5)
            try:
                calib.collect_data(nx, ny)
            except Exception as e:
                print(f"[TobiiTracker] collect_data failed at ({nx},{ny}): {e}")

        try:
            result = calib.compute_and_apply()
            calib.leave_calibration_mode()
            print(f"[TobiiTracker] Calibration status: {result.status}")
        except Exception as e:
            print(f"[TobiiTracker] compute_and_apply failed: {e}")
            try:
                calib.leave_calibration_mode()
            except Exception:
                pass
            return False

        win.flip()
        return True

    # ── recording ─────────────────────────────────────────────────────────────

    def _gaze_callback(self, gaze_data: dict) -> None:
        try:
            lv = int(gaze_data["left_gaze_point_validity"])
            rv = int(gaze_data["right_gaze_point_validity"])
            lx = ly = rx = ry = math.nan
            if lv:
                lx, ly = gaze_data["left_gaze_point_on_display_area"]
            if rv:
                rx, ry = gaze_data["right_gaze_point_on_display_area"]

            gx = lx if not math.isnan(lx) else rx
            gy = ly if not math.isnan(ly) else ry

            lp = gaze_data["left_pupil_diameter"]  if gaze_data["left_pupil_validity"]  else None
            rp = gaze_data["right_pupil_diameter"] if gaze_data["right_pupil_validity"] else None

            ts = time.time() - self._t0
            sample = GazeSample(
                timestamp=ts,
                trial_number=self._current_trial,
                gaze_x=float(gx),
                gaze_y=float(gy),
                left_validity=lv,
                right_validity=rv,
                left_pupil=float(lp) if lp is not None else None,
                right_pupil=float(rp) if rp is not None else None,
            )
            with self._lock:
                self._buffer.append(sample)
                self._latest = sample
        except Exception:
            pass

    def start_recording(self, trial_number: int) -> None:
        self._current_trial = trial_number
        self._buffer = []
        self._et.subscribe_to(self._tr.EYETRACKER_GAZE_DATA,
                              self._gaze_callback, as_dictionary=True)
        self._recording = True

    def stop_recording(self) -> List[GazeSample]:
        if not self._recording:
            return []
        self._et.unsubscribe_from(self._tr.EYETRACKER_GAZE_DATA,
                                  self._gaze_callback)
        self._recording = False
        with self._lock:
            samples = list(self._buffer)
            self._buffer = []
        return samples

    def get_latest_gaze(self) -> Optional[GazeSample]:
        with self._lock:
            return self._latest

    @property
    def is_connected(self) -> bool:
        return self._connected


# ─────────────────────────────────────────────────────────────────────────────
#  Mock tracker – simulates realistic gaze data for development & testing
# ─────────────────────────────────────────────────────────────────────────────

class MockTracker(BaseTracker):
    """
    Generates simulated gaze data at ~120 Hz.
    Gaze follows a slow random walk around the screen during each trial.
    """

    SAMPLE_INTERVAL = 1.0 / 120.0   # seconds

    def __init__(self):
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._buffer: List[GazeSample] = []
        self._lock = threading.Lock()
        self._latest: Optional[GazeSample] = None
        self._stop_event = threading.Event()
        self._current_trial = 0
        self._t0 = time.time()

    def connect(self) -> bool:
        self._t0 = time.time()
        print("[MockTracker] Simulated tracker ready.")
        return True

    def disconnect(self) -> None:
        if self._recording:
            self.stop_recording()
        print("[MockTracker] Disconnected.")

    def calibrate(self, win) -> bool:
        from psychopy import visual, event, core  # type: ignore
        msg = visual.TextStim(
            win,
            text="TRYB TESTOWY\n\nKalibracja eye trackera – symulacja.\n\nNaciśnij SPACJĘ, aby kontynuować.",
            height=36, color=(-1, -1, -1),
            wrapWidth=900,
        )
        msg.draw(); win.flip()
        event.waitKeys(keyList=["space"])
        win.flip()
        print("[MockTracker] Calibration simulated.")
        return True

    def _simulate(self) -> None:
        """Background thread: random-walk gaze at 120 Hz."""
        gx, gy = 0.5, 0.5
        while not self._stop_event.is_set():
            # slow random walk with soft boundary
            gx = max(0.05, min(0.95, gx + random.gauss(0, 0.008)))
            gy = max(0.05, min(0.95, gy + random.gauss(0, 0.008)))

            pupil = 3.5 + random.gauss(0, 0.05)
            sample = GazeSample(
                timestamp=time.time() - self._t0,
                trial_number=self._current_trial,
                gaze_x=gx,
                gaze_y=gy,
                left_validity=1,
                right_validity=1,
                left_pupil=pupil,
                right_pupil=pupil + random.gauss(0, 0.02),
            )
            with self._lock:
                self._buffer.append(sample)
                self._latest = sample

            time.sleep(self.SAMPLE_INTERVAL)

    def start_recording(self, trial_number: int) -> None:
        self._current_trial = trial_number
        self._buffer = []
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._simulate, daemon=True)
        self._thread.start()
        self._recording = True

    def stop_recording(self) -> List[GazeSample]:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._recording = False
        with self._lock:
            samples = list(self._buffer)
            self._buffer = []
        return samples

    def get_latest_gaze(self) -> Optional[GazeSample]:
        with self._lock:
            return self._latest

    @property
    def is_connected(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
#  Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_tracker(test_mode: bool = False) -> BaseTracker:
    """
    Returns a connected tracker instance.
    If test_mode=True, always returns MockTracker.
    Otherwise tries TobiiTracker; falls back to MockTracker on failure.
    """
    if test_mode:
        tracker = MockTracker()
        tracker.connect()
        return tracker

    tracker = TobiiTracker()
    if tracker.connect():
        return tracker

    print("[create_tracker] Tobii unavailable – falling back to MockTracker.")
    mock = MockTracker()
    mock.connect()
    return mock
