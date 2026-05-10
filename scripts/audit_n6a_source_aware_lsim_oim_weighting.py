#!/usr/bin/env python3
"""Audit N6A source-aware LSIM/OIM weighting activation.

中文说明：本审计用 toy 运行证明 source-aware trace 与 R scale 变化存在；不读取
真实 raw data，不提交 runtime artifacts，不编译 reference/final_v23_repo。
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_PY = [
    "src/legsa_gins/source_aware/__init__.py",
    "src/legsa_gins/source_aware/measurement_source_types.py",
    "src/legsa_gins/source_aware/lsim_metric.py",
    "src/legsa_gins/source_aware/oim_metric.py",
    "src/legsa_gins/source_aware/source_weight_policy.py",
    "src/legsa_gins/source_aware/source_weight_trace.py",
    "src/legsa_gins/source_aware/source_aware_ablation_matrix.py",
    "src/legsa_gins/source_aware/source_aware_evaluator.py",
    "src/legsa_gins/source_aware/source_aware_decision.py",
    "src/legsa_gins/source_aware/source_aware_spike_response.py",
]

REQUIRED_CPP = [
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/measurement_source.hpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/source_aware_policy.hpp",
    "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/source_aware_trace.hpp",
    "cpp/legsa_v23_port_core/src/source_aware/source_aware_trace.cpp",
]

REQUIRED_DOCS = [
    "docs/experiments/n6a_source_aware_lsim_oim_weighting.md",
    "docs/experiments/n6a_lsim_oim_definitions.md",
    "docs/experiments/n6a_source_aware_measurement_policy.md",
    "docs/experiments/n6a_spike_response_policy.md",
    "docs/experiments/n6a_ablation_protocol.md",
    "docs/experiments/n6a_decision.md",
    "docs/experiments/n6a_next_stage_plan.md",
    "docs/codex_prompts/N6A_source_aware_lsim_oim_weighting.md",
]

REQUIRED_VARIANTS = {
    "baseline_full_no_raw_no_sourceaware",
    "baseline_plus_raw_no_sourceaware",
    "baseline_plus_raw_lsim_only",
    "baseline_plus_raw_oim_only",
    "baseline_plus_raw_lsim_oim",
    "receiver_velocity_disabled_plus_raw_no_sourceaware",
    "receiver_velocity_disabled_plus_raw_lsim_oim",
    "receiver_velocity_std_scale_5_plus_raw_no_sourceaware",
    "receiver_velocity_std_scale_5_plus_raw_lsim_oim",
    "receiver_velocity_outage_30s_plus_raw_no_sourceaware",
    "receiver_velocity_outage_30s_plus_raw_lsim_oim",
    "receiver_velocity_noise_0p5_plus_raw_no_sourceaware",
    "receiver_velocity_noise_0p5_plus_raw_lsim_oim",
    "baseline_plus_raw_lsim_oim_spike_response_audit",
}


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n6a_source_aware_lsim_oim_weighting failed: {message}")


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
    forbidden = [
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "SOURCE_AWARE_WEIGHT_TRACE.csv",
        "RAW_DOPPLER_VELOCITY_FACTORS.csv",
    ]
    for line in raw.stdout.splitlines():
        if any(token in line for token in forbidden) or line.lower().endswith((".ubx", ".obs", ".nav", ".sp3", ".clk", ".gnss", ".imu", ".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked artifact: {line}")


def _check_no_path_leak() -> None:
    # 中文说明：禁用路径用拼接构造，避免审计脚本自身成为本机绝对路径泄漏。
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
    for rel in [*REQUIRED_PY, *REQUIRED_CPP, *REQUIRED_DOCS]:
        if not (ROOT / rel).exists():
            _fail(f"required file missing: {rel}")
    cmake_text = (ROOT / "cpp/CMakeLists.txt").read_text(encoding="utf-8")
    if "legsa_v23_port_core/src/*.cpp" not in cmake_text:
        _fail("CMake no longer includes port-core source glob")

    sys.path.insert(0, str(ROOT / "src"))
    from legsa_gins.source_aware.source_aware_ablation_matrix import build_n6a_source_aware_ablation_matrix

    matrix = build_n6a_source_aware_ablation_matrix("/tmp/RAW_DOPPLER_VELOCITY_FACTORS.csv", "/tmp/n6a_audit")
    found = {row["variant_id"] for row in matrix["matrix"]}
    if not REQUIRED_VARIANTS.issubset(found):
        _fail("required ablation variants missing")

    exe = _ensure_build()
    with tempfile.TemporaryDirectory(prefix="legsa_n6a_toy_") as tmp:
        proc = _run([str(exe), "--dry-run-source-aware-toy", "--output-dir", tmp], timeout=60)
        if proc.returncode != 0:
            _fail(f"source-aware toy failed: {proc.stderr[-1000:]}")
        trace = Path(tmp) / "SOURCE_AWARE_WEIGHT_TRACE.csv"
        manifest = Path(tmp) / "RUN_MANIFEST.json"
        if not trace.exists() or not manifest.exists():
            _fail("toy did not generate trace/manifest")
        rows = list(csv.DictReader(trace.open("r", encoding="utf-8-sig")))
        if not rows:
            _fail("source-aware toy trace empty")
        if max(float(row["combined_R_scale"]) for row in rows) <= 1.0:
            _fail("source-aware toy did not change R scale")
        sources = {row["source_id"] for row in rows}
        for source in ["receiver_position", "receiver_velocity", "dual_antenna_yaw", "raw_doppler_velocity"]:
            if source not in sources:
                _fail(f"toy missing source trace: {source}")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not data.get("source_aware_weighting_enabled") or data.get("paper_performance_claim"):
            _fail("manifest source-aware flags invalid")
    _check_no_forbidden_tracked_artifacts()
    _check_no_path_leak()
    print("audit_n6a_source_aware_lsim_oim_weighting passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
