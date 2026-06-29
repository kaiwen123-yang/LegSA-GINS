#!/usr/bin/env python3
"""Generate PAPER10M1R2C1 clean yaw semantic audit tables."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_semantic_audit import (  # noqa: E402
    METHODS,
    YawReference,
    audit_transform_candidates,
    best_candidate,
    classify_clean_yaw_gate,
    read_15col_yaw,
    read_csv_rows,
    read_eval_nav_yaw,
    read_raw_trace_heading_to_math,
    rmse,
    summarize_errors,
    p95_abs,
    wrap_deg180,
    write_csv_rows,
    yaw_errors_for_reference,
)


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _float_text(value: Any) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(value):
        return ""
    return f"{value:.6f}"


def _runtime_eval_nav(runtime_root: Path, method: str, row_id: str) -> Path:
    return runtime_root / "03_RUNTIME" / method / row_id / "EVAL_NAV.csv"


def _time_offset_candidate(nav_rows: list[dict[str, float]], reference: YawReference) -> dict[str, Any]:
    nav_times = [row["time"] for row in nav_rows]
    nav_yaws = [row["yaw_deg"] for row in nav_rows]
    if not nav_times or not reference.rows:
        return {
            "reference_name": reference.name,
            "reference_role": reference.role,
            "yaw_transform_candidate": "time_offset_candidate",
            "time_offset_sec": "",
            "row_count": 0,
            "yaw_rmse_deg": "",
            "yaw_mean_error_deg": "",
            "yaw_p95_abs_error_deg": "",
            "yaw_max_abs_error_deg": "",
        }
    import bisect

    best: tuple[float, float, list[float]] | None = None
    for offset in range(-120, 121):
        errors: list[float] = []
        for ref in reference.rows:
            target_time = ref["time"] + float(offset)
            index = bisect.bisect_left(nav_times, target_time)
            candidates: list[int] = []
            if index < len(nav_times):
                candidates.append(index)
            if index > 0:
                candidates.append(index - 1)
            if not candidates:
                continue
            nearest = min(candidates, key=lambda item: abs(nav_times[item] - target_time))
            if abs(nav_times[nearest] - target_time) <= 0.25:
                errors.append(wrap_deg180(nav_yaws[nearest] - ref["yaw_deg"]))
        if len(errors) < 100:
            continue
        score = rmse(errors)
        if best is None or score < best[0]:
            best = (score, float(offset), errors)
    if best is None:
        return {
            "reference_name": reference.name,
            "reference_role": reference.role,
            "yaw_transform_candidate": "time_offset_candidate",
            "time_offset_sec": "",
            "row_count": 0,
            "yaw_rmse_deg": "",
            "yaw_mean_error_deg": "",
            "yaw_p95_abs_error_deg": "",
            "yaw_max_abs_error_deg": "",
        }
    score, offset, errors = best
    return {
        "reference_name": reference.name,
        "reference_role": reference.role,
        "yaw_transform_candidate": "time_offset_candidate",
        "time_offset_sec": offset,
        "row_count": len(errors),
        "yaw_rmse_deg": score,
        "yaw_mean_error_deg": sum(errors) / len(errors),
        "yaw_p95_abs_error_deg": p95_abs(errors),
        "yaw_max_abs_error_deg": max(abs(value) for value in errors),
    }


def _load_references(args: argparse.Namespace) -> list[YawReference]:
    refs = [
        read_15col_yaw(args.provider_statusyaw_15col, name="provider_status_yaw_observation", role="source_observation_not_truth")
    ]
    if args.traceyaw_15col:
        refs.append(read_15col_yaw(args.traceyaw_15col, name="traceyaw_15col_reference", role="trace_evaluation_only"))
    if args.raw_trace_csv:
        refs.append(read_raw_trace_heading_to_math(args.raw_trace_csv, name="trace_heading_to_math"))
    return refs


def run(args: argparse.Namespace) -> dict[str, Any]:
    stage_root = Path(args.stage_root)
    yaw_dir = stage_root / "02_YAW_AUDIT"
    yaw_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = Path(args.m1r2c_runtime_root)
    row_rows = read_csv_rows(args.row_table)
    clean_rows = [row for row in row_rows if row.get("case_id") == "BY2_CLEAN_CANONICAL"]
    references = _load_references(args)

    candidate_rows: list[dict[str, Any]] = []
    method_rows: list[dict[str, Any]] = []
    for method in METHODS:
        row = next((item for item in clean_rows if item.get("method_mode_id") == method), None)
        if not row:
            continue
        nav_rows = read_eval_nav_yaw(_runtime_eval_nav(runtime_root, method, row["row_id"]))
        by_reference: dict[str, dict[str, Any]] = {}
        for reference in references:
            stride = 20 if reference.name == "trace_heading_to_math" else 20
            candidates = audit_transform_candidates(nav_rows, reference, nav_stride=stride)
            for candidate in candidates:
                candidate_rows.append({"method_mode_id": method, "row_id": row["row_id"], **candidate})
            candidate_rows.append({"method_mode_id": method, "row_id": row["row_id"], **_time_offset_candidate(nav_rows, reference)})
            by_reference[reference.name] = best_candidate(candidates)
        trace_reference = by_reference.get("trace_heading_to_math") or by_reference.get("traceyaw_15col_reference") or {}
        provider_reference = by_reference.get("provider_status_yaw_observation", {})
        trace_direct_ref = next((ref for ref in references if ref.name == "trace_heading_to_math"), None)
        trace_direct_summary: dict[str, Any] = {}
        if trace_direct_ref is not None:
            trace_direct_summary = summarize_errors(
                yaw_errors_for_reference(nav_rows, trace_direct_ref, transform_name="direct_yaw", nav_stride=20)
            )
        method_rows.append(
            {
                "case_id": row.get("case_id", ""),
                "row_id": row.get("row_id", ""),
                "method_mode_id": method,
                "terminal_status": row.get("terminal_status", ""),
                "m1r2c_original_yaw_rmse_deg": row.get("yaw_rmse_deg", ""),
                "best_provider_reference_transform": provider_reference.get("yaw_transform_candidate", ""),
                "best_provider_reference_rmse_deg": provider_reference.get("yaw_rmse_deg", ""),
                "best_provider_reference_rows": provider_reference.get("row_count", ""),
                "best_trace_reference_transform": trace_reference.get("yaw_transform_candidate", ""),
                "best_trace_reference_rmse_deg": trace_reference.get("yaw_rmse_deg", ""),
                "trace_heading_to_math_rmse_deg": trace_direct_summary.get("yaw_rmse_deg", ""),
                "trace_heading_to_math_rows": trace_direct_summary.get("row_count", ""),
                "clean_yaw_gate_10deg_pass": (
                    float(trace_direct_summary.get("yaw_rmse_deg", math.inf)) <= 10.0
                    if trace_direct_summary
                    else False
                ),
                "evaluator_only_candidate": False,
                "solver_nav_modified": False,
                "provider_modified": False,
                "trace_solver_input": False,
                "notes": "trace/reference used for audit only; solver/provider outputs unchanged",
            }
        )

    gate = classify_clean_yaw_gate(method_rows)
    for row in method_rows:
        row["yaw_gate_status"] = gate["gate_status"]
        row["yaw_gate_reason"] = gate["reason"]

    write_csv_rows(yaw_dir / "PAPER10M1R2C1_CLEAN_YAW_AUDIT_TABLE.csv", method_rows)
    write_csv_rows(yaw_dir / "PAPER10M1R2C1_YAW_TRANSFORM_CANDIDATE_TABLE.csv", candidate_rows)
    write_csv_rows(
        yaw_dir / "PAPER10M1R2C1_CLEAN_YAW_METHOD_MODE_TABLE.csv",
        [
            {
                "method_mode_id": row.get("method_mode_id", ""),
                "row_id": row.get("row_id", ""),
                "terminal_status": row.get("terminal_status", ""),
                "original_yaw_rmse_deg": _float_text(row.get("m1r2c_original_yaw_rmse_deg")),
                "trace_heading_to_math_rmse_deg": _float_text(row.get("trace_heading_to_math_rmse_deg")),
                "best_provider_reference_rmse_deg": _float_text(row.get("best_provider_reference_rmse_deg")),
                "clean_yaw_gate_10deg_pass": row.get("clean_yaw_gate_10deg_pass", False),
                "method_mode_semantic_status": "blocked_clean_yaw" if not row.get("clean_yaw_gate_10deg_pass") else "clean_yaw_pass",
            }
            for row in method_rows
        ],
    )
    report_lines = [
        "# PAPER10M1R2C1 Yaw Semantic Audit Report",
        "",
        "Scope: evaluator-side audit of existing M1R2C clean outputs only.",
        "",
        "Key findings:",
    ]
    for row in method_rows:
        report_lines.append(
            "- {method}: original={orig} deg, provider_best={prov} deg, trace_heading_to_math={trace} deg.".format(
                method=row["method_mode_id"],
                orig=_float_text(row.get("m1r2c_original_yaw_rmse_deg")),
                prov=_float_text(row.get("best_provider_reference_rmse_deg")),
                trace=_float_text(row.get("trace_heading_to_math_rmse_deg")),
            )
        )
    report_lines.extend(
        [
            "",
            f"Yaw gate status: `{gate['gate_status']}`.",
            f"Reason: {gate['reason']}.",
            "",
            "The audit did not modify solver NAV, providers, raw data, epochs, or original M1R2C tables.",
            "Trace is evaluation-only and was not used as solver input.",
        ]
    )
    (yaw_dir / "PAPER10M1R2C1_YAW_SEMANTIC_AUDIT_REPORT.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    _json_dump(
        yaw_dir / "PAPER10M1R2C1_YAW_GATE_SUMMARY.json",
        {
            **gate,
            "clean_method_rows": len(method_rows),
            "candidate_rows": len(candidate_rows),
            "solver_rerun": False,
            "provider_regeneration": False,
            "raw_data_modified": False,
        },
    )
    return gate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--m1r2c-runtime-root", required=True)
    parser.add_argument("--row-table", required=True)
    parser.add_argument("--provider-statusyaw-15col", required=True)
    parser.add_argument("--traceyaw-15col")
    parser.add_argument("--raw-trace-csv")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
