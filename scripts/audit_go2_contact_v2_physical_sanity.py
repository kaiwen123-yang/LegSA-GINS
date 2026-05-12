#!/usr/bin/env python3
"""Audit N7B2A contact v2 physical sanity boundaries.

中文说明：本审计用于防止 contact v2 过度乐观，尤其是全接触和低交替率场景。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_contact_v2_physical_sanity failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_contact_v2_physical_sanity.py",
        ROOT / "src/legsa_gins/go2_prior/go2_n7b2a_decision.py",
        ROOT / "docs/experiments/n7b2a_contact_v2_physical_sanity.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "all_contact_suspect",
        "contact_too_permissive",
        "alternating_contact_ratio",
        "physical_plausibility_status",
        "go2_velocity_prior_enabled",
        "go2_yaw_prior_enabled",
        "trace_solver_input",
        "final_v23_output_solver_input",
    ]:
        if token not in text:
            _fail(f"required contact sanity token missing: {token}")
    for token in [
        "go2_velocity_prior_enabled\": True",
        "go2_yaw_prior_enabled\": True",
        "fgo\": True",
    ]:
        if token in text:
            _fail(f"forbidden activation token present: {token}")
    print("audit_go2_contact_v2_physical_sanity passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
