#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py – entry point for the food-choice eye-tracking experiment.

Usage:
    python main.py                   # auto-detect Tobii; fallback to mock
    python main.py --test            # force mock tracker (no hardware needed)
    python main.py --no-fullscreen   # windowed mode (development)
    python main.py --screen 1        # use secondary monitor

Before first run generate placeholder product images:
    python generate_placeholders.py
"""

import argparse
import sys
import os

# ── ensure the project root is on the path ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Food-choice eye-tracking experiment (PsychoPy + Tobii Pro X3-120)"
    )
    p.add_argument(
        "--test", action="store_true",
        help="Run in test/development mode: use simulated eye-tracker (MockTracker).",
    )
    p.add_argument(
        "--no-fullscreen", dest="no_fullscreen", action="store_true",
        help="Run in a window instead of fullscreen (useful for development).",
    )
    p.add_argument(
        "--screen", type=int, default=0,
        help="Monitor index (0=primary, 1=secondary, …). Default: 0.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    if args.test:
        print("[main] TEST MODE – simulated eye-tracker active.")

    # Deferred import so argparse works even without PsychoPy on PATH
    try:
        from experiment import ExperimentRunner
    except ImportError as exc:
        print(
            f"\nStartup error: cannot import experiment module.\n"
            f"Details: {exc}\n"
            f"Make sure PsychoPy is installed and accessible:\n"
            f"  - On Windows run via run_experiment.bat (bundled PsychoPy)\n"
            f"  - Or activate the correct conda/virtualenv first.\n"
        )
        sys.exit(1)

    runner = ExperimentRunner(
        test_mode=args.test,
        fullscreen=not args.no_fullscreen,
        screen_idx=args.screen,
    )
    runner.run()


if __name__ == "__main__":
    main()
