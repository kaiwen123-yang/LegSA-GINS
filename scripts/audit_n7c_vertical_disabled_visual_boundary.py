#!/usr/bin/env python3
"""Audit N7C1 vertical-disabled visual boundary.

中文说明：N7C1 必须能证明 Go2 vertical velocity、position prior、yaw prior 仍然
关闭；缺少 vertical-disabled evidence 时 visual decision 不能通过。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c_plot_coverage import inspect_n7c1_plot_source_data
from legsa_gins.go2_prior.go2_n7c_visual_decision import make_n7c1_visual_decision


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c_vertical_disabled_visual_boundary failed: {message}")


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"nonempty-test-figure")
    return path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c1_vertical_") as tmp_value:
        valid_path = _touch(Path(tmp_value) / "vertical.png")
        missing = inspect_n7c1_plot_source_data(
            "05_vertical_disabled/vertical_velocity_disabled_check.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "vertical_disabled",
                "series": [{"label": "std_vd_999", "x": [0], "y": [1]}],
                "vertical_disabled_evidence": False,
            },
        )
        if "vertical_disabled_evidence_missing" not in missing.reason_codes:
            _fail("missing vertical-disabled evidence did not fail")
        decision = make_n7c1_visual_decision(
            coverage_report={"required_figures_nonempty": True},
            sanity_report={
                "vertical_velocity_disabled_confirmed": False,
                "clean_no_gross_degradation_visual": True,
                "stress_variants_visual_stable": True,
                "visual_sanity_passed": True,
            },
            n7c_decision_report={"status": "ready_with_weak_stress_evidence"},
        )
        if decision["status"] != "visual_validation_failed_vertical_boundary":
            _fail("decision did not stop on vertical boundary")
        valid = inspect_n7c1_plot_source_data(
            "05_vertical_disabled/vd_residual_or_std_vd_timeline.png",
            {
                "figure_path": str(valid_path),
                "figure_category": "vertical_disabled",
                "series": [{"label": "std_vd_disabled_999", "x": [0, 1], "y": [999, 999]}],
                "vertical_disabled_evidence": True,
            },
        )
        if valid.empty_plot_suspect:
            _fail("valid vertical-disabled evidence failed")
    print("audit_n7c_vertical_disabled_visual_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
