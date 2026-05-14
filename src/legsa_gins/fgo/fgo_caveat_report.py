"""N8E caveat report.

中文说明：集中记录 N8E caveat，避免把边界说明改写成性能结论。
"""

from __future__ import annotations

from typing import Any


REQUIRED_CAVEATS = [
    "raw_doppler_fgo_low_marginal_value",
    "go2_fields_not_truth",
    "contact_probability_not_direct_factor",
    "candidate_factors_diagnostic_only",
    "fgo_no_feedback_only",
    "fgo_output_not_ekf_nav_replacement",
    "no_trace_finalv23_tuning",
    "no_paper_performance_claim",
    "smoothness_not_deleted_as_final_shortcut",
    "by2_style_and_diagnostic_stress_evidence_scope",
]


def build_caveat_report(
    *,
    matrix_report: dict[str, Any],
    module_summary: dict[str, Any],
) -> dict[str, Any]:
    caveats = [
        {
            "id": "raw_doppler_fgo_low_marginal_value",
            "summary": "Raw Doppler FGO factor is active, but current no-feedback FGO marginal value is low.",
            "is_failure": False,
            "blocks_ekf_raw_doppler": False,
        },
        {
            "id": "go2_fields_not_truth",
            "summary": "Go2 fields are proprioceptive observations, not truth.",
            "is_failure": False,
        },
        {
            "id": "contact_probability_not_direct_factor",
            "summary": "Contact probability is weighting/candidate evidence, not a direct formal factor.",
            "is_failure": False,
        },
        {
            "id": "candidate_factors_diagnostic_only",
            "summary": "Candidate factors remain diagnostic-only unless explicitly promoted later.",
            "is_failure": False,
        },
        {
            "id": "fgo_no_feedback_only",
            "summary": "FGO is no-feedback only.",
            "is_failure": False,
        },
        {
            "id": "fgo_output_not_ekf_nav_replacement",
            "summary": "FGO output is not used to replace EKF NAV.",
            "is_failure": False,
        },
        {
            "id": "no_trace_finalv23_tuning",
            "summary": "Trace/final_v23 outputs are not used for solver input or weight tuning.",
            "is_failure": False,
        },
        {
            "id": "no_paper_performance_claim",
            "summary": "N8E is an engineering ablation and does not make a paper performance claim.",
            "is_failure": False,
        },
        {
            "id": "smoothness_not_deleted_as_final_shortcut",
            "summary": "Smoothness is not deleted as a final shortcut.",
            "is_failure": False,
        },
        {
            "id": "by2_style_and_diagnostic_stress_evidence_scope",
            "summary": "Current evidence is mainly BY2-style data plus diagnostic stress variants.",
            "is_failure": False,
        },
    ]
    present = {row["id"] for row in caveats}
    return {
        "stage": "N8E_formal_engineering_ablation_with_caveat",
        "caveats": caveats,
        "required_caveats": REQUIRED_CAVEATS,
        "missing_required_caveats": [name for name in REQUIRED_CAVEATS if name not in present],
        "all_required_caveats_present": all(name in present for name in REQUIRED_CAVEATS),
        "matrix_complete": bool(matrix_report.get("matrix_complete")),
        "module_count": module_summary.get("module_count", 0),
        "raw_doppler_low_marginal_value_is_not_failure": True,
        "candidate_factors_need_deeper_review": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }
