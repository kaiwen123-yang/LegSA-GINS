#!/usr/bin/env python3
"""Audit N4H2C-runtime yaw update/config parity tooling with toy evidence.

中文说明：该审计脚本只构造 toy evidence，检查 runtime yaw 诊断工具链和边界字段；
不读取真实 raw data，不修改 solver，也不写入外部 KF-GINS。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.actual_vs_replay_yaw_path import make_actual_vs_replay_yaw_path_report  # noqa: E402
from legsa_gins.evaluation.yaw_runtime_path_diagnostics import classify_yaw_runtime_issue  # noqa: E402
from legsa_gins.source_audit.kfgins_yaw_source_history import (  # noqa: E402
    audit_current_yaw_update_source,
    search_yaw_update_history,
)
from legsa_gins.source_audit.runtime_yaw_update_config_audit import (  # noqa: E402
    compare_actual_and_replay_config,
)


REQUIRED_FILES = [
    "src/legsa_gins/source_audit/runtime_yaw_update_config_audit.py",
    "src/legsa_gins/source_audit/kfgins_yaw_source_history.py",
    "src/legsa_gins/evaluation/actual_vs_replay_yaw_path.py",
    "src/legsa_gins/evaluation/yaw_runtime_path_diagnostics.py",
    "scripts/experiments/run_runtime_yaw_update_config_audit.py",
    "docs/experiments/runtime_yaw_update_config_audit.md",
    "docs/experiments/actual_vs_replay_yaw_path.md",
    "docs/experiments/kfgins_yaw_source_history.md",
    "docs/experiments/n4h2c_runtime_yaw_decision.md",
    "docs/codex_prompts/N4H2C_runtime_yaw_update_config_audit.md",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _assert_boundary(report: dict, name: str) -> None:
    for key in ["trace_solver_input", "output_only_correction", "numerical_performance_claim"]:
        if report.get(key) is not False:
            raise AssertionError(f"{name} {key} must be false")
    if report.get("solver_output_changed") not in {False, None}:
        raise AssertionError(f"{name} solver_output_changed must be false")


def _init_toy_git(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "toy@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Toy"], cwd=root, check=True)
    source = root / "src" / "kf-gins" / "gi_engine.cpp"
    _write(source, "double yaw_res = wrap(euler[2] - gnssdata.yaw); // scheme_C\n")
    subprocess.run(["git", "add", "src/kf-gins/gi_engine.cpp"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "yaw direct"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _write(source, "double yaw_res = wrap(euler[2] - (90 - gnssdata.yaw)); // scheme_C Rscale\n")
    subprocess.run(["git", "add", "src/kf-gins/gi_engine.cpp"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "yaw heading_to_math"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")

    actual_input = [
        {"time": 0.0, "lat": 40.0, "lon": 116.0, "height": 10.0, "vn": 1.0, "ve": 0.0, "vd": 0.0, "yaw": 10.0, "yaw_std": 1.5},
        {"time": 1.0, "lat": 40.0, "lon": 116.00001, "height": 10.0, "vn": 1.0, "ve": 0.0, "vd": 0.0, "yaw": 20.0, "yaw_std": 1.5},
    ]
    replay_input = [
        {"time": 0.0, "lat": 40.0, "lon": 116.0, "height": 10.0, "vn": 1.0, "ve": 0.0, "vd": 0.0, "yaw": 10.0, "yaw_std": 1.5},
        {"time": 1.0, "lat": 40.0, "lon": 116.00001, "height": 10.0, "vn": 1.0, "ve": 0.0, "vd": 0.0, "yaw": 20.0, "yaw_std": 1.5},
    ]
    actual_nav = [
        {"time": 0.0, "lat": 40.0, "lon": 116.0, "height": 10.0, "roll": 0.0, "pitch": 0.0, "yaw": 100.0},
        {"time": 1.0, "lat": 40.0, "lon": 116.00001, "height": 10.0, "roll": 0.0, "pitch": 0.0, "yaw": 110.0},
    ]
    replay_nav = [
        {"time": 0.0, "lat": 40.0, "lon": 116.0, "height": 10.0, "roll": 0.0, "pitch": 0.0, "yaw": 10.0},
        {"time": 1.0, "lat": 40.0, "lon": 116.00001, "height": 10.0, "roll": 0.0, "pitch": 0.0, "yaw": 20.0},
    ]
    yaw_path = make_actual_vs_replay_yaw_path_report(actual_input, replay_input, actual_nav, replay_nav)
    if yaw_path["likely_runtime_yaw_update_or_config_difference"] is not True:
        raise AssertionError("input same/nav diverged should flag runtime/config difference")
    _assert_boundary(yaw_path, "yaw_path")

    missing_config = compare_actual_and_replay_config(None, {"extracted_fields": {"initatt": [0, 0, 1]}})
    if missing_config["actual_config_status"] != "evidence_missing":
        raise AssertionError("missing actual config should be evidence_missing")
    _assert_boundary(missing_config, "missing_config")

    initatt_diff = compare_actual_and_replay_config(
        {"extracted_fields": {"initatt": [0.0, 0.0, 1.0], "antlever": [0.0, 0.0, -0.25]}},
        {"extracted_fields": {"initatt": [0.0, 0.0, 4.0], "antlever": [0.0, 0.0, -0.25]}},
    )
    if initatt_diff["significant_yaw_config_diff"] is not True:
        raise AssertionError("initatt yaw mismatch should be yaw relevant")

    with tempfile.TemporaryDirectory(prefix="legsa_n4h2c_source_") as tmp_name:
        source_root = Path(tmp_name)
        _init_toy_git(source_root)
        current = audit_current_yaw_update_source(source_root)
        history = search_yaw_update_history(source_root)
        if not current["current_yaw_measurement_loaded"]:
            raise AssertionError("toy source should load yaw measurement")
        if history["candidate_commit_count"] < 2:
            raise AssertionError("toy history should detect candidate commits")
        diagnostic = classify_yaw_runtime_issue(
            yaw_path,
            missing_config,
            {"current_source_audit": current, "source_history": history},
        )
        if diagnostic["recommended_next_stage"] not in {
            "N4H2C_source_version_parity_replay",
            "N4H2C_actual_config_recovery_needed",
        }:
            raise AssertionError("unexpected runtime diagnostic recommendation")
        _assert_boundary(current, "current_source")
        _assert_boundary(history, "source_history")
        _assert_boundary(diagnostic, "diagnostic")

    tracked_docs = [
        root / "docs/experiments/runtime_yaw_update_config_audit.md",
        root / "docs/experiments/actual_vs_replay_yaw_path.md",
        root / "docs/experiments/kfgins_yaw_source_history.md",
        root / "docs/experiments/n4h2c_runtime_yaw_decision.md",
        root / "docs/codex_prompts/N4H2C_runtime_yaw_update_config_audit.md",
    ]
    forbidden = [
        str(Path("/home") / "kaiwen") + "/",
        str(Path("/mnt") / "c" / "Users") + "/",
        "C:" + "\\Users",
    ]
    for doc in tracked_docs:
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    try:
        audit(REPO_ROOT)
    except AssertionError as exc:
        print(f"N4H2C runtime yaw update config audit failed: {exc}")
        return 1
    print("N4H2C runtime yaw update config audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
