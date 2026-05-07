#!/usr/bin/env python3
"""Audit Stage N4F BY2 filter-core diagnostic trial.

中文说明：本审计只用 toy 输入验证 N4F 产物和边界，不依赖真实 BY2 路径。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REQUIRED_FILES = [
    "scripts/experiments/run_by2_filter_core_trial.py",
    "src/legsa_gins/experiments/__init__.py",
    "src/legsa_gins/experiments/by2_filter_trial.py",
    "src/legsa_gins/evaluation/trajectory_metrics.py",
    "src/legsa_gins/evaluation/case_review_report.py",
    "cpp/include/legsa_gins/readers/standard_imu_increment_reader.hpp",
    "cpp/src/readers/standard_imu_increment_reader.cpp",
    "docs/experiments/by2_filter_core_trial.md",
    "docs/codex_prompts/N4F_by2_filter_core_trial.md",
    "configs/experiments/by2_filter_core_trial.example.yaml",
    "tests/unit/test_trajectory_metrics.py",
    "tests/unit/test_case_review_report.py",
    "tests/integration/test_by2_filter_trial_toy.py",
    "tests/audit/test_by2_filter_core_trial.py",
]

REQUIRED_OUTPUTS = [
    "run/LegSA_NAV.nav",
    "run/LegSA_STD.csv",
    "run/EVAL_NAV.csv",
    "run/RUN_MANIFEST.json",
    "evaluation/error_series.csv",
    "evaluation/summary.json",
    "case_review.md",
    "BY2_FILTER_TRIAL_MANIFEST.json",
]

FORBIDDEN_TRUE_FLAGS = [
    "trace_solver_input",
    "raw_doppler_claim",
    "go2_prior_claim",
    "source_aware_weighting_claim",
    "fgo_smoother_claim",
    "numerical_performance_claim",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "receiver_imu_as_body_imu",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("N4F audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4f_audit_"))
    try:
        command = [
            sys.executable,
            str(root / "scripts/experiments/run_by2_filter_core_trial.py"),
            "--toy",
            "--output-dir",
            str(tmp),
            "--max-filter-epochs",
            "140",
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print("N4F audit failed. Toy trial did not run.")
            print(completed.stdout)
            print(completed.stderr)
            return 1

        missing_outputs = [rel_path for rel_path in REQUIRED_OUTPUTS if not (tmp / rel_path).exists()]
        if missing_outputs:
            print("N4F audit failed. Missing outputs:")
            for rel_path in missing_outputs:
                print(f"- {rel_path}")
            return 1

        run_manifest = _load_json(tmp / "run/RUN_MANIFEST.json")
        trial_manifest = _load_json(tmp / "BY2_FILTER_TRIAL_MANIFEST.json")
        summary = _load_json(tmp / "evaluation/summary.json")
        for flag in FORBIDDEN_TRUE_FLAGS:
            if run_manifest.get(flag) is not False and trial_manifest.get(flag) is not False:
                print(f"N4F audit failed. Forbidden flag is not false: {flag}")
                return 1
        if trial_manifest.get("trace_evaluation_only") is not True:
            print("N4F audit failed. trace_evaluation_only is not true.")
            return 1
        if summary.get("count", 0) <= 100:
            print("N4F audit failed. Toy alignment count is too small.")
            return 1

        case_review = (tmp / "case_review.md").read_text(encoding="utf-8")
        forbidden_phrases = [
            "formal performance achieved",
            "final_v23 parity achieved",
            "raw Doppler implemented",
            "Go2 prior implemented",
        ]
        for phrase in forbidden_phrases:
            if phrase in case_review:
                print(f"N4F audit failed. Forbidden case_review phrase: {phrase}")
                return 1
        if "dual_final_v23 horizontal_rmse_m = 0.353" not in case_review:
            print("N4F audit failed. case_review lacks final_v23 context.")
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("N4F BY2 filter-core trial audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
