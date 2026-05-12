#!/usr/bin/env python3
"""Audit N6B1 mandatory-figure coverage gates.

中文说明：该审计只验证 coverage 规则，确保空图、短时间轴、缺源 ID、缺 spike
残差都不能通过；不读取真实 runtime 数据。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.source_aware.source_aware_n6b_plot_coverage import (
    inspect_n6b1_plot_source_data,
    summarize_n6b1_plot_coverage,
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n6b1_required_figures_nonempty failed: {message}")


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-a-real-figure-but-nonempty")
    return path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="legsa_n6b1_coverage_") as tmp_value:
        tmp = Path(tmp_value)
        valid_path = _touch(tmp / "valid.png")
        empty_rows = inspect_n6b1_plot_source_data(
            "01_clean_validation/clean_horizontal_error_no_sourceaware_vs_n6b.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "clean",
                "series": [{"label": "no_sourceaware", "x": [], "y": []}],
                "min_rows": 1000,
                "min_series": 2,
                "min_x_range": 200.0,
            },
        )
        if not empty_rows.empty_plot_suspect or "no_plotted_source_rows" not in empty_rows.reason_codes:
            _fail("zero plotted rows did not fail")
        short_axis = inspect_n6b1_plot_source_data(
            "01_clean_validation/clean_up_error_no_sourceaware_vs_n6b.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "clean",
                "series": [
                    {"label": "no_sourceaware", "x": list(range(20)), "y": [0.1] * 20},
                    {"label": "n6b", "x": list(range(20)), "y": [0.1] * 20},
                ],
                "min_rows": 10,
                "min_series": 2,
                "min_x_range": 200.0,
            },
        )
        if "unreasonable_time_axis_range" not in short_axis.reason_codes:
            _fail("short clean time axis did not fail")
        weight_bad = inspect_n6b1_plot_source_data(
            "02_weight_traces/n6b_R_scale_by_source_time.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "weight_trace",
                "source_ids": ["receiver_position", "receiver_velocity"],
                "series": [
                    {"label": "receiver_position", "x": [0, 1], "y": [1, 1.1]},
                    {"label": "receiver_velocity", "x": [0, 1], "y": [1, 1.2]},
                ],
                "min_rows": 2,
                "min_series": 2,
            },
        )
        if "weight_trace_source_ids_below_requirement" not in weight_bad.reason_codes:
            _fail("missing weight source IDs did not fail")
        spike_bad = inspect_n6b1_plot_source_data(
            "03_spike_response/raw_doppler_spike_response_zoom_96_97s.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "spike_zoom",
                "series": [{"label": "raw_doppler_scale", "x": [0, 1], "y": [1, 1.5]}],
                "min_rows": 2,
                "min_series": 1,
            },
        )
        if "spike_zoom_scale_or_residual_missing" not in spike_bad.reason_codes:
            _fail("spike zoom without residual did not fail")
        valid = inspect_n6b1_plot_source_data(
            "01_clean_validation/clean_yaw_error_no_sourceaware_vs_n6b.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "clean",
                "series": [
                    {"label": "no_sourceaware", "x": [float(i) * 0.25 for i in range(1200)], "y": [0.1] * 1200},
                    {"label": "n6b", "x": [float(i) * 0.25 for i in range(1200)], "y": [0.1] * 1200},
                ],
                "min_rows": 1000,
                "min_series": 2,
                "min_x_range": 200.0,
            },
        )
        if valid.empty_plot_suspect:
            _fail("valid clean coverage failed")
        report = summarize_n6b1_plot_coverage([valid])
        if not report.get("visual_validation_passed"):
            _fail("valid summary did not pass")
    print("audit_n6b1_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
