#!/usr/bin/env python3
"""Audit N7C disables Go2 vertical velocity, yaw, and position priors.

中文说明：N7C 只允许水平速度弱先验，vertical/yaw/position 仍为关闭边界。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_vertical_yaw_position_disabled failed: {message}")


def main() -> int:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_prior_policy.py",
            ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_activation_runner.py",
            ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_ablation.py",
            ROOT / "src/legsa_gins/go2_prior/go2_n7c_decision.py",
            ROOT / "docs/experiments/n7c_horizontal_velocity_policy.md",
            ROOT / "CLAIM_BOUNDARY.md",
        ]
    )
    required = [
        "vertical_velocity_enabled: bool = False",
        "go2_yaw_prior_enabled: bool = False",
        "go2_position_prior_enabled: bool = False",
        "go2_horizontal_velocity_prior_vertical_disabled: true",
        '"go2_yaw_prior_enabled": False',
        '"go2_position_prior_enabled": False',
        "go2_vertical_velocity_prior_enabled",
    ]
    for token in required:
        if token not in text:
            _fail(f"missing disabled token: {token}")
    print("audit_go2_vertical_yaw_position_disabled passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
