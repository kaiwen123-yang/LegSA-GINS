#!/usr/bin/env python3
"""Audit N7C1 mandatory figure coverage gates.

中文说明：该审计只验证 coverage 规则，确保空图、短 clean 时间轴、缺 Go2 prior
series、缺 stress 对比和缺 update rows 不能通过。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c_plot_coverage import (
    inspect_n7c1_plot_source_data,
    summarize_n7c1_plot_coverage,
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c_required_figures_nonempty failed: {message}")


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"nonempty-test-figure")
    return path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c1_coverage_") as tmp_value:
        tmp = Path(tmp_value)
        valid_path = _touch(tmp / "valid.png")
        empty_rows = inspect_n7c1_plot_source_data(
            "01_clean_validation/clean_horizontal_error_no_go2_vs_go2_horizontal.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "clean",
                "series": [{"label": "no_go2", "x": [], "y": []}],
                "min_rows": 1000,
                "min_series": 2,
                "min_x_range": 200.0,
            },
        )
        if not empty_rows.empty_plot_suspect or "no_plotted_source_rows" not in empty_rows.reason_codes:
            _fail("zero plotted rows did not fail")
        short_axis = inspect_n7c1_plot_source_data(
            "01_clean_validation/clean_yaw_error_no_go2_vs_go2_horizontal.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "clean",
                "series": [
                    {"label": "no_go2", "x": list(range(20)), "y": [0.1] * 20},
                    {"label": "go2_horizontal", "x": list(range(20)), "y": [0.1] * 20},
                ],
                "min_rows": 10,
                "min_series": 2,
                "min_x_range": 200.0,
            },
        )
        if "unreasonable_time_axis_range" not in short_axis.reason_codes:
            _fail("short clean time axis did not fail")
        missing_prior = inspect_n7c1_plot_source_data(
            "02_prior_signal/go2_prior_confidence_timeline.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "prior_signal",
                "series": [{"label": "confidence_only", "x": [0, 1], "y": [1, 2]}],
                "min_rows": 2,
                "min_series": 1,
            },
        )
        if "go2_horizontal_velocity_series_missing" not in missing_prior.reason_codes:
            _fail("missing Go2 horizontal prior series did not fail")
        missing_stress = inspect_n7c1_plot_source_data(
            "04_stress_validation/receiver_velocity_stress_no_go2_vs_plus_go2.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "stress",
                "series": [{"label": "no_go2", "x": [0, 1], "y": [1, 1]}],
                "min_rows": 2,
                "min_series": 1,
            },
        )
        if "stress_required_series_missing" not in missing_stress.reason_codes:
            _fail("missing plus-Go2 stress series did not fail")
        residual_short = inspect_n7c1_plot_source_data(
            "03_update_residuals/go2_horizontal_prior_residual_time.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "update_residual",
                "series": [{"label": "go2_horizontal_residual_norm", "x": [0, 1], "y": [0.1, 0.2]}],
                "update_count": 10,
            },
        )
        if "update_residual_rows_below_update_count" not in residual_short.reason_codes:
            _fail("short residual rows did not fail")
        valid = inspect_n7c1_plot_source_data(
            "01_clean_validation/clean_horizontal_error_no_go2_vs_go2_horizontal.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "clean",
                "series": [
                    {"label": "no_go2", "x": [float(i) * 0.25 for i in range(1200)], "y": [0.1] * 1200},
                    {"label": "go2_horizontal", "x": [float(i) * 0.25 for i in range(1200)], "y": [0.1] * 1200},
                ],
                "min_rows": 1000,
                "min_series": 2,
                "min_x_range": 200.0,
            },
        )
        if valid.empty_plot_suspect:
            _fail("valid clean coverage failed")
        report = summarize_n7c1_plot_coverage([valid])
        if not report.get("visual_validation_passed"):
            _fail("valid summary did not pass")
    print("audit_n7c_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
