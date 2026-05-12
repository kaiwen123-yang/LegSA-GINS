#!/usr/bin/env python3
"""Audit N7B2 contact v2 does not activate solver priors.

中文说明：N7B2 只输出 readiness/report/figures，禁止 Go2 velocity/yaw prior、
FGO、output-only correction 和 epoch deletion。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_contact_v2_no_solver_activation failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_contact_state_v2.py",
        ROOT / "src/legsa_gins/go2_prior/go2_contact_window_smoother.py",
        ROOT / "src/legsa_gins/go2_prior/go2_contact_velocity_segment_review.py",
        ROOT / "src/legsa_gins/go2_prior/go2_n7b2_decision.py",
        ROOT / "docs/experiments/n7b2_decision.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "go2_velocity_prior_enabled",
        "go2_yaw_prior_enabled",
        "paper_performance_claim",
        "trace_solver_input",
        "final_v23_output_solver_input",
        "fgo",
    ]:
        if token not in text:
            _fail(f"required no-activation token missing: {token}")
    forbidden = [
        "go2_velocity_prior_enabled\": True",
        "go2_yaw_prior_enabled\": True",
        "fgo\": True",
        "output_only_correction\": True",
        "bad_epoch_deletion_for_metric\": True",
    ]
    for token in forbidden:
        if token in text:
            _fail(f"forbidden activation token present: {token}")
    print("audit_go2_contact_v2_no_solver_activation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
