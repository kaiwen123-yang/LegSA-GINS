#!/usr/bin/env python3
"""Audit N7B5 Go2 frame equivalence review boundary.

中文说明：frame equivalence 只能使用 Go2/internal and receiver/raw cross-source
consistency；不得把 Go2 velocity 当 truth，不得使用 trace/final_v23 output。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_frame_equivalence_review import review_frame_equivalence


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_frame_equivalence_review failed: {message}")


def main() -> int:
    rows = [
        {
            "time": index * 0.1,
            "aligned_time": index * 0.1,
            "roll_rad": 0.002,
            "pitch_rad": -0.002,
            "yaw_rad": 0.01 * index,
            "yaw_speed_radps": 0.03,
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.1,
            "go2_velocity_2": 0.0,
        }
        for index in range(12)
    ]
    source = [{"time": row["time"], "vn": 1.0, "ve": 0.1, "vd": 0.0} for row in rows]
    _, report = review_frame_equivalence(
        go2_rows=rows,
        frame_score_report={
            "best_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
            "second_best": "yaw_only_rotation_diagnostic_only",
            "frame_status": "ambiguous_but_testable",
            "margin": 0.001,
        },
        receiver_velocity_rows=source,
        raw_doppler_rows=source,
    )
    if not report.get("diagnostic_only") or report.get("formal_go2_velocity_prior"):
        _fail("diagnostic/formal boundary invalid")
    if report.get("go2_velocity_truth_claim") or not report.get("no_truth_claim"):
        _fail("truth claim boundary invalid")
    if report.get("trace_solver_input") or report.get("final_v23_output_solver_input"):
        _fail("trace/final_v23 boundary invalid")
    if report.get("recommended_horizontal_policy") not in {
        "use_best_frame_horizontal_only",
        "use_yaw_only_horizontal_only",
        "do_not_use_go2_velocity",
    }:
        _fail("unexpected horizontal policy")
    print("audit_go2_frame_equivalence_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
