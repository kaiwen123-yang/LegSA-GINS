#!/usr/bin/env python3
"""Audit N6B source-aware policy refinement.

中文说明：本审计只验证 N6B 策略、toy trace、边界和文件存在性。
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "src/legsa_gins/source_aware/source_aware_n6b_policy.py",
    "src/legsa_gins/source_aware/source_aware_n6b_ablation_matrix.py",
    "src/legsa_gins/source_aware/source_aware_n6b_evaluator.py",
    "src/legsa_gins/source_aware/source_aware_n6b_decision.py",
    "src/legsa_gins/source_aware/source_aware_n6b_spike_response.py",
    "src/legsa_gins/source_aware/source_aware_policy_diagnostics.py",
    "scripts/experiments/run_n6b_source_aware_policy_refinement.py",
    "docs/experiments/n6b_source_aware_policy_refinement.md",
    "docs/experiments/n6b_oim_innovation_covariance_policy.md",
    "docs/experiments/n6b_lsim_metadata_policy.md",
    "docs/experiments/n6b_spike_response_review.md",
    "docs/experiments/n6b_decision.md",
    "docs/experiments/n6b_next_stage_plan.md",
    "docs/codex_prompts/N6B_source_aware_policy_refinement.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n6b_source_aware_policy_refinement failed: {message}")


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
    raw = _run(["git", "ls-files"])
    for line in raw.stdout.splitlines():
        lower = line.lower()
        if any(token in line for token in ["gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "SOURCE_AWARE_WEIGHT_TRACE.csv", "RAW_DOPPLER_VELOCITY_FACTORS.csv"]):
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
    policy = (ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp").read_text(encoding="utf-8")
    gi = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "n6b_conservative_innovation_covariance" not in policy + gi:
        _fail("N6B policy version missing")
    for token in ["innovation_covariance", "innovation.nis", "source_aware_receiver_position_cap", "source_aware_raw_doppler_cap"]:
        if token not in policy + gi + (ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text(encoding="utf-8"):
            _fail(f"N6B C++ policy token missing: {token}")
    exe = _ensure_build()
    with tempfile.TemporaryDirectory(prefix="legsa_n6b_toy_") as tmp:
        proc = _run([str(exe), "--dry-run-source-aware-toy", "--output-dir", tmp], timeout=60)
        if proc.returncode != 0:
            _fail(f"N6B source-aware toy failed: {proc.stderr[-1000:]}")
        trace = Path(tmp) / "SOURCE_AWARE_WEIGHT_TRACE.csv"
        manifest = Path(tmp) / "RUN_MANIFEST.json"
        if not trace.exists() or not manifest.exists():
            _fail("toy did not generate N6B trace/manifest")
        rows = list(csv.DictReader(trace.open("r", encoding="utf-8-sig")))
        if not rows:
            _fail("N6B trace empty")
        scales = [float(row["combined_R_scale"]) for row in rows]
        if max(scales) <= 1.0:
            _fail("toy did not inflate any R")
        if min(scales) >= 15.0:
            _fail("toy R scale appears all max cap")
        if not any(row.get("used_innovation_covariance") in {"1", "true", "True"} for row in rows):
            _fail("toy did not record innovation covariance usage")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("source_aware_policy_version") != "n6b_conservative_innovation_covariance":
            _fail("manifest missing N6B policy version")
        if data.get("paper_performance_claim"):
            _fail("manifest made paper claim")
    _check_no_forbidden_tracked_artifacts()
    _check_no_path_leak()
    print("audit_n6b_source_aware_policy_refinement passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
