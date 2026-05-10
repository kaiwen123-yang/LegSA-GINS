"""N5A readiness decision logic.

中文说明：provider 缺失时必须阻塞 raw Doppler solver activation。
"""

from __future__ import annotations

from .raw_doppler_types import ReadinessDecision


def decide_readiness(
    scan_report: dict,
    ephemeris_report: dict,
    rtklib_report: dict,
    provider_report: dict,
) -> ReadinessDecision:
    blockers: list[str] = []
    if not scan_report.get("rawx_found", False):
        blockers.append("rawx_missing")
    if not ephemeris_report.get("ephemeris_available", False):
        blockers.append("ephemeris_missing")
    if not rtklib_report.get("rtklib_provider_available", False):
        blockers.append("rtklib_missing")
    provider_status = provider_report.get("satellite_state_provider_status", "missing")
    if provider_status != "available":
        blockers.append(provider_status if provider_status else "provider_missing")
    factor_generated = provider_report.get("doppler_velocity_factor_generated", False)
    if provider_status == "available" and not factor_generated:
        blockers.append("doppler_velocity_factor_missing")
    activation_allowed = not blockers
    if activation_allowed:
        issue = "none"
        next_stage = "N5B_raw_doppler_ablation"
    elif "provider_missing_sat_state_export" in blockers or any("provider" in b for b in blockers):
        issue = "provider_missing_sat_state_export"
        next_stage = "N5B_rtklib_satellite_state_export_provider"
    elif "rawx_missing" in blockers:
        issue = "rawx_missing"
        next_stage = "N5B_rawx_capture_or_decoder"
    elif "ephemeris_missing" in blockers:
        issue = "ephemeris_missing"
        next_stage = "N5B_ephemeris_inventory_fix"
    else:
        issue = blockers[0] if blockers else "unknown_blocker"
        next_stage = "N5B_blocker_resolution"
    return ReadinessDecision(
        activation_allowed=activation_allowed,
        solver_enabled=activation_allowed,
        blocking_issue=issue,
        recommended_next_stage=next_stage,
        blocker_reasons=blockers,
    )
