"""PAPER10M1R2C1 QM trace and A1 counter semantic audit helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


METHODS_REQUIRING_QM = {"legsa_full_candidate_with_qm"}
METHODS_REQUIRING_SOURCE_TRACE = {"legsa_without_qm", "legsa_full_candidate_with_qm"}


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


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value)


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_count_object(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        out: dict[str, int] = {}
        for key, item in value.items():
            if isinstance(item, (int, float)):
                out[str(key)] = int(item)
        return out
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parse_count_object(parsed)


def sum_count_object(value: Any) -> int:
    return sum(parse_count_object(value).values())


def load_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def row_runtime_dir(runtime_root: str | Path, method_mode_id: str, row_id: str) -> Path:
    return Path(runtime_root) / "03_RUNTIME" / method_mode_id / row_id


def audit_qm_semantics(row_table: str | Path, runtime_root: str | Path) -> list[dict[str, Any]]:
    rows = read_csv_rows(row_table)
    audit_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("terminal_status") != "COMPLETED_EVALUABLE":
            continue
        method = row.get("method_mode_id", "")
        root = row_runtime_dir(runtime_root, method, row.get("row_id", ""))
        manifest = load_json(root / "RUN_MANIFEST.json")
        qm_required = method in METHODS_REQUIRING_QM or truthy(manifest.get("enable_multi_state_qm"))
        source_required = method in METHODS_REQUIRING_SOURCE_TRACE or truthy(manifest.get("source_aware_trace_enabled"))
        qm_file_exists = (root / "QM_STATE_ACTION_TRACE.csv").is_file() or (root / "QM_TRACE.csv").is_file()
        source_file_exists = (root / "SOURCE_AWARE_WEIGHT_TRACE.csv").is_file() or (root / "SOURCE_TRACE.csv").is_file()
        qm_action_count = sum_count_object(manifest.get("qm_action_count_by_source", {}))
        qm_state_count = {
            "normal": sum_count_object(manifest.get("qm_normal_count_by_source", {})),
            "downweight": sum_count_object(manifest.get("qm_downweight_count_by_source", {})),
            "reject": sum_count_object(manifest.get("qm_reject_count_by_source", {})),
            "hold": sum_count_object(manifest.get("qm_hold_count_by_source", {})),
            "recovery": sum_count_object(manifest.get("qm_recovery_count_by_source", {})),
            "fallback": sum_count_object(manifest.get("qm_fallback_count_by_source", {})),
        }
        yaw_update_count = safe_int(manifest.get("yaw_update_count"))
        yaw_normal_count = safe_int(manifest.get("yaw_NORMAL"))
        yaw_downweight_count = safe_int(manifest.get("yaw_DOWNWEIGHT"))
        yaw_reject_count = safe_int(manifest.get("yaw_REJECT"))
        bad_a1_count = safe_int(row.get("bad_a1_consumed_count"))
        bad_a1_maps_to_yaw_reject = bool(bad_a1_count == yaw_reject_count and yaw_reject_count > 0)
        audit_rows.append(
            {
                "row_id": row.get("row_id", ""),
                "case_id": row.get("case_id", ""),
                "degradation_type_id": row.get("degradation_type_id", ""),
                "method_mode_id": method,
                "qm_trace_required": qm_required,
                "qm_trace_file_exists": qm_file_exists,
                "qm_trace_has_state_actions": qm_action_count > 0 or any(value > 0 for value in qm_state_count.values()),
                "qm_trace_not_required": not qm_required,
                "qm_trace_exists_or_not_required_original": row.get("qm_trace_exists_or_not_required", ""),
                "source_trace_required": source_required,
                "source_trace_file_exists": source_file_exists,
                "source_trace_not_required": not source_required,
                "source_trace_exists_or_not_required_original": row.get("source_trace_exists_or_not_required", ""),
                "bad_a1_consumed_count_original": bad_a1_count,
                "bad_a1_consumed_count_defined": False,
                "bad_a1_consumed_count_valid_for_claim": False,
                "bad_a1_consumed_count_should_be_renamed": bad_a1_maps_to_yaw_reject,
                "bad_a1_maps_to_yaw_reject_count": bad_a1_maps_to_yaw_reject,
                "yaw_update_count": yaw_update_count,
                "yaw_normal_count": yaw_normal_count,
                "yaw_downweight_count": yaw_downweight_count,
                "yaw_reject_count": yaw_reject_count,
                "a1_diagnostic_count_candidate": yaw_update_count,
                "a1_accepted_count_candidate": max(0, yaw_update_count - yaw_reject_count),
                "a1_rejected_count_candidate": yaw_reject_count,
                "qm_state_count_summary_runtime": qm_state_count,
                "qm_action_count_by_source": manifest.get("qm_action_count_by_source", {}),
                "qm_downweight_count_by_source": manifest.get("qm_downweight_count_by_source", {}),
                "qm_reject_count_by_source": manifest.get("qm_reject_count_by_source", {}),
                "qm_recovery_count_by_source": manifest.get("qm_recovery_count_by_source", {}),
                "fallback_count_original": row.get("fallback_count", ""),
                "recovery_count_original": row.get("recovery_count", ""),
                "qa_a1_quality_source": manifest.get("qa_a1_quality_source", ""),
                "trace_solver_input": bool(manifest.get("trace_solver_input", False)),
                "final_v23_output_solver_input": bool(manifest.get("final_v23_output_solver_input", False)),
                "legsa_output_solver_input": bool(manifest.get("legsa_output_solver_input", False)),
                "notes": semantic_notes(
                    qm_required=qm_required,
                    qm_file_exists=qm_file_exists,
                    bad_a1_maps_to_yaw_reject=bad_a1_maps_to_yaw_reject,
                    method=method,
                ),
            }
        )
    return audit_rows


def semantic_notes(*, qm_required: bool, qm_file_exists: bool, bad_a1_maps_to_yaw_reject: bool, method: str) -> str:
    notes: list[str] = []
    if not qm_required and not qm_file_exists:
        notes.append("qm_trace_not_required")
    if qm_required and qm_file_exists:
        notes.append("qm_trace_required_and_present")
    if bad_a1_maps_to_yaw_reject:
        notes.append("bad_a1_consumed_count_is_yaw_reject_count_not_consumed_count")
    if method != "legsa_full_candidate_with_qm":
        notes.append("baseline_or_no_qm_method_must_not_use_qm_counters_for_claim")
    return "; ".join(notes)


def summarize_clean_qm(audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [row for row in audit_rows if row.get("case_id") == "BY2_CLEAN_CANONICAL"]
    full = [row for row in clean if row.get("method_mode_id") == "legsa_full_candidate_with_qm"]
    full_row = full[0] if full else {}
    full_downweight = sum_count_object(full_row.get("qm_downweight_count_by_source", {}))
    full_recovery = sum_count_object(full_row.get("qm_recovery_count_by_source", {}))
    full_reject = sum_count_object(full_row.get("qm_reject_count_by_source", {}))
    non_qm_bad = [
        row
        for row in clean
        if row.get("method_mode_id") != "legsa_full_candidate_with_qm"
        and safe_int(row.get("bad_a1_consumed_count_original")) > 0
    ]
    return {
        "clean_rows": len(clean),
        "full_qm_downweight_count": full_downweight,
        "full_qm_recovery_count": full_recovery,
        "full_qm_reject_count": full_reject,
        "non_qm_rows_with_bad_a1_consumed_original": len(non_qm_bad),
        "qm_semantics_clarified": True,
        "bad_a1_counter_valid_for_claim": False,
        "clean_qm_transparency_pass": full_downweight == 0 and full_recovery == 0 and full_reject == 0,
    }


def qm_gate_status(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary.get("qm_semantics_clarified"):
        return {
            "qm_gate_status": "BLOCKED_QM_TRACE_SEMANTIC_FAILURE",
            "reason": "QM trace semantics were not clarified",
        }
    if summary.get("bad_a1_counter_valid_for_claim"):
        return {
            "qm_gate_status": "BLOCKED_BAD_A1_COUNTER_SEMANTIC_FAILURE",
            "reason": "bad_a1_consumed_count remains claim-usable despite ambiguous semantics",
        }
    if not summary.get("clean_qm_transparency_pass"):
        return {
            "qm_gate_status": "BLOCKED_QM_TRACE_SEMANTIC_FAILURE",
            "reason": "clean full-QM row has non-transparent downweight/recovery/reject behavior",
        }
    return {"qm_gate_status": "QM_SEMANTICS_CLARIFIED", "reason": "QM fields are clarified and claim-blocked as needed"}
