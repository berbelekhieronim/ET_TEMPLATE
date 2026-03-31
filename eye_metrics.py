#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eye_metrics.py – fixation detection, AOI metrics, scanpath & heatmap visualisation.

Pipeline:
  1. Raw GazeSamples  →  detect_fixations_ivt()  →  List[Fixation]
  2. Fixations + AOIs →  compute_aoi_metrics()   →  metrics dicts
  3. Fixations        →  draw_scanpath()          →  PNG file
  4. GazeSamples      →  draw_heatmap()           →  PNG file
"""

import math
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from tobii_integration import GazeSample
from stimuli import get_aoi_definitions

# ─────────────────────────────────────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AOI:
    name: str
    x1: float   # left   (Tobii normalised 0-1)
    y1: float   # top
    x2: float   # right
    y2: float   # bottom

    def contains(self, gx: float, gy: float) -> bool:
        return self.x1 <= gx <= self.x2 and self.y1 <= gy <= self.y2


@dataclass
class Fixation:
    start_ms: float
    end_ms: float
    x: float        # normalised centroid
    y: float
    aoi: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms


def build_aois() -> List[AOI]:
    defs = get_aoi_definitions()
    return [AOI(name=k, x1=v[0], y1=v[1], x2=v[2], y2=v[3])
            for k, v in defs.items()]


# ─────────────────────────────────────────────────────────────────────────────
#  I-VT fixation detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_fixations_ivt(
    samples: List[GazeSample],
    velocity_threshold: float = 0.025,  # normalised units/sample (≈30°/s at 120 Hz, 60cm, 24″)
    min_fixation_ms: float = 100.0,
    max_gap_ms: float = 75.0,
) -> List[Fixation]:
    """
    I-VT (velocity-threshold identification) algorithm.

    velocity_threshold : gaze displacement between consecutive samples (Tobii norm)
                         that separates fixation (<threshold) from saccade.
    min_fixation_ms    : fixations shorter than this are discarded.
    max_gap_ms         : consecutive fixation clusters closer than this are merged.
    """
    valid = [s for s in samples
             if not (math.isnan(s.gaze_x) or math.isnan(s.gaze_y))]
    if len(valid) < 2:
        return []

    # Classify each sample as fixation (velocity < threshold)
    flags = [True]  # first sample is always 'fixation' candidate
    for i in range(1, len(valid)):
        dx = valid[i].gaze_x - valid[i - 1].gaze_x
        dy = valid[i].gaze_y - valid[i - 1].gaze_y
        vel = math.hypot(dx, dy)
        flags.append(vel < velocity_threshold)

    # Group consecutive fixation samples into clusters
    clusters: List[List[GazeSample]] = []
    current: List[GazeSample] = []
    for sample, is_fix in zip(valid, flags):
        if is_fix:
            current.append(sample)
        else:
            if current:
                clusters.append(current)
                current = []
    if current:
        clusters.append(current)

    # Convert clusters to Fixation objects
    fixations: List[Fixation] = []
    for cl in clusters:
        t0_ms = cl[0].timestamp * 1000
        t1_ms = cl[-1].timestamp * 1000
        dur = t1_ms - t0_ms
        if dur < min_fixation_ms:
            continue
        cx = sum(s.gaze_x for s in cl) / len(cl)
        cy = sum(s.gaze_y for s in cl) / len(cl)
        fixations.append(Fixation(start_ms=t0_ms, end_ms=t1_ms, x=cx, y=cy))

    # Merge fixations that are very close in time (bridging small saccades/noise)
    merged: List[Fixation] = []
    for fix in fixations:
        if merged and (fix.start_ms - merged[-1].end_ms) <= max_gap_ms:
            prev = merged[-1]
            # weighted centroid by duration
            w1, w2 = prev.duration_ms, fix.duration_ms
            total = w1 + w2
            merged[-1] = Fixation(
                start_ms=prev.start_ms,
                end_ms=fix.end_ms,
                x=(prev.x * w1 + fix.x * w2) / total,
                y=(prev.y * w1 + fix.y * w2) / total,
            )
        else:
            merged.append(fix)

    return merged


def assign_aois(fixations: List[Fixation], aois: List[AOI]) -> List[Fixation]:
    """Tag each fixation with the AOI it falls in (mutates in-place, returns list)."""
    for fix in fixations:
        for aoi in aois:
            if aoi.contains(fix.x, fix.y):
                fix.aoi = aoi.name
                break
    return fixations


# ─────────────────────────────────────────────────────────────────────────────
#  AOI metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_aoi_metrics(
    fixations: List[Fixation],
    aois: List[AOI],
    trial_number: int,
    participant_id: str,
) -> List[Dict]:
    """
    Compute standard AOI metrics per AOI per trial.
    Returns a list of dicts (one per AOI).
    """
    rows = []
    for aoi in aois:
        aoi_fixations = [f for f in fixations if f.aoi == aoi.name]
        total_dur = sum(f.duration_ms for f in aoi_fixations)

        ttff = None
        ffd = None
        if aoi_fixations:
            ttff = aoi_fixations[0].start_ms
            ffd = aoi_fixations[0].duration_ms

        # Visit count: a new "visit" begins when the gaze leaves the AOI and returns
        visits = 0
        in_aoi = False
        for fix in fixations:
            if fix.aoi == aoi.name:
                if not in_aoi:
                    visits += 1
                    in_aoi = True
            else:
                in_aoi = False

        fixation_count = len(aoi_fixations)
        mean_fix_dur = (total_dur / fixation_count) if fixation_count else 0.0

        rows.append({
            "participant_id":        participant_id,
            "trial_number":          trial_number,
            "aoi_name":              aoi.name,
            "fixation_count":        fixation_count,
            "total_fixation_dur_ms": round(total_dur, 2),
            "mean_fixation_dur_ms":  round(mean_fix_dur, 2),
            "time_to_first_fixation_ms": round(ttff, 2) if ttff is not None else "",
            "first_fixation_dur_ms": round(ffd, 2) if ffd is not None else "",
            "visit_count":           visits,
            "total_dwell_time_ms":   round(total_dur, 2),
        })
    return rows


def compute_trial_summary(
    fixations: List[Fixation],
    samples: List[GazeSample],
    trial_number: int,
    participant_id: str,
    chosen_side: str,
    reaction_time_ms: float,
) -> Dict:
    """
    Per-trial summary: left vs right dwelling, image vs text proportion.
    """
    def dur_in(aoi_name: str) -> float:
        return sum(f.duration_ms for f in fixations if f.aoi == aoi_name)

    left_img   = dur_in("left_image")
    left_txt   = dur_in("left_text")
    right_img  = dur_in("right_image")
    right_txt  = dur_in("right_text")

    total = left_img + left_txt + right_img + right_txt or 1.0
    total_left  = left_img  + left_txt
    total_right = right_img + right_txt

    # Transitions between AOIs
    transitions: List[Tuple[str, str]] = []
    prev_aoi: Optional[str] = None
    for fix in fixations:
        if fix.aoi and fix.aoi != prev_aoi:
            if prev_aoi:
                transitions.append((prev_aoi, fix.aoi))
            prev_aoi = fix.aoi

    img_to_txt = sum(1 for a, b in transitions
                     if a in ("left_image", "right_image")
                     and b in ("left_text", "right_text"))
    txt_to_img = sum(1 for a, b in transitions
                     if a in ("left_text", "right_text")
                     and b in ("left_image", "right_image"))

    return {
        "participant_id":          participant_id,
        "trial_number":            trial_number,
        "chosen_side":             chosen_side,
        "reaction_time_ms":        round(reaction_time_ms, 1),
        "total_fixations":         len(fixations),
        "total_dwell_left_ms":     round(total_left, 2),
        "total_dwell_right_ms":    round(total_right, 2),
        "dwell_left_image_ms":     round(left_img, 2),
        "dwell_left_text_ms":      round(left_txt, 2),
        "dwell_right_image_ms":    round(right_img, 2),
        "dwell_right_text_ms":     round(right_txt, 2),
        "pct_dwell_left":          round(100 * total_left / total, 1),
        "pct_dwell_right":         round(100 * total_right / total, 1),
        "pct_image_dwell":         round(100 * (left_img + right_img) / total, 1),
        "pct_text_dwell":          round(100 * (left_txt + right_txt) / total, 1),
        "transitions_total":       len(transitions),
        "img_to_text_transitions": img_to_txt,
        "text_to_img_transitions": txt_to_img,
        "aoi_visit_sequence":      " → ".join(
            f.aoi or "none" for f in fixations if f.aoi
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Scanpath visualisation
# ─────────────────────────────────────────────────────────────────────────────

def draw_scanpath(
    fixations: List[Fixation],
    aois: List[AOI],
    output_path: str,
    scr_w: int = 1920,
    scr_h: int = 1080,
    background_path: Optional[str] = None,
) -> str:
    """
    Draw numbered fixation circles connected by lines on a background.
    Saves to output_path (PNG).  Returns the path.
    """
    try:
        import matplotlib  # type: ignore
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
        import matplotlib.patches as mpatches  # type: ignore
    except ImportError:
        print("[eye_metrics] matplotlib not available – skipping scanpath.")
        return ""

    fig, ax = plt.subplots(figsize=(scr_w / 100, scr_h / 100), dpi=100)
    ax.set_xlim(0, scr_w)
    ax.set_ylim(scr_h, 0)   # y-axis: 0 at top (Tobii convention)
    ax.set_aspect("equal")
    ax.axis("off")

    # Background image or light-grey canvas
    if background_path and os.path.exists(background_path):
        try:
            img = plt.imread(background_path)
            ax.imshow(img, extent=[0, scr_w, scr_h, 0], aspect="auto",
                      alpha=0.6)
        except Exception:
            ax.set_facecolor("#f5f5f5")
    else:
        ax.set_facecolor("#f5f5f5")

    # Draw AOI rectangles
    aoi_colors = {
        "left_image":  "#4488cc",
        "left_text":   "#44cc88",
        "right_image": "#cc4488",
        "right_text":  "#cc8844",
    }
    for aoi in aois:
        color = aoi_colors.get(aoi.name, "#888888")
        rect = mpatches.FancyBboxPatch(
            (aoi.x1 * scr_w, aoi.y1 * scr_h),
            (aoi.x2 - aoi.x1) * scr_w,
            (aoi.y2 - aoi.y1) * scr_h,
            boxstyle="round,pad=5",
            edgecolor=color, facecolor="none", linewidth=2, alpha=0.7,
        )
        ax.add_patch(rect)

    if not fixations:
        plt.tight_layout(pad=0)
        plt.savefig(output_path, bbox_inches="tight", dpi=100)
        plt.close(fig)
        return output_path

    # Saccade lines
    xs = [f.x * scr_w for f in fixations]
    ys = [f.y * scr_h for f in fixations]
    ax.plot(xs, ys, color="#555555", linewidth=1.2, alpha=0.6, zorder=2)

    # Fixation circles (radius ∝ duration)
    for idx, fix in enumerate(fixations, start=1):
        fx, fy = fix.x * scr_w, fix.y * scr_h
        radius = max(10, min(35, fix.duration_ms / 30))
        color = aoi_colors.get(fix.aoi, "#999999") if fix.aoi else "#999999"
        circle = plt.Circle((fx, fy), radius, color=color, alpha=0.55, zorder=3)
        ax.add_patch(circle)
        ax.text(fx, fy, str(idx), fontsize=7, ha="center", va="center",
                color="white", fontweight="bold", zorder=4)

    plt.tight_layout(pad=0)
    plt.savefig(output_path, bbox_inches="tight", dpi=100)
    plt.close(fig)
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
#  Heatmap visualisation
# ─────────────────────────────────────────────────────────────────────────────

def draw_heatmap(
    samples: List[GazeSample],
    output_path: str,
    scr_w: int = 1920,
    scr_h: int = 1080,
    sigma_frac: float = 0.025,   # Gaussian sigma as fraction of screen width
    background_path: Optional[str] = None,
) -> str:
    """
    Gaussian heatmap of all valid gaze samples.
    Saves to output_path (PNG).  Returns the path.
    """
    try:
        import matplotlib  # type: ignore
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
        from scipy.ndimage import gaussian_filter  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        print("[eye_metrics] scipy/numpy/matplotlib not available – skipping heatmap.")
        return ""

    import numpy as np  # noqa: F811

    valid = [(s.gaze_x, s.gaze_y) for s in samples
             if not (math.isnan(s.gaze_x) or math.isnan(s.gaze_y))]
    if not valid:
        return ""

    scale = 4  # downsample for speed
    w, h = scr_w // scale, scr_h // scale
    grid = np.zeros((h, w), dtype=float)

    for gx, gy in valid:
        xi = int(gx * w)
        yi = int(gy * h)
        if 0 <= xi < w and 0 <= yi < h:
            grid[yi, xi] += 1

    sigma = sigma_frac * w
    grid = gaussian_filter(grid, sigma=sigma)
    grid /= grid.max() if grid.max() > 0 else 1

    fig, ax = plt.subplots(figsize=(scr_w / 100, scr_h / 100), dpi=100)
    ax.axis("off")

    if background_path and os.path.exists(background_path):
        try:
            bg = plt.imread(background_path)
            ax.imshow(bg, extent=[0, scr_w, scr_h, 0], aspect="auto", alpha=0.5)
        except Exception:
            ax.set_facecolor("#f5f5f5")
    else:
        ax.set_facecolor("#f5f5f5")

    ax.imshow(
        grid,
        extent=[0, scr_w, scr_h, 0],
        cmap="hot",
        alpha=0.6,
        aspect="auto",
        interpolation="bilinear",
    )
    plt.tight_layout(pad=0)
    plt.savefig(output_path, bbox_inches="tight", dpi=100)
    plt.close(fig)
    return output_path
