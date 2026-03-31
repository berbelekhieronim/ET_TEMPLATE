#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils.py – shared utilities: file I/O, coordinate conversion, participant ID.
"""

import os
import csv
import datetime
from typing import List, Dict, Any

SCR_W: int = 1920
SCR_H: int = 1080


# ─────────────────────────────────────────────────────────────────────────────
#  Participant / output directory helpers
# ─────────────────────────────────────────────────────────────────────────────

def generate_participant_id() -> str:
    return datetime.datetime.now().strftime("P%Y%m%d_%H%M%S")


def create_output_dirs(participant_id: str) -> Dict[str, str]:
    base = os.path.join("output", participant_id)
    scanpath = os.path.join(base, "scanpath_images")
    heatmaps = os.path.join(base, "heatmaps")
    for d in (base, scanpath, heatmaps):
        os.makedirs(d, exist_ok=True)
    return {"base": base, "scanpath": scanpath, "heatmaps": heatmaps}


# ─────────────────────────────────────────────────────────────────────────────
#  CSV savers
# ─────────────────────────────────────────────────────────────────────────────

def _write_csv(filepath: str, rows: List[Dict], fieldnames: List[str]) -> str:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return filepath


def save_questionnaire_csv(answers: Dict[str, Dict], output_dir: str,
                           participant_id: str) -> str:
    rows = [
        {
            "participant_id": participant_id,
            "question_id": qid,
            "question_text": v.get("text", ""),
            "answer": v.get("answer", ""),
        }
        for qid, v in answers.items()
    ]
    return _write_csv(
        os.path.join(output_dir, f"{participant_id}_questionnaire.csv"),
        rows,
        ["participant_id", "question_id", "question_text", "answer"],
    )


def save_behavioral_csv(trials: List[Dict], output_dir: str,
                        participant_id: str) -> str:
    rows = []
    for t in trials:
        row = dict(t)
        row["participant_id"] = participant_id
        for key in ("left_ingredients", "right_ingredients"):
            if isinstance(row.get(key), list):
                row[key] = " | ".join(row[key])
        rows.append(row)

    fieldnames = [
        "participant_id", "datetime", "trial_number",
        "left_product_id", "right_product_id",
        "left_product_name", "right_product_name",
        "left_image_path", "right_image_path",
        "left_ingredients", "right_ingredients",
        "left_health_profile", "right_health_profile",
        "chosen_side", "chosen_product_name", "reaction_time_ms",
    ]
    return _write_csv(
        os.path.join(output_dir, f"{participant_id}_behavioral.csv"),
        rows, fieldnames,
    )


def save_raw_gaze_csv(samples: List[Any], output_dir: str,
                      participant_id: str) -> str:
    rows = [
        {
            "timestamp":            f"{s.timestamp:.6f}",
            "trial_number":         s.trial_number,
            "gaze_x":               f"{s.gaze_x:.6f}",
            "gaze_y":               f"{s.gaze_y:.6f}",
            "left_validity":        s.left_validity,
            "right_validity":       s.right_validity,
            "left_pupil_diameter":  f"{s.left_pupil:.3f}"  if s.left_pupil  else "",
            "right_pupil_diameter": f"{s.right_pupil:.3f}" if s.right_pupil else "",
        }
        for s in samples
    ]
    return _write_csv(
        os.path.join(output_dir, f"{participant_id}_raw_gaze.csv"),
        rows,
        ["timestamp", "trial_number", "gaze_x", "gaze_y",
         "left_validity", "right_validity",
         "left_pupil_diameter", "right_pupil_diameter"],
    )


def save_aoi_metrics_csv(metrics_list: List[Dict], output_dir: str,
                         participant_id: str) -> str:
    if not metrics_list:
        return ""
    return _write_csv(
        os.path.join(output_dir, f"{participant_id}_aoi_metrics.csv"),
        metrics_list,
        list(metrics_list[0].keys()),
    )


def save_trial_summary_csv(summary: List[Dict], output_dir: str,
                           participant_id: str) -> str:
    if not summary:
        return ""
    return _write_csv(
        os.path.join(output_dir, f"{participant_id}_trial_summary.csv"),
        summary,
        list(summary[0].keys()),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Coordinate conversion between Tobii (top-left, 0-1) and PsychoPy (pix, centre)
# ─────────────────────────────────────────────────────────────────────────────

def tobii_to_psychopy(x: float, y: float,
                      scr_w: int = SCR_W, scr_h: int = SCR_H):
    """Tobii normalised (0-1, top-left) → PsychoPy pix (centre, y-up)."""
    px =  x * scr_w - scr_w / 2
    py = -(y * scr_h - scr_h / 2)
    return px, py


def psychopy_to_tobii(px: float, py: float,
                      scr_w: int = SCR_W, scr_h: int = SCR_H):
    """PsychoPy pix (centre, y-up) → Tobii normalised (0-1, top-left)."""
    x = (px + scr_w / 2) / scr_w
    y = (-py + scr_h / 2) / scr_h
    return x, y
