"""N4H4R3C decision logic for metric namespace split audits.

中文说明：本模块只根据 R3C comparison report 给出下一阶段建议；
不做论文性能 claim，不做 tuning，不删 epoch。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    path = Path(value)
    if path.exists() and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _comparison_from_reports(reports: dict[str, Any]) -> dict[str, Any]:
    if "comparison" in reports:
        return _load(reports["comparison"])
    if "corrected_parity_status" in reports:
        return reports
    return {}


def make_metric_namespace_decision(
    reports: dict[str, Any] | str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Map corrected parity-vs-absolute status to the next stage."""

    loaded = _load(reports)
    comparison = _comparison_from_reports(loaded)
    status = comparison.get("corrected_parity_status", "evidence_missing")

    if status == "backbone_parity_passed":
        recommended = "N4H4E_visual_validation_for_source_backed_port"
        candidate: bool | str = True
    elif status == "parity_to_finalv23_passed_absolute_missing":
        recommended = "N4H4R3D_absolute_trace_evaluation_recovery"
        candidate = "conditional"
    elif status == "evaluator_or_reference_mismatch":
        recommended = "N4H4R3D_reference_evaluator_fix"
        candidate = False
    elif status == "port_parity_failed":
        recommended = "N4H4R3D_port_parity_gap_fix"
        candidate = False
    else:
        recommended = "N4H4R3D_metric_namespace_evidence_recovery"
        candidate = False

    blocking = list(comparison.get("blocking_issues", []))
    if not blocking and status not in {"backbone_parity_passed"}:
        blocking.append(status)

    decision = {
        "phase": "N4H4R3C",
        "corrected_parity_status": status,
        "recommended_next_stage": recommended,
        "engineering_backbone_candidate": candidate,
        "blocking_issues": blocking,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_proposed_factor_claim": True,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "tuning": False,
        "epoch_deletion": False,
        "raw_doppler": False,
        "go2_prior": False,
        "lsim_oim": False,
        "source_aware_weighting": False,
        "fgo": False,
    }
    if output_dir is not None:
        _write_json(Path(output_dir) / "PORT_METRIC_NAMESPACE_DECISION_REPORT.json", decision)
    return decision
