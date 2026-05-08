"""Evaluate LegSA-v23 clean replay against dual official reference.

中文说明：本模块只做 fresh evaluation，reference/trace 都是 evaluation-only；
不回写 solver，不做 output-only correction，不删 epoch。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_summary
from legsa_gins.evaluation.official_case_review_reproduction import load_eval_nav_csv
from legsa_gins.evaluation.official_reference_reconstruction import reconstruct_from_paths
from legsa_gins.evaluation.trajectory_metrics import align_by_timestamp, compute_errors, summary_metrics, write_error_series
from legsa_gins.evaluation.legsa_v23_parity_decision import EXTERNAL_CLEAN_REFERENCE, gate_status, metric_deltas


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_external_clean_summary(clean_root: str | Path) -> dict[str, Any]:
    """中文说明：读取 external KF-GINS clean replay summary；缺失则使用冻结参考数值。"""

    summary_path = Path(clean_root) / "CLEAN_REPLAY_SUMMARY.json"
    if not summary_path.exists():
        fallback = dict(EXTERNAL_CLEAN_REFERENCE)
        fallback["evidence_status"] = "external_clean_summary_missing_using_reference_constants"
        return fallback
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    return {**EXTERNAL_CLEAN_REFERENCE, **{key: data.get(key) for key in EXTERNAL_CLEAN_REFERENCE if key in data}, "raw_summary": data}


def load_dual_official_reference(dual_root: str | Path) -> dict[str, Any]:
    """中文说明：从 dual official NAV + error_series 重建 evaluation-only reference。"""

    root = Path(dual_root)
    nav_path = root / "KF_GINS_Navresult.nav"
    error_path = root / "error_series.csv"
    summary_path = root / "summary.json"
    missing = [name for name, path in {
        "KF_GINS_Navresult.nav": nav_path,
        "error_series.csv": error_path,
        "summary.json": summary_path,
    }.items() if not path.exists()]
    if missing:
        return {
            "dual_reference_status": "reference_missing",
            "evidence_missing": missing,
            "trace_solver_input": False,
            "final_v23_output_substitution": False,
        }
    reconstructed = reconstruct_from_paths(nav_path, error_path, summary_path)
    selected_name = reconstructed.get("selected_reference_sign")
    references = reconstructed.get("reference_candidates", {})
    selected_rows = references.get(selected_name, []) if isinstance(references, dict) else []
    return {
        "dual_reference_status": "reference_loaded",
        "reference_rows": selected_rows,
        "selected_reference_sign": selected_name,
        "selected_reference_profile": reconstructed.get("selected_reference_profile"),
        "reference_reconstruction_status": reconstructed.get("evidence_status"),
        "official_summary": load_official_summary(summary_path),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
    }


def _add_gate_fields(summary: dict[str, Any]) -> dict[str, Any]:
    summary.update(gate_status(summary))
    summary.update(
        {
            "aligned_count": summary.get("count"),
            "reference_profile": "selected_dual_official_reference_direct_identity",
            "trace_solver_input": False,
            "trace_evaluation_only": True,
            "final_v23_output_substitution": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
    )
    return summary


def evaluate_legsa_clean_replay(
    eval_nav_path: str | Path,
    official_reference_rows: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """中文说明：评估 LegSA_V23 EVAL_NAV；输出 summary 和 error_series 到 runtime-only 目录。"""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    est_rows = load_eval_nav_csv(eval_nav_path)
    aligned = align_by_timestamp(est_rows, official_reference_rows, max_dt=0.05)
    errors = compute_errors(aligned)
    summary = _add_gate_fields(summary_metrics(errors))
    write_error_series(errors, out / "LEGSA_V23_CLEAN_REPLAY_ERROR_SERIES.csv")
    _write_json(out / "LEGSA_V23_CLEAN_REPLAY_SUMMARY.json", summary)
    return {
        "phase": "N4H4D",
        "summary": summary,
        "eval_nav_rows": len(est_rows),
        "official_reference_rows": len(official_reference_rows),
        "error_series_path": "LEGSA_V23_CLEAN_REPLAY_ERROR_SERIES.csv",
        "summary_path": "LEGSA_V23_CLEAN_REPLAY_SUMMARY.json",
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def compare_to_references(
    legsa_summary: dict[str, Any],
    external_clean_summary: dict[str, Any],
    dual_official_summary: dict[str, Any],
) -> dict[str, Any]:
    """中文说明：对比 external clean replay 和 dual official summary，不做性能 claim。"""

    return {
        "phase": "N4H4D",
        "external_clean_deltas": metric_deltas(legsa_summary, external_clean_summary),
        "dual_official_deltas": metric_deltas(legsa_summary, dual_official_summary),
        "external_clean_summary": {key: external_clean_summary.get(key) for key in EXTERNAL_CLEAN_REFERENCE},
        "dual_official_summary": {key: dual_official_summary.get(key) for key in EXTERNAL_CLEAN_REFERENCE},
        "engineering_baseline_parity_only": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def write_report(path: str | Path, report: dict[str, Any]) -> None:
    """中文说明：写 runtime-only JSON 报告；不要提交该输出目录。"""

    _write_json(Path(path), report)
