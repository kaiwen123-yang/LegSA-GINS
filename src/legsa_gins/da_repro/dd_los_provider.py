"""Double-difference carrier and LOS design gate for DA01."""

from __future__ import annotations

from typing import Any


def build_dd_los_summary(common_report: dict[str, Any], los_report: dict[str, Any]) -> dict[str, Any]:
    epochs_with_dd = [
        row for row in common_report.get("sample_rows", []) if int(row.get("common_satellite_count", 0)) >= 2
    ]
    carrier_dd_candidate_available = bool(epochs_with_dd)
    los_available = bool(los_report.get("los_available_for_full_backend"))
    return {
        "dd_carrier_candidate_available": carrier_dd_candidate_available,
        "dd_candidate_sample_epoch_count": len(epochs_with_dd),
        "los_available": los_available,
        "dd_design_matrix_available": carrier_dd_candidate_available and los_available,
        "dd_design_matrix_rows": 0 if not los_available else sum(int(row["common_satellite_count"]) - 1 for row in epochs_with_dd),
        "reference_satellite_policy": "highest_common_cno_or_first_sorted_pending_full_provider",
        "provider_status": "available" if carrier_dd_candidate_available and los_available else "BLOCKED_WITH_PROOF",
        "blocker_reasons": []
        if carrier_dd_candidate_available and los_available
        else sorted(
            set(
                ([] if carrier_dd_candidate_available else ["insufficient_common_satellites_for_dd"])
                + ([] if los_available else ["los_provider_not_available"])
            )
        ),
    }
