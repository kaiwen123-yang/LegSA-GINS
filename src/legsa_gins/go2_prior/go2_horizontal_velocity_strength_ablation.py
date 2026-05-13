"""N7C4 Go2 horizontal velocity strength ablation matrix and comparison.

中文说明：本模块只定义固定/自适应 std 强度扫描矩阵和诊断 delta，
不使用 trace/final_v23 输出调参，也不声明论文性能提升。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_horizontal_velocity_ablation import _row
from legsa_gins.source_aware.source_aware_policy_diagnostics import metric_delta


REQUIRED_N7C4_VARIANT_IDS = [
    "no_go2_horizontal",
    "fixed_2p0",
    "fixed_1p5",
    "fixed_1p0",
    "fixed_0p75_aggressive",
    "recalibrated_adaptive",
    "recalibrated_adaptive_aggressive",
    "receiver_velocity_stress_fixed_2p0",
    "receiver_velocity_stress_fixed_1p0",
    "receiver_velocity_stress_adaptive",
    "raw_doppler_stress_fixed_2p0",
    "raw_doppler_stress_fixed_1p0",
    "raw_doppler_stress_adaptive",
]


def _strength_row(*, strength_policy: str, **kwargs: Any) -> dict[str, Any]:
    row = _row(**kwargs)
    row["go2_horizontal_velocity_strength_policy"] = strength_policy
    row["go2_horizontal_velocity_adaptive_std_enabled"] = strength_policy.startswith("recalibrated_adaptive")
    row["go2_horizontal_velocity_bounded_std_policy"] = strength_policy if strength_policy.startswith("recalibrated") else ""
    row["source_aware_go2_horizontal_velocity_cap"] = 8.0
    row["paper_performance_claim"] = False
    row["no_outperform_final_v23_claim"] = True
    row["trace_solver_input"] = False
    row["final_v23_output_solver_input"] = False
    return row


def build_n7c4_strength_ablation_matrix(
    *,
    output_dir: str | Path,
    raw_doppler_factor_path: str | Path,
    prior_paths: dict[str, Path],
) -> dict[str, Any]:
    out = Path(output_dir)
    matrix = [
        _strength_row(
            variant_id="no_go2_horizontal",
            strength_policy="no_go2_horizontal",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=None,
            enable_go2=False,
        ),
        _strength_row(
            variant_id="fixed_2p0",
            strength_policy="fixed_std_2p0",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_2p0"],
            enable_go2=True,
        ),
        _strength_row(
            variant_id="fixed_1p5",
            strength_policy="fixed_std_1p5",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_1p5"],
            enable_go2=True,
        ),
        _strength_row(
            variant_id="fixed_1p0",
            strength_policy="fixed_std_1p0",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_1p0"],
            enable_go2=True,
        ),
        _strength_row(
            variant_id="fixed_0p75_aggressive",
            strength_policy="fixed_std_0p75_aggressive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_0p75_aggressive"],
            enable_go2=True,
            diagnostic_only=True,
        ),
        _strength_row(
            variant_id="recalibrated_adaptive",
            strength_policy="recalibrated_adaptive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["recalibrated_adaptive"],
            enable_go2=True,
        ),
        _strength_row(
            variant_id="recalibrated_adaptive_aggressive",
            strength_policy="recalibrated_adaptive_aggressive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["recalibrated_adaptive_aggressive"],
            enable_go2=True,
            diagnostic_only=True,
        ),
        _strength_row(
            variant_id="receiver_velocity_stress_fixed_2p0",
            strength_policy="receiver_velocity_stress_fixed_std_2p0",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_2p0"],
            enable_go2=True,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _strength_row(
            variant_id="receiver_velocity_stress_fixed_1p0",
            strength_policy="receiver_velocity_stress_fixed_std_1p0",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_1p0"],
            enable_go2=True,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _strength_row(
            variant_id="receiver_velocity_stress_adaptive",
            strength_policy="receiver_velocity_stress_recalibrated_adaptive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["recalibrated_adaptive"],
            enable_go2=True,
            receiver_velocity_stress_mode="std_scale",
            receiver_velocity_std_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _strength_row(
            variant_id="raw_doppler_stress_fixed_2p0",
            strength_policy="raw_doppler_stress_fixed_std_2p0",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_2p0"],
            enable_go2=True,
            raw_doppler_R_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _strength_row(
            variant_id="raw_doppler_stress_fixed_1p0",
            strength_policy="raw_doppler_stress_fixed_std_1p0",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["fixed_std_1p0"],
            enable_go2=True,
            raw_doppler_R_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
        _strength_row(
            variant_id="raw_doppler_stress_adaptive",
            strength_policy="raw_doppler_stress_recalibrated_adaptive",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["recalibrated_adaptive"],
            enable_go2=True,
            raw_doppler_R_scale=5.0,
            diagnostic_only=True,
            diagnostic_stress_only=True,
        ),
    ]
    found = {row["variant_id"] for row in matrix}
    return {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "matrix": matrix,
        "required_variant_ids": REQUIRED_N7C4_VARIANT_IDS,
        "required_variants_present": all(variant_id in found for variant_id in REQUIRED_N7C4_VARIANT_IDS),
        "fixed_reference_variant": "fixed_2p0",
        "main_candidate_variants": ["fixed_1p5", "fixed_1p0", "recalibrated_adaptive"],
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


def compare_n7c4_strength_variants(variant_summaries: list[dict[str, Any]], prior_report: dict[str, Any], nis_report: dict[str, Any]) -> dict[str, Any]:
    by_id = {row.get("variant_id"): row for row in variant_summaries}
    comparisons = {
        "fixed_2p0_minus_no_go2_clean": {"delta": metric_delta(by_id.get("fixed_2p0"), by_id.get("no_go2_horizontal")), "paper_performance_claim": False},
        "fixed_1p5_minus_fixed_2p0_clean": {"delta": metric_delta(by_id.get("fixed_1p5"), by_id.get("fixed_2p0")), "paper_performance_claim": False},
        "fixed_1p0_minus_fixed_2p0_clean": {"delta": metric_delta(by_id.get("fixed_1p0"), by_id.get("fixed_2p0")), "paper_performance_claim": False},
        "fixed_0p75_minus_fixed_2p0_clean": {"delta": metric_delta(by_id.get("fixed_0p75_aggressive"), by_id.get("fixed_2p0")), "paper_performance_claim": False},
        "recalibrated_adaptive_minus_fixed_2p0_clean": {"delta": metric_delta(by_id.get("recalibrated_adaptive"), by_id.get("fixed_2p0")), "paper_performance_claim": False},
        "recalibrated_adaptive_aggressive_minus_fixed_2p0_clean": {"delta": metric_delta(by_id.get("recalibrated_adaptive_aggressive"), by_id.get("fixed_2p0")), "paper_performance_claim": False},
        "receiver_velocity_stress_fixed_1p0_minus_fixed_2p0": {"delta": metric_delta(by_id.get("receiver_velocity_stress_fixed_1p0"), by_id.get("receiver_velocity_stress_fixed_2p0")), "paper_performance_claim": False},
        "receiver_velocity_stress_adaptive_minus_fixed_2p0": {"delta": metric_delta(by_id.get("receiver_velocity_stress_adaptive"), by_id.get("receiver_velocity_stress_fixed_2p0")), "paper_performance_claim": False},
        "raw_doppler_stress_fixed_1p0_minus_fixed_2p0": {"delta": metric_delta(by_id.get("raw_doppler_stress_fixed_1p0"), by_id.get("raw_doppler_stress_fixed_2p0")), "paper_performance_claim": False},
        "raw_doppler_stress_adaptive_minus_fixed_2p0": {"delta": metric_delta(by_id.get("raw_doppler_stress_adaptive"), by_id.get("raw_doppler_stress_fixed_2p0")), "paper_performance_claim": False},
    }
    return {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "fixed_2p0_reference": (by_id.get("fixed_2p0") or {}).get("summary", {}),
        "candidate_summaries": {key: (by_id.get(key) or {}).get("summary", {}) for key in REQUIRED_N7C4_VARIANT_IDS},
        "candidate_manifests": {key: (by_id.get(key) or {}).get("manifest", {}) for key in REQUIRED_N7C4_VARIANT_IDS},
        "comparisons": comparisons,
        "prior_strength_report": prior_report,
        "nis_diagnostics": nis_report,
        "metric_namespace": {"variant_delta": True, "paper_performance_claim": False, "no_outperform_final_v23_claim": True},
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }


def write_n7c4_strength_ablation_artifacts(
    *,
    output_dir: str | Path,
    matrix: dict[str, Any],
    variant_summaries: list[dict[str, Any]],
    comparison_report: dict[str, Any],
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "N7C4_STRENGTH_ABLATION_MATRIX.json").write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "N7C4_STRENGTH_VARIANT_SUMMARIES.json").write_text(
        json.dumps({"variants": variant_summaries, "paper_performance_claim": False}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "N7C4_STRENGTH_COMPARISON_REPORT.json").write_text(
        json.dumps(comparison_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
