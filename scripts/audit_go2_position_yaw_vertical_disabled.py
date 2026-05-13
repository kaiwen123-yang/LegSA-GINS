#!/usr/bin/env python3
"""Audit Go2 position, yaw, and vertical velocity priors remain disabled.

中文说明：扫描 N7C6 相关代码，防止误开启 Go2 position/yaw/vertical prior。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_builder.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_policy.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_jacobian.py",
    "src/legsa_gins/go2_prior/go2_n7c6_decision.py",
    "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py",
    "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp",
    "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_position_yaw_vertical_disabled failed: {message}")


def main() -> int:
    for rel in FILES:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for key in ["go2_position_prior_enabled", "go2_yaw_prior_enabled", "go2_vertical_velocity_prior_enabled"]:
            bad_json = f'"{key}": True'
            bad_yaml = key + ": " + "true"
            if bad_json in text or bad_yaml in text:
                _fail(f"{key} enabled in {rel}")
    print("audit_go2_position_yaw_vertical_disabled passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
