#!/usr/bin/env python3
"""Audit N7C has a real EKF activation path for horizontal Go2 velocity.

中文说明：检查 C++ 配置、manifest 和 2D vn/ve EKF update 入口是否存在。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_horizontal_velocity_real_ekf_activation failed: {message}")


def main() -> int:
    engine = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    config = (ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text(encoding="utf-8")
    manifest = (ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp").read_text(encoding="utf-8")
    runner = (ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_activation_runner.py").read_text(encoding="utf-8")
    for token in [
        "enable_go2_horizontal_velocity_prior",
        "go2_horizontal_velocity_prior_path",
        "go2_horizontal_velocity_prior_mode",
    ]:
        if token not in config + runner:
            _fail(f"missing config token: {token}")
    for token in ["horizontal_2d", "H(0, V_ID + 0)", "H(1, V_ID + 1)", "EKFUpdate(dz, H, scaled_R)"]:
        if token not in engine:
            _fail(f"missing EKF token: {token}")
    for token in ["go2_horizontal_velocity_prior_enabled", "go2_horizontal_velocity_prior_update_count"]:
        if token not in manifest:
            _fail(f"missing manifest token: {token}")
    print("audit_go2_horizontal_velocity_real_ekf_activation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
