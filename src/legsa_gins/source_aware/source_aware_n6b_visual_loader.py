"""Runtime-only input loader for N6B1 source-aware visual validation.

中文说明：N6B1 只读取 N6B 已有 runtime 输出和 evaluation-only reference 来生成
图像审计数据；不把 final_v23/trace 输出送回 solver，也不重写滤波器结果。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import (
    align_by_time,
    compute_error_rows,
    load_port_eval_nav,
)
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav


N6B_REQUIRED_REPORTS = [
    "N6B_SOURCE_AWARE_VARIANT_SUMMARIES.json",
    "N6B_SOURCE_AWARE_WEIGHT_STATS.json",
    "N6B_SOURCE_AWARE_COMPARISON_REPORT.json",
    "N6B_SOURCE_AWARE_POLICY_DIAGNOSTICS.json",
    "N6B_SPIKE_RESPONSE_REPORT.json",
]

CLEAN_VARIANTS = [
    "baseline_plus_raw_no_sourceaware",
    "n6b_lsim_only",
    "n6b_oim_only",
    "n6b_lsim_oim",
    "n6a_lsim_oim_original_policy",
]

STRESS_PAIRS = {
    "stress_disabled": (
        "receiver_velocity_disabled_plus_raw_no_sourceaware",
        "receiver_velocity_disabled_plus_raw_n6b_lsim_oim",
    ),
    "stress_std_scale5": (
        "receiver_velocity_std_scale_5_plus_raw_no_sourceaware",
        "receiver_velocity_std_scale_5_plus_raw_n6b_lsim_oim",
    ),
    "stress_outage30": (
        "receiver_velocity_outage_30s_plus_raw_no_sourceaware",
        "receiver_velocity_outage_30s_plus_raw_n6b_lsim_oim",
    ),
    "stress_noise0p5": (
        "receiver_velocity_noise_0p5_plus_raw_no_sourceaware",
        "receiver_velocity_noise_0p5_plus_raw_n6b_lsim_oim",
    ),
}


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _variant_path(n6b_root: Path, variant_id: str, file_name: str) -> Path:
    return n6b_root / "variants" / variant_id / file_name


def _load_error_rows(eval_nav: Path, reference_rows: list[dict[str, float]]) -> list[dict[str, float]]:
    if not eval_nav.exists() or not reference_rows:
        return []
    estimate = load_port_eval_nav(eval_nav)
    return compute_error_rows(align_by_time(estimate, reference_rows, tolerance=0.005))


def load_n6b1_visual_inputs(
    *,
    n6b_root: str | Path,
    n5d1_root: str | Path | None,
    dual_root: str | Path,
    rerun_missing_timeseries: bool = True,
) -> dict[str, Any]:
    """Load N6B visual-validation inputs.

    中文说明：`rerun_missing_timeseries` 在 N6B1 中只是 manifest 记录；当前实现
    优先使用 N6B 已有 runtime variants，缺失时报告 evidence_missing，不调参。
    """

    del rerun_missing_timeseries
    n6b = Path(n6b_root)
    n5d1 = Path(n5d1_root) if n5d1_root else None
    dual = Path(dual_root)
    reports = {name: read_json(n6b / name) for name in N6B_REQUIRED_REPORTS}
    reference_nav = dual / "KF_GINS_Navresult.nav"
    reference_rows = parse_kfgins_nav(reference_nav) if reference_nav.exists() else []
    clean_errors = {
        variant_id: _load_error_rows(_variant_path(n6b, variant_id, "EVAL_NAV.csv"), reference_rows)
        for variant_id in CLEAN_VARIANTS
    }
    stress_errors: dict[str, dict[str, list[dict[str, float]]]] = {}
    for label, (no_sourceaware, n6b_variant) in STRESS_PAIRS.items():
        stress_errors[label] = {
            "no_sourceaware": _load_error_rows(_variant_path(n6b, no_sourceaware, "EVAL_NAV.csv"), reference_rows),
            "n6b": _load_error_rows(_variant_path(n6b, n6b_variant, "EVAL_NAV.csv"), reference_rows),
            "no_sourceaware_variant_id": no_sourceaware,
            "n6b_variant_id": n6b_variant,
        }
    n6b_trace = read_csv_rows(_variant_path(n6b, "n6b_lsim_oim", "SOURCE_AWARE_WEIGHT_TRACE.csv"))
    n6a_trace = read_csv_rows(_variant_path(n6b, "n6a_lsim_oim_original_policy", "SOURCE_AWARE_WEIGHT_TRACE.csv"))
    variant_dirs = {
        variant_id: str(n6b / "variants" / variant_id)
        for variant_id in CLEAN_VARIANTS
        if (n6b / "variants" / variant_id).exists()
    }
    for _, (no_sourceaware, n6b_variant) in STRESS_PAIRS.items():
        for variant_id in [no_sourceaware, n6b_variant]:
            if (n6b / "variants" / variant_id).exists():
                variant_dirs[variant_id] = str(n6b / "variants" / variant_id)
    manifest = {
        "stage": "N6B1_source_aware_visual_validation",
        "n6b_reports_found": {name: bool(reports[name]) for name in N6B_REQUIRED_REPORTS},
        "source_aware_trace_found": bool(n6b_trace),
        "clean_time_series_found": all(bool(clean_errors.get(key)) for key in ["baseline_plus_raw_no_sourceaware", "n6b_lsim_oim"]),
        "stress_time_series_found": all(bool(pair["no_sourceaware"]) and bool(pair["n6b"]) for pair in stress_errors.values()),
        "spike_report_found": bool(reports["N6B_SPIKE_RESPONSE_REPORT.json"]),
        "variant_output_dirs_found": variant_dirs,
        "n5d1_reports_found": {
            "N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json": bool(n5d1 and (n5d1 / "N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json").exists()),
            "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json": bool(n5d1 and (n5d1 / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json").exists()),
        },
        "reference_role": "DUAL_FINAL_V23_ARTIFACT_ROOT/KF_GINS_Navresult.nav",
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }
    return {
        "manifest": manifest,
        "reports": reports,
        "clean_errors": clean_errors,
        "stress_errors": stress_errors,
        "n6b_trace": n6b_trace,
        "n6a_trace": n6a_trace,
        "reference_row_count": len(reference_rows),
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def write_n6b1_visual_input_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
