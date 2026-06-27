#!/usr/bin/env python3
"""Validate PAPER10M0 smoke output contracts.

中文说明：只检查 runtime-only smoke 输出是否满足契约；不读取 trace 作为
solver 输入，不把 NAV/STD/EVAL_NAV/RUN_MANIFEST 加入 Git 或 export-clean。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


NAV_NAMES = ["LegSA_PORT_NAV.nav", "NAV", "NAV.csv"]
STD_NAMES = ["LegSA_PORT_STD.csv", "STD", "STD.csv"]
METRIC_NAMES = ["EVAL_NAV.csv", "metric.csv", "metrics.json"]
SOURCE_TRACE_NAMES = ["SOURCE_AWARE_WEIGHT_TRACE.csv", "SOURCE_TRACE.csv"]
QM_TRACE_NAMES = ["QM_STATE_ACTION_TRACE.csv", "QM_TRACE.csv"]


def _exists_any(root: Path, names: list[str]) -> bool:
    return any((root / name).is_file() for name in names)


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "RUN_MANIFEST.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def validate_smoke_output(
    output_dir: str | Path,
    *,
    source_trace_required: bool,
    qm_trace_required: bool,
) -> dict[str, Any]:
    root = Path(output_dir)
    manifest = _load_manifest(root)
    nav = _exists_any(root, NAV_NAMES)
    std = _exists_any(root, STD_NAMES)
    metrics = _exists_any(root, METRIC_NAMES)
    run_manifest = (root / "RUN_MANIFEST.json").is_file()
    feature_dump = (root / "FEATURE_FLAGS.json").is_file()
    dataset_dump = (root / "DATASET_ROLE_DUMP.json").is_file()
    source_trace = _exists_any(root, SOURCE_TRACE_NAMES)
    qm_trace = _exists_any(root, QM_TRACE_NAMES)
    forbidden_flags = {
        "trace_used_online": bool(manifest.get("trace_solver_input", False)),
        "final_v23_output_used_as_input": bool(manifest.get("final_v23_output_solver_input", False)),
        "legsa_output_used_as_input": bool(manifest.get("legsa_output_solver_input", False)),
        "benchmark_output_used_as_input": bool(manifest.get("benchmark_output_solver_input", False)),
        "per_case_tuning_used": bool(manifest.get("per_case_tuning", False)),
        "output_only_correction_used": bool(manifest.get("output_only_correction", False)),
        "qa_fallback_as_final_method": bool(manifest.get("enable_qa_fallback", False) or manifest.get("qa_active_mode", False)),
    }
    blockers = []
    required = {
        "nav_exists": nav,
        "std_exists": std,
        "metrics_exists": metrics,
        "run_manifest_exists": run_manifest,
        "feature_flag_dump_exists": feature_dump,
        "dataset_role_dump_exists": dataset_dump,
        "source_trace_exists_or_not_required": source_trace or not source_trace_required,
        "qm_trace_exists_or_not_required": qm_trace or not qm_trace_required,
    }
    for key, passed in required.items():
        if not passed:
            blockers.append(key)
    for key, used in forbidden_flags.items():
        if used:
            blockers.append(key)
    return {
        **required,
        "source_trace_exists": source_trace,
        "qm_trace_exists": qm_trace,
        **forbidden_flags,
        "status": "pass" if not blockers else "fail",
        "blocker": "; ".join(blockers),
    }


def main(argv: list[str] | None = None) -> int:
    if not argv:
        raise SystemExit("usage: paper10m0_output_contract_validator.py <output-dir>")
    result = validate_smoke_output(argv[0], source_trace_required=False, qm_trace_required=False)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
