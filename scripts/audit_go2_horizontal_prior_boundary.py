#!/usr/bin/env python3
"""Audit N7B5 horizontal Go2 velocity prior boundary.

中文说明：horizontal-only prior 必须关闭 vertical component、保持 diagnostic-only，
且不得声明 formal Go2 velocity prior。
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_horizontal_velocity_prior_builder import build_horizontal_velocity_diagnostic_priors


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_horizontal_prior_boundary failed: {message}")


def _rows() -> list[dict[str, object]]:
    out = []
    for index in range(8):
        out.append(
            {
                "time": index * 0.1,
                "aligned_time": index * 0.1,
                "roll_rad": 0.0,
                "pitch_rad": 0.0,
                "yaw_rad": 0.0,
                "go2_velocity_0": 1.0,
                "go2_velocity_1": 0.2,
                "go2_velocity_2": 0.1,
            }
        )
    return out


def _prob_rows() -> list[dict[str, object]]:
    return [
        {
            "time": index * 0.1,
            "model_id": "ensemble_probability",
            "support_probability": 0.7 if index % 2 == 0 else 0.45,
            "confidence_score": 0.55 if index % 2 == 0 else 0.35,
        }
        for index in range(8)
    ]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="go2_horizontal_prior_") as tmp:
        paths, report = build_horizontal_velocity_diagnostic_priors(
            go2_rows=_rows(),
            frame_equivalence_report={
                "primary_frame": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
                "secondary_frame": "yaw_only_rotation_diagnostic_only",
                "recommended_horizontal_policy": "use_best_frame_horizontal_only",
                "top_candidate_difference": {"horizontal_rmse_mps": 0.02},
            },
            frame_score_report={
                "best_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
                "second_best": "yaw_only_rotation_diagnostic_only",
                "candidates": {},
            },
            probability_model_report={
                "selected_contact_probability_model": "ensemble_probability",
                "contact_probability_model_ready": True,
            },
            probability_timeseries=_prob_rows(),
            output_dir=tmp,
        )
        if not report.get("diagnostic_only") or report.get("formal_activation_allowed"):
            _fail("report boundary flags invalid")
        if not report.get("vertical_velocity_disabled") or report.get("formal_go2_velocity_prior"):
            _fail("vertical disabled/formal prior flags invalid")
        with paths["best_frame_horizontal_only"].open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            _fail("horizontal prior CSV has no rows")
        if any(float(row["std_vd"]) < 999.0 for row in rows):
            _fail("horizontal prior did not disable vertical std")
        report_json = json.loads((Path(tmp) / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json").read_text())
        if report_json.get("go2_velocity_truth_claim") or report_json.get("paper_performance_claim"):
            _fail("truth or performance claim leaked")
    print("audit_go2_horizontal_prior_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
