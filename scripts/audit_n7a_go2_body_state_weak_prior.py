#!/usr/bin/env python3
"""Audit N7A Go2 body-state weak-prior foundation.

中文说明：本审计验证 parser、C++ factor、toy EKF activation、runtime-only
边界和文档合同；不读取 trace/final_v23 output 作为 solver 输入。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "src/legsa_gins/go2_state/__init__.py",
    "src/legsa_gins/go2_state/go2_body_state_parser.py",
    "src/legsa_gins/go2_state/go2_quaternion_rpy_check.py",
    "src/legsa_gins/go2_state/go2_time_alignment.py",
    "src/legsa_gins/go2_state/go2_frame_contract.py",
    "src/legsa_gins/go2_state/go2_weak_prior_types.py",
    "src/legsa_gins/go2_state/go2_weak_prior_builder.py",
    "src/legsa_gins/go2_state/go2_weak_prior_evaluator.py",
    "src/legsa_gins/go2_state/go2_weak_prior_decision.py",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/go2_weak_prior_types.hpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/go2_weak_prior_factor.hpp",
    "cpp/legsa_v23_port_core/src/factors/go2_weak_prior_factor.cpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/go2_weak_prior_loader.hpp",
    "cpp/legsa_v23_port_core/src/factors/go2_weak_prior_loader.cpp",
    "scripts/experiments/run_n7a_go2_body_state_weak_prior.py",
    "docs/experiments/n7a_go2_body_state_weak_prior.md",
    "docs/experiments/n7a_go2_source_contract.md",
    "docs/experiments/n7a_go2_attitude_prior_model.md",
    "docs/experiments/n7a_go2_readiness_report.md",
    "docs/experiments/n7a_ablation_protocol.md",
    "docs/experiments/n7a_decision.md",
    "docs/codex_prompts/N7A_go2_body_state_weak_prior.md",
]

REQUIRED_VARIANTS = {
    "baseline_plus_raw_sourceaware_n6b_no_go2",
    "baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior",
    "baseline_plus_raw_no_sourceaware_go2_attitude_weak_prior",
    "raw_doppler_stress_plus_sourceaware_no_go2",
    "raw_doppler_stress_plus_sourceaware_go2_attitude_weak_prior",
    "attitude_prior_std_3deg",
    "attitude_prior_std_5deg",
    "attitude_prior_std_10deg",
}


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7a_go2_body_state_weak_prior failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def _ensure_build() -> Path:
    exe = ROOT / "build/cpp/legsa_v23_port_core_demo"
    if exe.exists():
        return exe
    if _run(["cmake", "-S", "cpp", "-B", "build/cpp"]).returncode != 0:
        _fail("cmake configure failed")
    build = _run(["cmake", "--build", "build/cpp"], timeout=120)
    if build.returncode != 0:
        _fail(f"cmake build failed: {build.stderr[-1000:]}")
    return exe


def _check_no_forbidden_tracked_artifacts() -> None:
    proc = _run(["git", "ls-files"])
    for line in proc.stdout.splitlines():
        lower = line.lower()
        if any(token in line for token in ["by2.txt", "GO2_ATTITUDE_WEAK_PRIORS.csv", "SOURCE_AWARE_WEIGHT_TRACE.csv"]):
            _fail(f"forbidden tracked artifact: {line}")
        if lower.endswith((".ubx", ".obs", ".nav", ".sp3", ".clk", ".gnss", ".imu", ".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked artifact: {line}")


def _check_no_path_leak() -> None:
    for token in [
        "/mnt/c/Users" + "/ykw/Desktop",
        "/mnt/c/Users" + "/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/" + "kaiwen/legsa_external_artifacts",
    ]:
        proc = _run(["git", "grep", "-n", token, "--", "."])
        if proc.returncode == 0:
            _fail(f"local path leak: {token}")


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"required file missing: {rel}")
    matrix_code = (ROOT / "src/legsa_gins/go2_state/go2_weak_prior_evaluator.py").read_text(encoding="utf-8")
    for variant_id in REQUIRED_VARIANTS:
        if variant_id not in matrix_code:
            _fail(f"required ablation variant missing: {variant_id}")
    factor = (ROOT / "cpp/legsa_v23_port_core/src/factors/go2_weak_prior_factor.cpp").read_text(encoding="utf-8")
    gi = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "Go2WeakPriorFactor::designMatrix" not in factor or "EKFUpdate(dz, H, scaled_R)" not in gi:
        _fail("C++ Go2 weak prior factor does not reach EKFUpdate")
    exe = _ensure_build()
    with tempfile.TemporaryDirectory(prefix="legsa_n7a_go2_toy_") as tmp:
        proc = _run([str(exe), "--dry-run-go2-weak-prior-toy", "--output-dir", tmp], timeout=60)
        if proc.returncode != 0:
            _fail(f"Go2 weak-prior toy failed: {proc.stderr[-1000:]}")
        manifest = json.loads((Path(tmp) / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if int(manifest.get("go2_attitude_weak_prior_update_count", 0)) <= 0:
            _fail("toy did not activate Go2 weak prior")
        if manifest.get("go2_position_prior_enabled") or manifest.get("go2_velocity_prior_enabled") or manifest.get("go2_yaw_prior_enabled"):
            _fail("toy enabled forbidden Go2 position/velocity/yaw prior")
    _check_no_forbidden_tracked_artifacts()
    _check_no_path_leak()
    print("audit_n7a_go2_body_state_weak_prior passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
