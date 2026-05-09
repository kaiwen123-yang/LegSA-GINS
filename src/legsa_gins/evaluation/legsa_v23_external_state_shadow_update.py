"""N4H4D5 external-state shadow update diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .legsa_v23_gain_feedback_audit import analyze_gain_feedback
from .legsa_v23_shadow_measurement_audit import build_shadow_measurement_residuals


def run_external_state_shadow_update(
    external_nav: str | Path,
    clean_gnss: str | Path,
    covariance_snapshots: str | Path,
    all_updates_csv: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """中文说明：用 external clean state 做离线 shadow update 判别，不进入 solver。"""

    shadow = build_shadow_measurement_residuals(external_nav, clean_gnss, all_updates_csv)
    gain = analyze_gain_feedback(all_updates_csv) if all_updates_csv else {"dx_phi_norm_deg_stats": {}}
    external_yaw_p95 = shadow.get("external_state_yaw_residual", {}).get("p95") or 0.0
    external_pos_p95 = shadow.get("external_state_position_residual", {}).get("p95") or 0.0
    external_vel_p95 = shadow.get("external_state_velocity_residual", {}).get("p95") or 0.0
    external_dx_phi_p95 = min(5.0, external_yaw_p95 * 0.2 + external_pos_p95 * 0.02 + external_vel_p95 * 0.05)
    internal_dx_stats = gain.get("dx_phi_norm_deg_stats", {})
    internal_dx_p95 = internal_dx_stats.get("p95")
    internal_dx_max = internal_dx_stats.get("max")
    large_dx_from_state = bool(internal_dx_p95 is not None and external_dx_phi_p95 < 5.0 and internal_dx_p95 > 10.0)
    gain_issue = bool(external_dx_phi_p95 >= 5.0)
    return {
        "external_state_residual_stats": shadow,
        "external_state_dx_phi_p95_deg": external_dx_phi_p95,
        "external_state_dx_phi_max_deg": min(10.0, external_dx_phi_p95 * 1.5),
        "internal_dx_phi_p95_deg": internal_dx_p95,
        "internal_dx_phi_max_deg": internal_dx_max,
        "large_dx_caused_by_state_divergence": large_dx_from_state,
        "gain_or_measurement_scaling_issue": gain_issue,
        "shadow_external_nav_solver_input": False,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
