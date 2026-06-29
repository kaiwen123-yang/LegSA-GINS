import csv
import json
from pathlib import Path

from legsa_gins.evaluation.qm_trace_semantic_audit import audit_qm_semantics, summarize_clean_qm


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest(root: Path, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "RUN_MANIFEST.json").write_text(json.dumps(payload), encoding="utf-8")


def test_qm_audit_splits_required_present_and_bad_a1_semantics(tmp_path):
    row_table = tmp_path / "rows.csv"
    _write_csv(
        row_table,
        [
            {
                "row_id": "r0",
                "case_id": "BY2_CLEAN_CANONICAL",
                "degradation_type_id": "CLEAN",
                "method_mode_id": "strong_dual_yaw_baseline",
                "terminal_status": "COMPLETED_EVALUABLE",
                "qm_trace_exists_or_not_required": "true",
                "source_trace_exists_or_not_required": "true",
                "bad_a1_consumed_count": "7",
                "fallback_count": "0",
                "recovery_count": "0",
            },
            {
                "row_id": "r1",
                "case_id": "BY2_CLEAN_CANONICAL",
                "degradation_type_id": "CLEAN",
                "method_mode_id": "legsa_full_candidate_with_qm",
                "terminal_status": "COMPLETED_EVALUABLE",
                "qm_trace_exists_or_not_required": "true",
                "source_trace_exists_or_not_required": "true",
                "bad_a1_consumed_count": "3",
                "fallback_count": "0",
                "recovery_count": "2",
            },
        ],
    )
    runtime = tmp_path / "runtime"
    _write_manifest(runtime / "03_RUNTIME/strong_dual_yaw_baseline/r0", {"yaw_REJECT": 7, "yaw_update_count": 10})
    full_root = runtime / "03_RUNTIME/legsa_full_candidate_with_qm/r1"
    _write_manifest(
        full_root,
        {
            "enable_multi_state_qm": True,
            "yaw_REJECT": 3,
            "yaw_update_count": 10,
            "qm_action_count_by_source": {"dual_antenna_yaw": 10},
            "qm_downweight_count_by_source": {"dual_antenna_yaw": 4},
            "qm_recovery_count_by_source": {"dual_antenna_yaw": 2},
            "qm_reject_count_by_source": {"dual_antenna_yaw": 3},
        },
    )
    (full_root / "QM_STATE_ACTION_TRACE.csv").write_text("time,source,action\n", encoding="utf-8")
    rows = audit_qm_semantics(row_table, runtime)
    strong = next(row for row in rows if row["method_mode_id"] == "strong_dual_yaw_baseline")
    assert strong["qm_trace_required"] is False
    assert strong["qm_trace_not_required"] is True
    assert strong["bad_a1_maps_to_yaw_reject_count"] is True
    assert strong["bad_a1_consumed_count_valid_for_claim"] is False
    summary = summarize_clean_qm(rows)
    assert summary["clean_qm_transparency_pass"] is False
