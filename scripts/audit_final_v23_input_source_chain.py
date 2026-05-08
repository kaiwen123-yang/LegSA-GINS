#!/usr/bin/env python3
"""Audit Stage N4H1 final_v23 input source-chain and yaw generation.

中文说明：本审计只用 toy 数据验证 15-column `.gnss`、source-chain report 和
yaw-chain report；不依赖真实 BY2 或 final_v23 本地路径。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/final_v23_input_audit.py",
    "src/legsa_gins/evaluation/final_v23_yaw_chain_audit.py",
    "scripts/experiments/run_final_v23_input_source_audit.py",
    "docs/experiments/final_v23_input_source_chain.md",
    "docs/experiments/final_v23_yaw_generation_chain.md",
    "docs/codex_prompts/N4H1_final_v23_input_yaw_audit.md",
    "tests/unit/test_final_v23_input_audit.py",
    "tests/unit/test_final_v23_yaw_chain_audit.py",
    "tests/integration/test_final_v23_input_source_audit_toy.py",
    "tests/audit/test_final_v23_input_source_chain.py",
]

REQUIRED_OUTPUTS = [
    "PROCESS_DATA_SOURCE_MAP.json",
    "FINAL_V23_INPUT_SOURCE_REPORT.json",
    "FINAL_V23_YAW_CHAIN_REPORT.json",
    "final_v23_input_source_chain_review.md",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("N4H1 audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4h1_audit_"))
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/experiments/run_final_v23_input_source_audit.py"),
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
            print("N4H1 audit failed. Toy runner failed.")
            print(completed.stdout)
            print(completed.stderr)
            return 1

        missing_outputs = [rel_path for rel_path in REQUIRED_OUTPUTS if not (tmp / rel_path).exists()]
        if missing_outputs:
            print("N4H1 audit failed. Missing outputs:")
            for rel_path in missing_outputs:
                print(f"- {rel_path}")
            return 1

        source_map = _load_json(tmp / "PROCESS_DATA_SOURCE_MAP.json")
        input_report = _load_json(tmp / "FINAL_V23_INPUT_SOURCE_REPORT.json")
        yaw_report = _load_json(tmp / "FINAL_V23_YAW_CHAIN_REPORT.json")
        if input_report.get("position_source_status") != "matched_gnss1_status":
            print("N4H1 audit failed. Position source did not match gnss1 status.")
            return 1
        if input_report.get("position_std_source_status") != "matched_pos_acc_h_pos_acc_v":
            print("N4H1 audit failed. Position std source did not match pos_acc fields.")
            return 1
        if yaw_report.get("yaw_column_source_status") != "matched_a1_dual_diff":
            print("N4H1 audit failed. A1_dual_diff yaw did not match toy final .gnss yaw.")
            return 1
        if input_report.get("trace_solver_input") is not False:
            print("N4H1 audit failed. trace_solver_input is not false.")
            return 1
        if input_report.get("final_v23_is_proposed") is not False:
            print("N4H1 audit failed. final_v23_is_proposed is not false.")
            return 1
        if input_report.get("numerical_performance_claim") is not False:
            print("N4H1 audit failed. numerical_performance_claim is not false.")
            return 1
        if not source_map.get("found_position_mapping") or not source_map.get("found_yaw_mapping"):
            print("N4H1 audit failed. Toy process_data source map is incomplete.")
            return 1
        review = (tmp / "final_v23_input_source_chain_review.md").read_text(encoding="utf-8")
        for needle in ["runtime actual input", "upstream generation fields", "trace_solver_input: false"]:
            if needle not in review:
                print(f"N4H1 audit failed. Review missing: {needle}")
                return 1
        for phrase in ["performance achieved", "proposed solver performance", "raw Doppler implemented"]:
            if phrase in review:
                print(f"N4H1 audit failed. Forbidden review phrase: {phrase}")
                return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("N4H1 final_v23 input source-chain audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
