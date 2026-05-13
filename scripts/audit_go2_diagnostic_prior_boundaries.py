#!/usr/bin/env python3
"""Audit N7B3 Go2 diagnostic prior solver/claim boundaries.

中文说明：本审计固定 diagnostic-only prior 边界，防止 Go2 velocity/yaw-rate
被写成正式 prior、paper result 或 FGO claim。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_diagnostic_prior_boundaries failed: {message}")


def main() -> int:
    required = [
        ROOT / "src/legsa_gins/go2_prior/go2_velocity_prior_diagnostic_builder.py",
        ROOT / "src/legsa_gins/go2_prior/go2_yaw_rate_prior_diagnostic_builder.py",
        ROOT / "src/legsa_gins/go2_prior/go2_diagnostic_activation_runner.py",
        ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp",
        ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp",
        ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
        ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp",
        ROOT / "docs/experiments/n7b3_diagnostic_prior_boundary.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in required)
    for token in [
        "enable_go2_velocity_prior_diagnostic",
        "go2_velocity_prior_diagnostic_path",
        "go2_diagnostic_prior_only",
        "go2_velocity_prior_update_count",
        "yaw_rate_prior_not_activated_due_to_state_model",
        "diagnostic_only",
        "paper_performance_claim",
        "go2_velocity_truth_claim",
        "trace_solver_input",
        "final_v23_output_solver_input",
    ]:
        if token not in text:
            _fail(f"required token missing: {token}")
    forbidden = [
        "paper_performance_claim\": True",
        "go2_velocity_truth_claim\": True",
        "formal_go2_velocity_prior_enabled\": True",
        "fgo\": True",
    ]
    for token in forbidden:
        if token in text:
            _fail(f"forbidden claim token present: {token}")
    print("audit_go2_diagnostic_prior_boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
