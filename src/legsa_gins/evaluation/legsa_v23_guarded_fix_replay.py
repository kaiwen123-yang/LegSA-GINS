"""Guarded formula fix clean replay helpers for N4H4D3.

中文说明：默认 solver replay 不启用 diagnostic variants；输出只作为工程 gap screen，
不是论文性能，也不是 proposed factor contribution。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_clean_replay_evaluator import (
    compare_to_references,
    evaluate_legsa_clean_replay,
    load_dual_official_reference,
    load_external_clean_summary,
)
from legsa_gins.evaluation.legsa_v23_clean_replay_runner import (
    build_clean_replay_config,
    check_runtime_outputs,
    run_legsa_v23_core,
)
from legsa_gins.evaluation.legsa_v23_gap_screen import screen_gap
from legsa_gins.evaluation.legsa_v23_parity_decision import EXTERNAL_CLEAN_REFERENCE, make_decision, metric_deltas


METRICS = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def _empty_summary(reason: str) -> dict[str, Any]:
    return {
        "count": 0,
        "evidence_status": reason,
        "horizontal_rmse_m": None,
        "up_rmse_m": None,
        "yaw_rmse_deg": None,
        "roll_rmse_deg": None,
        "pitch_rmse_deg": None,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def load_d2_baseline_and_variants(d2_root: str | Path) -> dict[str, Any]:
    """中文说明：读取 D2 baseline/variant 结果作对照；不把 variant 当正式结果。"""

    matrix_path = Path(d2_root) / "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json"
    if not matrix_path.exists():
        return {"evidence_status": "d2_matrix_missing", "baseline_current": {}, "best_diagnostic_variant": {}}
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    variants = matrix.get("variant_summaries", {})
    best = matrix.get("best_candidate_variant")
    return {
        "evidence_status": "d2_matrix_loaded",
        "baseline_current": variants.get("baseline_current", {}).get("summary", {}),
        "best_diagnostic_variant_name": best,
        "best_diagnostic_variant": variants.get(best, {}).get("summary", {}) if best else {},
        "candidate_fix_detected": matrix.get("candidate_fix_detected"),
        "multi_issue_or_coupled_issue": matrix.get("multi_issue_or_coupled_issue"),
    }


def _delta(current: dict[str, Any], reference: dict[str, Any]) -> dict[str, float | None]:
    return metric_deltas(current, reference)


def _improvement_from_baseline(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, float | None] = {}
    ratios: dict[str, float | None] = {}
    improved_over_50 = []
    for key in METRICS:
        cur = _num(current.get(key))
        base = _num(baseline.get(key))
        deltas[key] = None if cur is None or base is None else cur - base
        ratios[key] = None if cur is None or base is None or base == 0 else cur / base
        if ratios[key] is not None and ratios[key] <= 0.5:
            improved_over_50.append(key)
    return {"delta_vs_baseline_current": deltas, "ratio_vs_baseline_current": ratios, "improved_over_50_percent": improved_over_50}


def _status(summary: dict[str, Any], baseline: dict[str, Any], run_report: dict[str, Any]) -> str:
    stderr = str(run_report.get("stderr_tail", ""))
    if run_report.get("run_status") != "completed":
        return "invalid_covariance" if "covariance" in stderr.lower() else "runtime_failed"
    decision = make_decision(summary, EXTERNAL_CLEAN_REFERENCE)
    if decision.get("parity_classification") == "parity_passed":
        return "passed"
    improvement = _improvement_from_baseline(summary, baseline)
    materially_improved = {"horizontal_rmse_m", "up_rmse_m"}.issubset(set(improvement["improved_over_50_percent"]))
    if materially_improved:
        return "partial_improvement"
    return "no_improvement"


def run_guarded_fix_clean_replay(
    clean_root: str | Path,
    dual_root: str | Path,
    d2_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    allow_run: bool,
) -> dict[str, Any]:
    """中文说明：运行默认 solver clean replay，并与 N4H4D/D2/external clean 对比。"""

    out = Path(output_dir)
    run_dir = out / "default_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    config_report = build_clean_replay_config(clean_root, run_dir, run_dir / "config")
    if config_report.get("config_status") != "config_written":
        summary = _empty_summary("clean_input_missing")
        run_report = {"run_status": "clean_input_missing", "returncode": None}
        manifest: dict[str, Any] = {}
        dual_reference = {"dual_reference_status": "not_loaded"}
        external_clean = dict(EXTERNAL_CLEAN_REFERENCE)
    else:
        run_report = run_legsa_v23_core(exe, config_report["config_path"], run_dir, allow_run)
        runtime_outputs = check_runtime_outputs(run_dir)
        manifest = runtime_outputs.get("manifest", {})
        dual_reference = load_dual_official_reference(dual_root)
        external_clean = load_external_clean_summary(clean_root)
        if (
            run_report.get("run_status") == "completed"
            and runtime_outputs.get("runtime_output_status") == "outputs_ready"
            and dual_reference.get("dual_reference_status") == "reference_loaded"
        ):
            evaluation = evaluate_legsa_clean_replay(run_dir / "EVAL_NAV.csv", dual_reference["reference_rows"], run_dir)
            summary = evaluation["summary"]
        else:
            summary = _empty_summary("runtime_or_reference_missing")

    d2 = load_d2_baseline_and_variants(d2_root)
    baseline = d2.get("baseline_current", {})
    decision = make_decision(summary, external_clean)
    gap = screen_gap(summary, manifest, {"clean_input_status": config_report.get("clean_input_status"), "dual_reference_status": dual_reference.get("dual_reference_status")}, decision)
    comparison = {
        "phase": "N4H4D3",
        "delta_vs_N4H4D_baseline_current": _delta(summary, baseline),
        "delta_vs_external_clean_replay": _delta(summary, external_clean),
        "improvement_from_baseline_current": _improvement_from_baseline(summary, baseline),
        "d2_best_diagnostic_variant_name": d2.get("best_diagnostic_variant_name"),
        "delta_vs_d2_best_diagnostic_variant": _delta(summary, d2.get("best_diagnostic_variant", {})),
        "still_failed_categories": gap.get("gap_classification", []),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    guarded_status = _status(summary, baseline, run_report)
    summary_out = {
        "phase": "N4H4D3",
        **summary,
        "guarded_fix_parity_status": guarded_status,
        "update_counts": {
            "propagation_count": manifest.get("propagation_count", 0),
            "measurement_update_count": manifest.get("measurement_update_count", 0),
            "position_update_count": manifest.get("position_update_count", 0),
            "velocity_update_count": manifest.get("velocity_update_count", 0),
            "yaw_update_count": manifest.get("yaw_update_count", 0),
        },
        "yaw_mode_counts": {
            "NORMAL": manifest.get("yaw_normal_count", 0),
            "DOWNWEIGHT": manifest.get("yaw_downweight_count", 0),
            "REJECT": manifest.get("yaw_reject_count", 0),
        },
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "not_for_performance_claim": True,
    }
    report = {
        "phase": "N4H4D3",
        "config_report": config_report,
        "run_report": run_report,
        "manifest": manifest,
        "summary": summary_out,
        "gap_screen": gap,
        "comparison_report": comparison,
        "decision": decision,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "GUARDED_FIX_CLEAN_REPLAY_SUMMARY.json", summary_out)
    _write_json(out / "GUARDED_FIX_CLEAN_REPLAY_GAP_SCREEN.json", gap)
    _write_json(out / "GUARDED_FIX_COMPARISON_REPORT.json", comparison)
    return report
