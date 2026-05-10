#!/usr/bin/env python3
"""Audit that mandatory N5D/N5D1 figures require non-empty plotted data.

中文说明：这个审计不解析图片像素，而是检查绘图源数据覆盖；mandatory 图为空时
visual validation 不能通过。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_plot_data_coverage import (
    inspect_plot_source_data,
    validate_required_figure_coverage,
)


def _fail(message: str) -> None:
    raise SystemExit(f"FAILED: {message}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="legsa_n5d1_coverage_audit_") as tmp_value:
        tmp = Path(tmp_value)
        fig = tmp / "clean_horizontal_error_baseline_vs_raw_repaired.png"
        fig.write_text("placeholder", encoding="utf-8")
        empty = inspect_plot_source_data(
            "01_clean_ablation_repaired/clean_horizontal_error_baseline_vs_raw_repaired.png",
            {
                "figure_path": str(fig),
                "mandatory": True,
                "source_data_roles": ["empty_source"],
                "min_rows": 1000,
                "min_series": 2,
                "min_x_range": 200.0,
                "series": [],
            },
        )
        if not empty.empty_plot_suspect:
            _fail("empty mandatory figure was not marked suspect")
        summary = validate_required_figure_coverage([empty])
        if summary["required_figures_generated"] or summary["required_figures_nonempty"]:
            _fail("empty mandatory figure incorrectly passed generated/nonempty gate")
        good = inspect_plot_source_data(
            "01_clean_ablation_repaired/clean_horizontal_error_baseline_vs_raw_repaired.png",
            {
                "figure_path": str(fig),
                "mandatory": True,
                "source_data_roles": ["baseline", "raw"],
                "min_rows": 1000,
                "min_series": 2,
                "min_x_range": 200.0,
                "series": [
                    {"label": "baseline", "x": [i * 0.25 for i in range(1200)], "y": [0.1] * 1200},
                    {"label": "raw", "x": [i * 0.25 for i in range(1200)], "y": [0.09] * 1200},
                ],
            },
        )
        if good.empty_plot_suspect or not good.has_reasonable_time_axis:
            _fail("non-empty mandatory figure failed coverage")
        short_axis = inspect_plot_source_data(
            "01_clean_ablation_repaired/baseline_minus_raw_yaw_diff_repaired.png",
            {
                "figure_path": str(fig),
                "mandatory": True,
                "source_data_roles": ["diff"],
                "min_rows": 1000,
                "min_series": 1,
                "min_x_range": 200.0,
                "series": [{"label": "diff", "x": [0.0] * 1200, "y": [0.1] * 1200}],
            },
        )
        if "unreasonable_time_axis_range" not in short_axis.reason_codes:
            _fail("time-axis range check missing")
    print("audit_n5d_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
