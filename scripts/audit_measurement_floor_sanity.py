#!/usr/bin/env python3
"""Audit Stage N4H0 receiver-native measurement-floor sanity.

中文说明：本审计只用 toy 输入验证 measurement floor 产物和边界，不依赖真实 BY2 路径。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/measurement_floor.py",
    "scripts/experiments/run_by2_measurement_floor_sanity.py",
    "docs/experiments/by2_measurement_floor_sanity.md",
    "docs/codex_prompts/N4H0_measurement_floor_sanity.md",
    "tests/unit/test_measurement_floor.py",
    "tests/integration/test_by2_measurement_floor_toy.py",
    "tests/audit/test_measurement_floor_sanity.py",
]

REQUIRED_OUTPUTS = [
    "GNSS1_MEASUREMENT_FLOOR_EVAL_NAV.csv",
    "GNSS2_MEASUREMENT_FLOOR_EVAL_NAV.csv",
    "GNSS1_MEASUREMENT_FLOOR_SUMMARY.json",
    "GNSS2_MEASUREMENT_FLOOR_SUMMARY.json",
    "HEADING_FLOOR_CANDIDATE_REPORT.json",
    "MEASUREMENT_FLOOR_SANITY_REPORT.json",
    "measurement_floor_case_review.md",
]

FORBIDDEN_TRUE_FLAGS = [
    "trace_solver_input",
    "proposed_solver_output",
    "raw_doppler_claim",
    "go2_prior_claim",
    "source_aware_weighting_claim",
    "fgo_smoother_claim",
    "numerical_performance_claim",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("N4H0 audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4h0_audit_"))
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/experiments/run_by2_measurement_floor_sanity.py"),
                "--toy",
                "--output-dir",
                str(tmp),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print("N4H0 audit failed. Toy measurement-floor run failed.")
            print(completed.stdout)
            print(completed.stderr)
            return 1

        missing_outputs = [rel_path for rel_path in REQUIRED_OUTPUTS if not (tmp / rel_path).exists()]
        if missing_outputs:
            print("N4H0 audit failed. Missing outputs:")
            for rel_path in missing_outputs:
                print(f"- {rel_path}")
            return 1

        report = _load_json(tmp / "MEASUREMENT_FLOOR_SANITY_REPORT.json")
        heading_report = _load_json(tmp / "HEADING_FLOOR_CANDIDATE_REPORT.json")
        for flag in FORBIDDEN_TRUE_FLAGS:
            if report.get(flag) is not False:
                print(f"N4H0 audit failed. Forbidden flag is not false: {flag}")
                return 1
        if report.get("trace_evaluation_only") is not True:
            print("N4H0 audit failed. trace_evaluation_only is not true.")
            return 1
        if heading_report.get("formal_heading_offset_selected") is not False:
            print("N4H0 audit failed. formal heading offset was selected.")
            return 1

        case_review = (tmp / "measurement_floor_case_review.md").read_text(encoding="utf-8")
        required_case_strings = [
            "primary_benchmark: dual_final_v23_reference_context",
            "proposed_solver_output: false",
            "trace_solver_input: false",
            "formal performance claim: false",
        ]
        for needle in required_case_strings:
            if needle not in case_review:
                print(f"N4H0 audit failed. case_review missing: {needle}")
                return 1
        forbidden_phrases = [
            "formal performance achieved",
            "final_v23 parity achieved",
            "proposed solver performance",
            "raw Doppler implemented",
        ]
        for phrase in forbidden_phrases:
            if phrase in case_review:
                print(f"N4H0 audit failed. Forbidden case_review phrase: {phrase}")
                return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("N4H0 measurement floor sanity audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
