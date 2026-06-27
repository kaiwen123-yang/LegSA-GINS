#!/usr/bin/env python3
"""Build locked PAPER10M1 BY2 queue drafts from PAPER10M0 mode mappings.

中文说明：队列草案默认 locked，run_allowed_now=false；本模块不执行 solver、
不生成退化输入，也不启动 PAPER10M1。
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper10m0_method_mode_loader import METHOD_MODE_IDS


CASE_FAMILY_COUNTS = {
    "normal": 1,
    "outage": 4,
    "downsample": 3,
    "position_noise": 30,
    "position_spike": 30,
    "position_std": 3,
    "yaw_noise": 30,
    "yaw_std": 3,
    "module_disable": 6,
    "mixed": 10,
}


def canonical_by2_cases() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for family, count in CASE_FAMILY_COUNTS.items():
        for index in range(count):
            case_id = "BY2_NORMAL_CLEAN" if family == "normal" else f"BY2_{family.upper()}_{index + 1:03d}"
            rows.append({"case_family": family, "case_id": case_id})
    if len(rows) != 120:
        raise AssertionError(f"canonical BY2 queue expected 120 cases, got {len(rows)}")
    return rows


def feature_flags_hash(flags: dict[str, Any]) -> str:
    blob = json.dumps(flags, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def build_paper10m1_queue(mode_flags: dict[str, dict[str, Any]], output_root_alias: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cases = canonical_by2_cases()
    for mode_id in METHOD_MODE_IDS:
        flags = mode_flags.get(mode_id, {})
        flag_hash = feature_flags_hash(flags)
        for case in cases:
            queue_id = f"PAPER10M1_BY2_{mode_id}_{case['case_id']}"
            rows.append(
                {
                    "queue_id": queue_id,
                    "dataset": "BY2",
                    "case_family": case["case_family"],
                    "case_id": case["case_id"],
                    "method_mode_id": mode_id,
                    "feature_flags_hash": flag_hash,
                    "runner_config_path": f"{output_root_alias}/runtime_configs/{mode_id}/{case['case_id']}.yaml",
                    "expected_output_root": f"{output_root_alias}/outputs/{mode_id}/{case['case_id']}",
                    "required_inputs": "BY2 approved providers only",
                    "forbidden_inputs": "trace_online; final_v23_output; LegSA_output; benchmark_output; per_case_tuning; output_only_correction",
                    "trace_eval_only": "true",
                    "run_allowed_now": "false",
                    "run_allowed_in_paper10m1": "true",
                    "human_approval_required": "true",
                    "notes": "Queue draft only; PAPER10M0 does not execute this row.",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def smoke_queue() -> list[dict[str, str]]:
    return [
        {
            "row_id": f"PAPER10M0_SMOKE_{index:02d}",
            "dataset": "BY2",
            "case_family": "normal_smoke",
            "case_id": "BY2_NORMAL_CLEAN_SMOKE",
            "method_mode_id": mode_id,
            "run_allowed_now": "true_paper10m0_smoke_only",
            "run_allowed_in_paper10m1": "false",
            "human_approval_required_for_full_matrix": "true",
        }
        for index, mode_id in enumerate(METHOD_MODE_IDS, start=1)
    ]


def main() -> int:
    flags = {mode_id: {} for mode_id in METHOD_MODE_IDS}
    rows = build_paper10m1_queue(flags, "<PAPER10M1_FULL_MATRIX_ROOT>")
    print(json.dumps({"rows": len(rows), "smoke_rows": len(smoke_queue())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
