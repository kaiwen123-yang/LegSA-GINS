#!/usr/bin/env python3
"""Audit N7B3 Go2 velocity frame review boundaries.

中文说明：本审计确认 frame review 只做 cross-source consistency，不把 Go2
velocity 写成 truth，也不读取 trace/final_v23 output。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_velocity_frame_review import review_go2_velocity_frame


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_velocity_frame_review failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_velocity_frame_review.py",
        ROOT / "docs/experiments/n7b3_go2_velocity_frame_review.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "cross-source consistency",
        "not truth",
        "no_truth_claim",
        "trace_solver_input",
        "final_v23_output_solver_input",
    ]:
        if token not in text:
            _fail(f"required boundary token missing: {token}")
    go2_rows = []
    receiver_rows = []
    raw_rows = []
    for index in range(20):
        t = index * 0.1
        v = [1.0 + 0.1 * index, 0.3, 0.1]
        go2_rows.append(
            {
                "time": t,
                "aligned_time": t,
                "go2_velocity_0": v[0],
                "go2_velocity_1": v[1],
                "go2_velocity_2": v[2],
                "roll_rad": 0.0,
                "pitch_rad": 0.0,
                "yaw_rad": 0.4,
            }
        )
        receiver_rows.append({"time": t, "vn": v[0], "ve": v[1], "vd": v[2]})
        raw_rows.append({"time": t, "vn": v[0], "ve": v[1], "vd": v[2]})
    report = review_go2_velocity_frame(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_rows,
        raw_doppler_rows=raw_rows,
    )
    if report.get("best_candidate_by_cross_source_consistency") != "go2_velocity_as_world_enu_or_ned_direct":
        _fail("direct frame was not selected in synthetic direct-consistency case")
    if not report.get("no_truth_claim") or report.get("go2_velocity_truth_claim"):
        _fail("truth boundary flags invalid")
    print("audit_go2_velocity_frame_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
