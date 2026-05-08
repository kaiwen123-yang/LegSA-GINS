"""Apply the identified official yaw evaluator transform to N4H2 replay NAV.

中文说明：该步骤仍是 diagnostic evaluator parity；不改 replay NAV，不做
output-only correction，也不形成 proposed solver performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.official_case_review_reproduction import load_eval_nav_csv, parse_kfgins_nav
from legsa_gins.evaluation.trajectory_metrics import write_error_series, write_summary
from legsa_gins.evaluation.yaw_evaluator_parity import compute_errors_for_transforms


def _load_replay_nav(path: str | Path) -> list[dict[str, float]]:
    nav_path = Path(path)
    if nav_path.suffix.lower() == ".csv":
        return load_eval_nav_csv(nav_path)
    return parse_kfgins_nav(nav_path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _best_candidate(transform_report: dict[str, Any]) -> dict[str, str]:
    candidate = transform_report.get("best_yaw_transform_candidate") or transform_report
    return {
        "candidate_id": str(candidate.get("candidate_id", "est=identity|ref=identity")),
        "est_transform": str(candidate.get("est_transform", "identity")),
        "ref_transform": str(candidate.get("ref_transform", "identity")),
    }


def apply_official_yaw_transform_to_replay(
    n4h2_replay_nav: str | Path,
    reference: list[dict[str, Any]],
    transform_report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate N4H2 replay NAV with the official evaluator transform."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    candidate = _best_candidate(transform_report)
    replay_rows = _load_replay_nav(n4h2_replay_nav)
    errors = compute_errors_for_transforms(
        replay_rows,
        reference,
        est_transform=candidate["est_transform"],
        ref_transform=candidate["ref_transform"],
    )
    from legsa_gins.evaluation.trajectory_metrics import summary_metrics

    summary = summary_metrics(errors)
    summary.update(
        {
            "phase": "N4R",
            "algorithm_role": "baseline_replay",
            "est_transform": candidate["est_transform"],
            "ref_transform": candidate["ref_transform"],
            "trace_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    )
    yaw = summary.get("yaw_rmse_deg")
    likely_evaluator = isinstance(yaw, (int, float)) and yaw <= 3.0
    likely_runtime = isinstance(yaw, (int, float)) and yaw >= 60.0
    report = {
        "phase": "N4R",
        "candidate_id": candidate["candidate_id"],
        "replay_summary": summary,
        "likely_evaluator_convention_issue": likely_evaluator,
        "likely_runtime_yaw_or_config_issue": likely_runtime,
        "likely_artifact_or_reference_mismatch": bool(not likely_evaluator and not likely_runtime),
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    write_summary(summary, out / "REPLAY_WITH_OFFICIAL_YAW_TRANSFORM_SUMMARY.json")
    write_error_series(errors, out / "REPLAY_WITH_OFFICIAL_YAW_TRANSFORM_ERROR_SERIES.csv")
    _write_json(out / "REPLAY_OFFICIAL_YAW_PARITY_REPORT.json", report)
    return report
