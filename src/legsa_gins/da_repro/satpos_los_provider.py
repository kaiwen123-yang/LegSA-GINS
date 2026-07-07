"""Satellite position and LOS provider gate for DA01."""

from __future__ import annotations

from typing import Any


def build_satpos_los_summary(rinex_report: dict[str, Any], common_report: dict[str, Any]) -> dict[str, Any]:
    obs_ok = bool(rinex_report.get("obs_generated"))
    nav_ok = bool(rinex_report.get("nav_generated"))
    common_ok = bool(common_report.get("common_rawx_available"))
    # RTKLIB convbin can generate RINEX, but this repo does not yet expose a
    # satellite-state export API for per-epoch LOS vectors. Keep this blocked
    # rather than silently using status yaw as a C-LAMBDA backend.
    los_available = False
    blockers: list[str] = []
    if not obs_ok:
        blockers.append("rinex_obs_missing")
    if not nav_ok:
        blockers.append("rinex_nav_missing")
    if not common_ok:
        blockers.append("common_epoch_satellite_missing")
    blockers.append("satellite_state_los_export_not_implemented")
    return {
        "rinex_obs_available": obs_ok,
        "rinex_nav_available": nav_ok,
        "common_rawx_available": common_ok,
        "satellite_position_provider": "not_available",
        "los_design_rows": 0,
        "los_provider_status": "BLOCKED_WITH_PROOF",
        "los_available_for_full_backend": los_available,
        "blocker_reasons": sorted(set(blockers)),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "status_yaw_used_as_los": False,
    }
