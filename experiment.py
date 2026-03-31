#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experiment.py – ExperimentRunner: orchestrates the full session flow.

Session flow:
  1. Welcome screen
  2. Questionnaire (5 questions)
  3. Instructions
  4. Eye-tracker calibration
  5. 10 trials  (fixation cross → stimulus → response → ISI)
  6. End screen
  7. Data save + visualisations
"""

import datetime
import os
from typing import List, Dict, Optional

from stimuli import build_trial_list, PRODUCT_PAIRS
from tobii_integration import create_tracker, GazeSample
from eye_metrics import (
    build_aois,
    detect_fixations_ivt,
    assign_aois,
    compute_aoi_metrics,
    compute_trial_summary,
    draw_scanpath,
    draw_heatmap,
)
import ui
import utils


class ExperimentRunner:

    N_TRIALS = 10

    def __init__(self, test_mode: bool = False,
                 fullscreen: bool = True,
                 screen_idx: int = 0):
        self.test_mode   = test_mode
        self.fullscreen  = fullscreen
        self.screen_idx  = screen_idx

        self.win         = None
        self.tracker     = None
        self.participant_id: str = ""
        self.dirs: Dict[str, str] = {}

        self.questionnaire_answers: Dict[str, Dict] = {}
        self.behavioral_data: List[Dict] = []
        self.all_gaze_samples: List[GazeSample] = []
        self.all_aoi_metrics: List[Dict] = []
        self.all_trial_summaries: List[Dict] = []

    # ─────────────────────────────────────────────────────────────────────────
    #  Setup
    # ─────────────────────────────────────────────────────────────────────────

    def _setup(self) -> None:
        self.participant_id = utils.generate_participant_id()
        self.dirs = utils.create_output_dirs(self.participant_id)
        os.makedirs("images", exist_ok=True)
        os.makedirs("data",   exist_ok=True)

        self.win = ui.create_window(
            fullscreen=self.fullscreen,
            screen=self.screen_idx,
        )

        self.tracker = create_tracker(test_mode=self.test_mode)
        if not self.tracker.is_connected:
            print("[ExperimentRunner] WARNING: tracker not connected – "
                  "continuing without eye-tracking data.")

    # ─────────────────────────────────────────────────────────────────────────
    #  Individual stages
    # ─────────────────────────────────────────────────────────────────────────

    def _show_welcome(self) -> None:
        ui.show_text_screen(
            self.win,
            "Witaj w badaniu",
            subtext=(
                "Za chwilę odpowiesz na kilka pytań,\n"
                "a następnie zobaczysz pary produktów.\n\n"
                "Twoim zadaniem będzie wybrać ten produkt,\n"
                "który byś kupił(a).\n\n"
                "Naciśnij SPACJĘ, aby kontynuować."
            ),
        )

    def _run_questionnaire(self) -> None:
        self.questionnaire_answers = ui.run_questionnaire(self.win)

    def _show_instructions(self) -> None:
        ui.show_text_screen(
            self.win,
            "Instrukcja",
            subtext=(
                "Za chwilę zobaczysz pary produktów spożywczych.\n\n"
                "Każdy produkt będzie pokazany jako zdjęcie\n"
                "oraz prosty tekstowy skład umieszczony pod zdjęciem.\n\n"
                "Wybierz produkt, który byś kupił(a):\n\n"
                "  Lewy przycisk myszy  =  produkt po LEWEJ\n"
                "  Prawy przycisk myszy =  produkt po PRAWEJ\n\n"
                "Odpowiadaj możliwie naturalnie.\n\n"
                "Naciśnij SPACJĘ, aby rozpocząć.",
            ),
            button_label="Rozpocznij",
        )

    def _run_calibration(self) -> None:
        ui.run_calibration_screen(self.win, self.tracker)

    # ─────────────────────────────────────────────────────────────────────────
    #  Trial execution
    # ─────────────────────────────────────────────────────────────────────────

    def _run_single_trial(self, trial_config) -> None:
        aois = build_aois()

        # Start recording
        if self.tracker.is_connected:
            self.tracker.start_recording(trial_config.trial_number)

        # Present stimulus and collect response
        chosen_side, rt_ms = ui.run_trial_screen(
            self.win, trial_config, trial_total=self.N_TRIALS,
        )

        # Stop recording
        trial_samples: List[GazeSample] = []
        if self.tracker.is_connected:
            trial_samples = self.tracker.stop_recording()

        self.all_gaze_samples.extend(trial_samples)

        # Determine chosen product
        chosen_product = (
            trial_config.left_product  if chosen_side == "left"
            else trial_config.right_product
        )

        # Behavioural record
        now = datetime.datetime.now().isoformat(timespec="seconds")
        self.behavioral_data.append({
            "datetime":             now,
            "trial_number":         trial_config.trial_number,
            "left_product_id":      trial_config.left_product.product_id,
            "right_product_id":     trial_config.right_product.product_id,
            "left_product_name":    trial_config.left_product.name,
            "right_product_name":   trial_config.right_product.name,
            "left_image_path":      trial_config.left_product.image_path,
            "right_image_path":     trial_config.right_product.image_path,
            "left_ingredients":     trial_config.left_product.ingredients,
            "right_ingredients":    trial_config.right_product.ingredients,
            "left_health_profile":  trial_config.left_product.health_profile,
            "right_health_profile": trial_config.right_product.health_profile,
            "chosen_side":          chosen_side,
            "chosen_product_name":  chosen_product.name,
            "reaction_time_ms":     round(rt_ms, 1),
        })

        # Eye-tracking metrics (only meaningful with real samples)
        if trial_samples:
            fixations = detect_fixations_ivt(trial_samples)
            assign_aois(fixations, aois)

            aoi_rows = compute_aoi_metrics(
                fixations, aois,
                trial_config.trial_number,
                self.participant_id,
            )
            self.all_aoi_metrics.extend(aoi_rows)

            summary = compute_trial_summary(
                fixations, trial_samples,
                trial_config.trial_number,
                self.participant_id,
                chosen_side, rt_ms,
            )
            self.all_trial_summaries.append(summary)

            # Scanpath image
            sp_path = os.path.join(
                self.dirs["scanpath"],
                f"trial_{trial_config.trial_number:02d}_scanpath.png",
            )
            draw_scanpath(fixations, aois, sp_path)

            # Heatmap image
            hm_path = os.path.join(
                self.dirs["heatmaps"],
                f"trial_{trial_config.trial_number:02d}_heatmap.png",
            )
            draw_heatmap(trial_samples, hm_path)

    # ─────────────────────────────────────────────────────────────────────────
    #  End screen & save
    # ─────────────────────────────────────────────────────────────────────────

    def _show_end_screen(self) -> None:
        ui.show_text_screen(
            self.win,
            "Dziękujemy za udział w badaniu.",
            subtext=(
                "Dane zostały zapisane.\n\n"
                "Naciśnij SPACJĘ, aby zakończyć."
            ),
        )

    def _save_data(self) -> None:
        base = self.dirs["base"]
        pid  = self.participant_id

        if self.questionnaire_answers:
            p = utils.save_questionnaire_csv(
                self.questionnaire_answers, base, pid)
            print(f"[Data] Questionnaire: {p}")

        if self.behavioral_data:
            p = utils.save_behavioral_csv(self.behavioral_data, base, pid)
            print(f"[Data] Behavioural:   {p}")

        if self.all_gaze_samples:
            p = utils.save_raw_gaze_csv(self.all_gaze_samples, base, pid)
            print(f"[Data] Raw gaze:      {p}")

        if self.all_aoi_metrics:
            p = utils.save_aoi_metrics_csv(self.all_aoi_metrics, base, pid)
            print(f"[Data] AOI metrics:   {p}")

        if self.all_trial_summaries:
            p = utils.save_trial_summary_csv(
                self.all_trial_summaries, base, pid)
            print(f"[Data] Trial summary: {p}")

    def _cleanup(self) -> None:
        if self.tracker:
            self.tracker.disconnect()
        if self.win:
            self.win.close()

    # ─────────────────────────────────────────────────────────────────────────
    #  Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            self._setup()

            self._show_welcome()
            self._run_questionnaire()
            self._show_instructions()
            self._run_calibration()

            trials = build_trial_list(PRODUCT_PAIRS, n_trials=self.N_TRIALS)

            for trial in trials:
                self._run_single_trial(trial)

            self._show_end_screen()
            self._save_data()

        except SystemExit:
            # Graceful abort (ESC pressed)
            self._save_data()
        except Exception as exc:
            import traceback
            print(f"[ExperimentRunner] FATAL: {exc}")
            traceback.print_exc()
            self._save_data()
        finally:
            self._cleanup()
