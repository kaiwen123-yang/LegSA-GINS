"""Evaluator-only yaw metric repair helpers for PAPER10M1R2C1.

The helpers can rebuild clearly labeled corrected metric tables only when the
yaw audit has classified the issue as evaluator-only. They must not modify
solver NAV, providers, raw data, or original M1R2C tables.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable


CORRECTED_SUFFIX = "corrected_evaluator_only"


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value)


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def aggregate(values: Iterable[float], op: str) -> float:
    values = [float(value) for value in values if math.isfinite(float(value))]
    if not values:
        return math.nan
    if op == "mean":
        return statistics.fmean(values)
    if op == "median":
        return statistics.median(values)
    if op == "p95":
        values = sorted(values)
        index = min(len(values) - 1, max(0, int(round((len(values) - 1) * 0.95))))
        return values[index]
    raise ValueError(op)


def build_corrected_row_table(
    original_rows: list[dict[str, str]],
    yaw_corrections: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    corrected: list[dict[str, Any]] = []
    for row in original_rows:
        out: dict[str, Any] = dict(row)
        correction = yaw_corrections.get(row.get("row_id", ""))
        out["metric_table_role"] = CORRECTED_SUFFIX
        out["yaw_metric_source"] = CORRECTED_SUFFIX
        out["horizontal_up_roll_pitch_modified"] = "false"
        out["solver_nav_modified"] = "false"
        out["provider_modified"] = "false"
        out["row_deleted_for_metric"] = "false"
        if correction:
            out["yaw_transform_applied"] = correction.get("yaw_transform_applied", "")
            out["yaw_rmse_deg_original"] = row.get("yaw_rmse_deg", "")
            out["yaw_rmse_deg"] = correction.get("yaw_rmse_deg", row.get("yaw_rmse_deg", ""))
        else:
            out["yaw_transform_applied"] = "none"
            out["yaw_rmse_deg_original"] = row.get("yaw_rmse_deg", "")
        corrected.append(out)
    return corrected


def summarize_by_method(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    methods = sorted({str(row.get("method_mode_id", "")) for row in rows if row.get("method_mode_id")})
    out: list[dict[str, Any]] = []
    for method in methods:
        subset = [row for row in rows if row.get("method_mode_id") == method and row.get("terminal_status") == "COMPLETED_EVALUABLE"]
        out.append(
            {
                "method_mode_id": method,
                "completed_rows": len(subset),
                "median_horizontal_rmse_m": aggregate((safe_float(row.get("horizontal_rmse_m")) for row in subset), "median"),
                "median_up_rmse_m": aggregate((safe_float(row.get("up_rmse_m")) for row in subset), "median"),
                "median_yaw_rmse_deg": aggregate((safe_float(row.get("yaw_rmse_deg")) for row in subset), "median"),
                "metric_table_role": CORRECTED_SUFFIX,
                "yaw_metric_source": CORRECTED_SUFFIX,
                "paper_claim_allowed": "false_until_human_result_review",
            }
        )
    return out


def summarize_by_degradation_type(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dtype_ids = sorted({str(row.get("degradation_type_id", "")) for row in rows if row.get("degradation_type_id")})
    out: list[dict[str, Any]] = []
    for dtype in dtype_ids:
        subset = [row for row in rows if row.get("degradation_type_id") == dtype and row.get("terminal_status") == "COMPLETED_EVALUABLE"]
        out.append(
            {
                "degradation_type_id": dtype,
                "case_count": len({row.get("case_id", "") for row in subset}),
                "completed_rows": len(subset),
                "median_horizontal_rmse_m": aggregate((safe_float(row.get("horizontal_rmse_m")) for row in subset), "median"),
                "median_yaw_rmse_deg": aggregate((safe_float(row.get("yaw_rmse_deg")) for row in subset), "median"),
                "metric_table_role": CORRECTED_SUFFIX,
                "yaw_metric_source": CORRECTED_SUFFIX,
            }
        )
    return out


def write_no_corrected_metrics_blocker(output_dir: str | Path, reason: str) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    blocker = {
        "corrected_metrics_generated": False,
        "reason": reason,
        "solver_nav_modified": False,
        "provider_modified": False,
        "raw_data_modified": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
    }
    (out / "NO_CORRECTED_METRICS_GENERATED_BLOCKER.md").write_text(
        "# No Corrected Metrics Generated\n\n"
        f"Reason: {reason}\n\n"
        "The yaw audit did not classify the issue as evaluator-only. Original M1R2C tables remain unchanged.\n",
        encoding="utf-8",
    )
    write_json(out / "PAPER10M1R2C1_CORRECTION_MANIFEST.json", blocker)
    return blocker


def rebuild_corrected_metrics(
    *,
    row_table: str | Path,
    output_dir: str | Path,
    yaw_corrections: dict[str, dict[str, Any]],
    evaluator_only: bool,
    blocked_reason: str = "",
) -> dict[str, Any]:
    if not evaluator_only:
        return write_no_corrected_metrics_blocker(output_dir, blocked_reason or "not_evaluator_only")
    original = read_csv_rows(row_table)
    corrected_rows = build_corrected_row_table(original, yaw_corrections)
    out = Path(output_dir)
    write_csv_rows(out / "PAPER10M1R2C1_ROW_LEVEL_RESULT_TABLE_CORRECTED_EVALUATOR_ONLY.csv", corrected_rows)
    write_csv_rows(
        out / "PAPER10M1R2C1_METHOD_LEVEL_SUMMARY_CORRECTED_EVALUATOR_ONLY.csv",
        summarize_by_method(corrected_rows),
    )
    write_csv_rows(
        out / "PAPER10M1R2C1_DEGRADATION_TYPE_SUMMARY_CORRECTED_EVALUATOR_ONLY.csv",
        summarize_by_degradation_type(corrected_rows),
    )
    manifest = {
        "corrected_metrics_generated": True,
        "metric_table_role": CORRECTED_SUFFIX,
        "yaw_metric_source": CORRECTED_SUFFIX,
        "yaw_transform_rows": len(yaw_corrections),
        "horizontal_up_roll_pitch_modified": False,
        "solver_nav_modified": False,
        "provider_modified": False,
        "raw_data_modified": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
    }
    write_json(out / "PAPER10M1R2C1_CORRECTION_MANIFEST.json", manifest)
    return manifest


def decide_m1r2d_gate(
    *,
    yaw_gate_status: str,
    qm_gate_status: str,
    corrected_metrics_generated: bool,
    forbidden_input_violation: bool,
    row_completion_valid: bool,
) -> dict[str, Any]:
    if forbidden_input_violation:
        return {
            "m1r2d_gate": "BLOCKED_FOR_M1R2D",
            "final_decision": "BLOCKED_M1R2C_RESULT_NOT_USABLE_FOR_ABLATION",
            "reason": "forbidden input violation detected",
        }
    if not row_completion_valid:
        return {
            "m1r2d_gate": "BLOCKED_FOR_M1R2D",
            "final_decision": "BLOCKED_M1R2C_RESULT_NOT_USABLE_FOR_ABLATION",
            "reason": "M1R2C row completion is not valid",
        }
    if yaw_gate_status == "BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE":
        return {
            "m1r2d_gate": "BLOCKED_FOR_M1R2D",
            "final_decision": "BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE",
            "reason": "clean yaw remains above gate after evaluator/reference semantic audit",
        }
    if yaw_gate_status.startswith("BLOCKED"):
        return {
            "m1r2d_gate": "BLOCKED_FOR_M1R2D",
            "final_decision": yaw_gate_status,
            "reason": "clean yaw semantics are unresolved",
        }
    if qm_gate_status == "BLOCKED_BAD_A1_COUNTER_SEMANTIC_FAILURE":
        return {
            "m1r2d_gate": "BLOCKED_FOR_M1R2D",
            "final_decision": "BLOCKED_BAD_A1_COUNTER_SEMANTIC_FAILURE",
            "reason": "bad_a1 counter semantics are unresolved",
        }
    if qm_gate_status.startswith("BLOCKED"):
        return {
            "m1r2d_gate": "BLOCKED_FOR_M1R2D",
            "final_decision": "BLOCKED_QM_TRACE_SEMANTIC_FAILURE",
            "reason": "QM trace clean behavior or fields are unresolved",
        }
    if corrected_metrics_generated:
        return {
            "m1r2d_gate": "CONDITIONAL_FOR_M1R2D",
            "final_decision": "CONDITIONAL_PASS_PAPER10M1R2C1_EVALUATOR_ONLY_FIX_READY_FOR_M1R2D_WITH_CAVEATS",
            "reason": "evaluator-only corrected metrics generated with caveats",
        }
    return {
        "m1r2d_gate": "PASS_FOR_M1R2D",
        "final_decision": "PASS_PAPER10M1R2C1_SEMANTICS_REPAIRED_READY_FOR_M1R2D",
        "reason": "original metrics passed semantic gates",
    }
