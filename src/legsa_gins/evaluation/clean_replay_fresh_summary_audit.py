"""Fresh clean replay summary recomputation for N4H2G2.

中文说明：本模块从 clean NAV 与 dual official reference 重新计算 summary，
不读取旧 CLEAN_REPLAY_SUMMARY 作为输入，不做 output-only correction。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.fresh_replay_evaluator import _add_gate_booleans
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav
from legsa_gins.evaluation.trajectory_metrics import align_by_timestamp, compute_errors, summary_metrics, write_error_series


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _summary_diff(fresh: dict[str, Any], old: dict[str, Any]) -> dict[str, float | None]:
    diff: dict[str, float | None] = {}
    for key in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]:
        if isinstance(fresh.get(key), (int, float)) and isinstance(old.get(key), (int, float)):
            diff[key] = float(fresh[key]) - float(old[key])
        else:
            diff[key] = None
    return diff


def recompute_clean_summary_from_nav(
    clean_nav: str | Path,
    dual_reference: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    old_clean_summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """Recompute clean summary from NAV rows and write fresh audit outputs."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean_rows = parse_kfgins_nav(clean_nav)
    aligned = align_by_timestamp(clean_rows, dual_reference, max_dt=0.05)
    errors = compute_errors(aligned)
    fresh_summary = _add_gate_booleans(summary_metrics(errors))
    fresh_summary.update(
        {
            "phase": "N4H2G2",
            "aligned_count": fresh_summary.get("count"),
            "reference_profile": "selected_dual_official_reference_direct_identity",
        }
    )
    old_summary = _load_json(old_clean_summary_path)
    diff = _summary_diff(fresh_summary, old_summary)
    stale_status = "old_summary_not_used_fresh_matches" if old_summary and all((value is None or abs(value) <= 1.0e-12) for value in diff.values()) else "old_summary_not_used_recomputed"
    report = {
        "phase": "N4H2G2",
        "fresh_summary_computed": True,
        "fresh_summary": fresh_summary,
        "old_clean_summary_path": "N4H2G_CLEAN_ROOT/CLEAN_REPLAY_SUMMARY.json" if old_clean_summary_path else None,
        "old_clean_summary_used_as_input": False,
        "fresh_vs_old_summary_diff": diff,
        "summary_staleness_status": stale_status,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    write_error_series(errors, out / "CLEAN_REPLAY_FRESH_ERROR_SERIES.csv")
    _write_json(out / "CLEAN_REPLAY_FRESH_SUMMARY.json", fresh_summary)
    _write_json(out / "CLEAN_REPLAY_FRESH_SUMMARY_AUDIT.json", report)
    return report
