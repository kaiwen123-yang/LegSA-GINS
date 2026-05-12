#!/usr/bin/env python3
"""Audit N7A Go2 weak prior reaches real EKFUpdate path.

中文说明：默认关闭；启用后 roll/pitch weak prior 经 EKFUpdate 进入滤波器。
若 runner 已写 tmp/N7A_LATEST_OUTPUT_DIR.txt，则额外检查真实 replay update_count。
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_weak_prior_real_ekf_activation failed: {message}")


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


def _latest_output_dir() -> Path | None:
    value = os.environ.get("N7A_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def main() -> int:
    options = (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/go2_weak_prior_types.hpp").read_text(encoding="utf-8")
    gi = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "enable_go2_attitude_weak_prior = false" not in options:
        _fail("enable_go2_attitude_weak_prior default is not false")
    for token in ["applyGo2AttitudeWeakPriorForTime", "Go2WeakPriorFactor::residual", "EKFUpdate(dz, H, scaled_R)", "stateFeedback"]:
        if token not in gi:
            _fail(f"EKF activation token missing: {token}")
    if "output_only_correction" in gi:
        _fail("Go2 path mentions output-only correction inside engine")
    exe = _ensure_build()
    with tempfile.TemporaryDirectory(prefix="legsa_n7a_activation_") as tmp:
        proc = _run([str(exe), "--dry-run-go2-weak-prior-toy", "--output-dir", tmp], timeout=60)
        if proc.returncode != 0:
            _fail(f"Go2 activation toy failed: {proc.stderr[-1000:]}")
        manifest = json.loads((Path(tmp) / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if int(manifest.get("go2_attitude_weak_prior_update_count", 0)) <= 0:
            _fail("toy update_count is zero")
        trace = (Path(tmp) / "SOURCE_AWARE_WEIGHT_TRACE.csv").read_text(encoding="utf-8")
        if "go2_attitude_roll_pitch" not in trace:
            _fail("toy source-aware trace lacks Go2 source")
    latest = _latest_output_dir()
    if latest is not None:
        decision = json.loads((latest / "N7A_GO2_WEAK_PRIOR_DECISION_REPORT.json").read_text(encoding="utf-8"))
        build_report = json.loads((latest / "GO2_WEAK_PRIOR_BUILD_REPORT.json").read_text(encoding="utf-8"))
        if build_report.get("activation_allowed") and int(decision.get("go2_attitude_weak_prior_update_count", 0)) <= 0:
            _fail("real run activation_allowed but update_count is zero")
    print("audit_go2_weak_prior_real_ekf_activation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
