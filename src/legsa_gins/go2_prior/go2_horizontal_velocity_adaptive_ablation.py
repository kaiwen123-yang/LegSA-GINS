"""N7C3 bounded adaptive Go2 horizontal velocity ablation matrix.

中文说明：本模块只组织 N7C3 有界自适应策略的消融矩阵，不改变滤波器数学。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_horizontal_velocity_ablation import _row
from legsa_gins.source_aware.source_aware_policy_diagnostics import metric_delta


REQUIRED_N7C3_VARIANT_IDS = [
    "baseline_no_go2_horizontal",
    "fixed_std_2mps_main",
    "bounded_adaptive_std_soft_gating",
    "high_confidence_only",
    "probability_weighted_original_for_comparison",
    "receiver_velocity_stress_fixed",
    "receiver_velocity_stress_bounded_adaptive",
    "raw_doppler_stress_fixed",
    "raw_doppler_stress_bounded_adaptive",
]


def _bounded_row(**kwargs: Any) -> dict[str, Any]:
    row = _row(**kwargs)
    row["source_aware_go2_horizontal_velocity_cap"] = 5.0
    row["go2_horizontal_velocity_adaptive_std_enabled"] = True
    row["go2_horizontal_velocity_bounded_std_policy"] = "n7c3_bounded_adaptive_std_soft_gating"
    row["paper_performance_claim"] = False
    row["no_outperform_final_v23_claim"] = True
    row["trace_solver_input"] = False
    row["final_v23_output_solver_input"] = False
    return row


def build_n7c3_bounded_adaptive_ablation_matrix(
    *,
    output_dir: str | Path,
    raw_doppler_factor_path: str | Path,
    prior_paths: dict[str, Path],
) -> dict[str, Any]:
    out = Path(output_dir)
    matrix = [
        _bounded_row(
            variant_id="baseline_no_go2_horizontal",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=None,
            enable_go2=False,
        ),
        _bounded_row(
            variant_id="fixed_std_2mps_main",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_2mps"],
            enable_go2=True,
        ),
        _bounded_row(
            variant_id="bounded_adaptive_std_soft_gating",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["bounded_adaptive"],
            enable_go2=True,
        ),
        _bounded_row(
            variant_id="high_confidence_only",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["high_confidence_only"],
            enable_go2=True,
            diagnostic_only=True,
        ),
        _bounded_row(
            variant_id="probability_weighted_original_for_comparison",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["probability_weighted_original"],
            enable_go2=True,
            diagnostic_only=True,
        ),
        _bounded_row(
            variant_id="receiver_velocity_stress_fixed",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_2mps"],
            enable_go2=True,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _bounded_row(
            variant_id="receiver_velocity_stress_bounded_adaptive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["bounded_adaptive"],
            enable_go2=True,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _bounded_row(
            variant_id="raw_doppler_stress_fixed",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_2mps"],
            enable_go2=True,
            raw_doppler_R_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _bounded_row(
            variant_id="raw_doppler_stress_bounded_adaptive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["bounded_adaptive"],
            enable_go2=True,
            raw_doppler_R_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
    ]
    found = {row["variant_id"] for row in matrix}
    return {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "matrix": matrix,
        "required_variant_ids": REQUIRED_N7C3_VARIANT_IDS,
        "required_variants_present": all(item in found for item in REQUIRED_N7C3_VARIANT_IDS),
        "main_candidate_variant": "bounded_adaptive_std_soft_gating",
        "fixed_reference_variant": "fixed_std_2mps_main",
        "stress_variants_diagnostic_only": True,
        "go2_velocity_truth_claim": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def compare_n7c3_bounded_adaptive_variants(variant_summaries: list[dict[str, Any]], std_report: dict[str, Any]) -> dict[str, Any]:
    by_id = {row.get("variant_id"): row for row in variant_summaries}
    comparisons = {
        "fixed_std_2mps_main_minus_baseline": {
            "delta": metric_delta(by_id.get("fixed_std_2mps_main"), by_id.get("baseline_no_go2_horizontal")),
            "paper_performance_claim": False,
        },
        "bounded_adaptive_minus_fixed_clean": {
            "delta": metric_delta(by_id.get("bounded_adaptive_std_soft_gating"), by_id.get("fixed_std_2mps_main")),
            "paper_performance_claim": False,
        },
        "high_confidence_only_minus_fixed_clean": {
            "delta": metric_delta(by_id.get("high_confidence_only"), by_id.get("fixed_std_2mps_main")),
            "paper_performance_claim": False,
        },
        "original_probability_weighted_minus_fixed_clean": {
            "delta": metric_delta(by_id.get("probability_weighted_original_for_comparison"), by_id.get("fixed_std_2mps_main")),
            "paper_performance_claim": False,
        },
        "receiver_velocity_stress_bounded_adaptive_minus_fixed": {
            "delta": metric_delta(by_id.get("receiver_velocity_stress_bounded_adaptive"), by_id.get("receiver_velocity_stress_fixed")),
            "paper_performance_claim": False,
        },
        "raw_doppler_stress_bounded_adaptive_minus_fixed": {
            "delta": metric_delta(by_id.get("raw_doppler_stress_bounded_adaptive"), by_id.get("raw_doppler_stress_fixed")),
            "paper_performance_claim": False,
        },
    }
    return {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "fixed_reference": (by_id.get("fixed_std_2mps_main") or {}).get("summary", {}),
        "bounded_adaptive": (by_id.get("bounded_adaptive_std_soft_gating") or {}).get("summary", {}),
        "bounded_adaptive_manifest": (by_id.get("bounded_adaptive_std_soft_gating") or {}).get("manifest", {}),
        "std_distribution": {
            "std_vn_p50": std_report.get("std_vn_p50"),
            "std_vn_p95": std_report.get("std_vn_p95"),
            "std_vn_max": std_report.get("std_vn_max"),
            "std_ve_p50": std_report.get("std_ve_p50"),
            "std_ve_p95": std_report.get("std_ve_p95"),
            "std_ve_max": std_report.get("std_ve_max"),
            "max_std_le_5": std_report.get("max_std_le_5"),
        },
        "comparisons": comparisons,
        "metric_namespace": {
            "variant_delta": True,
            "paper_performance_claim": False,
            "no_outperform_final_v23_claim": True,
        },
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }


def write_n7c3_ablation_artifacts(
    *,
    output_dir: str | Path,
    matrix: dict[str, Any],
    variant_summaries: list[dict[str, Any]],
    comparison_report: dict[str, Any],
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "N7C3_BOUNDED_ADAPTIVE_STD_ABLATION_MATRIX.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "N7C3_BOUNDED_ADAPTIVE_STD_VARIANT_SUMMARIES.json").write_text(
        json.dumps({"variants": variant_summaries, "paper_performance_claim": False}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "N7C3_BOUNDED_ADAPTIVE_STD_COMPARISON_REPORT.json").write_text(
        json.dumps(comparison_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
