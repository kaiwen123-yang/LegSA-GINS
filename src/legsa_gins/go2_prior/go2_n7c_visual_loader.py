"""Runtime-only input loader for N7C1 Go2 horizontal velocity visual validation.

中文说明：本模块只读取 N7C 已有 runtime 输出、Go2 horizontal prior CSV 和
evaluation-only dual reference；final_v23/trace 不进入 solver，也不触发调参。
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


N7C_REQUIRED_REPORTS = [
    "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_ABLATION_MATRIX.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json",
]

N7C_OPTIONAL_REPORTS = ["N7C_FIGURE_MANIFEST.json"]

CLEAN_VARIANTS = [
    "baseline_no_go2_horizontal_velocity",
    "go2_horizontal_velocity_weak_prior_main",
    "go2_horizontal_velocity_probability_weighted",
    "go2_horizontal_velocity_contact_weighted",
    "go2_horizontal_velocity_high_confidence_only",
]

STRESS_PAIRS = {
    "receiver_velocity_stress": (
        "receiver_velocity_stress_no_go2",
        "receiver_velocity_stress_plus_go2_horizontal",
    ),
    "raw_doppler_stress": (
        "raw_doppler_stress_no_go2",
        "raw_doppler_stress_plus_go2_horizontal",
    ),
}


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _variant_path(n7c_root: Path, variant_id: str, file_name: str) -> Path:
    return n7c_root / "variants" / variant_id / file_name


def _load_error_rows(eval_nav: Path, reference_rows: list[dict[str, float]]) -> list[dict[str, float]]:
    if not eval_nav.exists() or not reference_rows:
        return []
    estimate = load_port_eval_nav(eval_nav)
    return compute_error_rows(align_by_time(estimate, reference_rows, tolerance=0.005))


def _find_raw_doppler_csv(n5b_root: str | Path | None) -> Path | None:
    if not n5b_root:
        return None
    root = Path(n5b_root)
    for name in ["RAW_DOPPLER_VELOCITY_FACTORS.csv", "RAW_DOPPLER_FACTORS.csv"]:
        candidate = root / name
        if candidate.exists():
            return candidate
    for candidate in root.rglob("*DOPPLER*FACTORS*.csv"):
        return candidate
    return None


def _source_trace_rows(n7c_root: Path, variant_id: str) -> list[dict[str, Any]]:
    return read_csv_rows(_variant_path(n7c_root, variant_id, "SOURCE_AWARE_WEIGHT_TRACE.csv"))


def _main_variant_summary(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summaries = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json", {}).get("variants", [])
    for row in summaries:
        if row.get("variant_id") == "go2_horizontal_velocity_weak_prior_main":
            return row
    return {}


def load_n7c1_visual_inputs(
    *,
    n7c_root: str | Path,
    n7b5_root: str | Path | None = None,
    n5b_root: str | Path | None = None,
    n6b_root: str | Path | None = None,
    dual_root: str | Path | None = None,
    rerun_missing_timeseries: bool = True,
) -> dict[str, Any]:
    """Load N7C visual inputs from runtime-only directories.

    中文说明：`rerun_missing_timeseries` 只作为 manifest 记录；N7C1 当前优先使用
    N7C 已生成的 variants/time-series，缺失时标记 evidence_missing，不改 solver。
    """

    n7c = Path(n7c_root)
    dual = Path(dual_root) if dual_root else None
    reports = {name: read_json(n7c / name) for name in [*N7C_REQUIRED_REPORTS, *N7C_OPTIONAL_REPORTS]}
    reference_nav = dual / "KF_GINS_Navresult.nav" if dual else None
    reference_rows = parse_kfgins_nav(reference_nav) if reference_nav and reference_nav.exists() else []
    clean_errors = {
        variant_id: _load_error_rows(_variant_path(n7c, variant_id, "EVAL_NAV.csv"), reference_rows)
        for variant_id in CLEAN_VARIANTS
    }
    eval_nav_rows = {
        variant_id: read_csv_rows(_variant_path(n7c, variant_id, "EVAL_NAV.csv"))
        for variant_id in CLEAN_VARIANTS
    }
    stress_errors: dict[str, dict[str, Any]] = {}
    for label, (no_go2, plus_go2) in STRESS_PAIRS.items():
        stress_errors[label] = {
            "no_go2": _load_error_rows(_variant_path(n7c, no_go2, "EVAL_NAV.csv"), reference_rows),
            "plus_go2": _load_error_rows(_variant_path(n7c, plus_go2, "EVAL_NAV.csv"), reference_rows),
            "no_go2_variant_id": no_go2,
            "plus_go2_variant_id": plus_go2,
        }
    prior_rows = read_csv_rows(n7c / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv")
    raw_doppler_path = _find_raw_doppler_csv(n5b_root)
    raw_doppler_rows = read_csv_rows(raw_doppler_path) if raw_doppler_path else []
    main_trace_rows = _source_trace_rows(n7c, "go2_horizontal_velocity_weak_prior_main")
    go2_trace_rows = [row for row in main_trace_rows if row.get("source_id") == "go2_horizontal_velocity"]
    main_summary = _main_variant_summary(reports)
    main_manifest = main_summary.get("manifest", {}) if isinstance(main_summary, dict) else {}
    decision = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json", {})
    prior_build = reports.get("GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json", {})
    std_vd_sample = [str(row.get("std_vd")) for row in prior_rows[:50] if row.get("std_vd")]
    vertical_disabled = bool(
        prior_build.get("vertical_velocity_disabled")
        or decision.get("go2_vertical_velocity_prior_enabled") is False
        or main_manifest.get("go2_horizontal_velocity_prior_vertical_disabled")
        or (bool(std_vd_sample) and all(value in {"999.0", "999"} for value in std_vd_sample))
    )
    baseline_found = bool(clean_errors.get("baseline_no_go2_horizontal_velocity"))
    main_found = bool(clean_errors.get("go2_horizontal_velocity_weak_prior_main"))
    stress_found = all(bool(pair["no_go2"]) and bool(pair["plus_go2"]) for pair in stress_errors.values())
    manifest = {
        "stage": "N7C1_go2_horizontal_velocity_visual_validation",
        "n7c_reports_found": {name: bool(reports[name]) for name in N7C_REQUIRED_REPORTS},
        "prior_build_report_found": bool(prior_build),
        "baseline_timeseries_found": baseline_found,
        "main_prior_timeseries_found": main_found,
        "stress_timeseries_found": stress_found,
        "go2_prior_csv_found": bool(prior_rows),
        "source_trace_found": bool(main_trace_rows),
        "go2_horizontal_source_trace_found": bool(go2_trace_rows),
        "vertical_disabled_confirmed": vertical_disabled,
        "rerun_missing_timeseries_requested": bool(rerun_missing_timeseries),
        "rerun_missing_timeseries_status": "not_needed" if baseline_found and main_found and stress_found else "evidence_missing_not_rerun_in_visual_only_loader",
        "input_role_aliases": {
            "n7c_root": "N7C_RUNTIME_REPORT_ROOT",
            "n7b5_root": "N7B5_RUNTIME_REPORT_ROOT" if n7b5_root else "not_provided",
            "n5b_root": "N5B_RUNTIME_REPORT_ROOT" if n5b_root else "not_provided",
            "n6b_root": "N6B_RUNTIME_REPORT_ROOT" if n6b_root else "not_provided",
            "dual_root": "DUAL_FINAL_V23_ARTIFACT_ROOT" if dual_root else "not_provided",
        },
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
    }
    return {
        "manifest": manifest,
        "reports": reports,
        "clean_errors": clean_errors,
        "stress_errors": stress_errors,
        "eval_nav_rows": eval_nav_rows,
        "prior_rows": prior_rows,
        "raw_doppler_rows": raw_doppler_rows,
        "main_trace_rows": main_trace_rows,
        "go2_trace_rows": go2_trace_rows,
        "reference_row_count": len(reference_rows),
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def write_n7c1_visual_input_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
