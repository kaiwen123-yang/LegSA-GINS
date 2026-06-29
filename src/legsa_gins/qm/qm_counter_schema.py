"""QM counter schema split for PAPER10M1R2C2."""

from __future__ import annotations

from typing import Any


LEGACY_COUNTER = "bad_a1_consumed_count"

CLAIM_VALID_FIELDS = [
    "a1_yaw_update_count",
    "a1_yaw_accepted_count",
    "a1_yaw_downweighted_count",
    "a1_yaw_rejected_count",
    "bad_a1_accepted_count",
    "bad_a1_downweighted_count",
    "bad_a1_rejected_count",
    "qm_state_normal_count",
    "qm_state_downweight_count",
    "qm_state_reject_count",
    "qm_state_hold_count",
    "qm_state_recovery_count",
    "qm_state_fallback_count",
    "qm_trace_required",
    "qm_trace_file_exists",
    "qm_trace_has_state_actions",
    "qm_trace_not_required",
]


def count_mapping_rows() -> list[dict[str, Any]]:
    return [
        {
            "legacy_field": LEGACY_COUNTER,
            "new_field": "a1_yaw_rejected_count",
            "source_manifest_field": "yaw_REJECT",
            "claim_valid": False,
            "reason": "legacy name implied consumed bad A1 but M1R2C1 showed it maps to yaw_REJECT/diagnostic rejection",
        },
        {
            "legacy_field": "",
            "new_field": "a1_yaw_update_count",
            "source_manifest_field": "yaw_update_count",
            "claim_valid": True,
            "reason": "total A1 yaw update attempts",
        },
        {
            "legacy_field": "",
            "new_field": "a1_yaw_accepted_count",
            "source_manifest_field": "yaw_NORMAL + yaw_DOWNWEIGHT",
            "claim_valid": True,
            "reason": "accepted yaw updates include normal and downweighted updates",
        },
        {
            "legacy_field": "",
            "new_field": "a1_yaw_downweighted_count",
            "source_manifest_field": "yaw_DOWNWEIGHT",
            "claim_valid": True,
            "reason": "downweighted yaw updates",
        },
        {
            "legacy_field": "",
            "new_field": "bad_a1_accepted_count",
            "source_manifest_field": "source-aware/QM bad-source labels when available",
            "claim_valid": False,
            "reason": "requires explicit bad-source labeling, not available from legacy counter alone",
        },
        {
            "legacy_field": "",
            "new_field": "bad_a1_downweighted_count",
            "source_manifest_field": "source-aware/QM bad-source labels when available",
            "claim_valid": False,
            "reason": "requires explicit bad-source labeling, not available from legacy counter alone",
        },
        {
            "legacy_field": "",
            "new_field": "bad_a1_rejected_count",
            "source_manifest_field": "source-aware/QM bad-source labels when available",
            "claim_valid": False,
            "reason": "requires explicit bad-source labeling, not available from legacy counter alone",
        },
    ]


def split_manifest_counters(manifest: dict[str, Any], *, qm_trace_required: bool, qm_trace_file_exists: bool) -> dict[str, Any]:
    yaw_normal = int(float(manifest.get("yaw_NORMAL", 0) or 0))
    yaw_down = int(float(manifest.get("yaw_DOWNWEIGHT", 0) or 0))
    yaw_reject = int(float(manifest.get("yaw_REJECT", 0) or 0))
    qm_normal = _sum_dict(manifest.get("qm_normal_count_by_source", {}))
    qm_down = _sum_dict(manifest.get("qm_downweight_count_by_source", {}))
    qm_reject = _sum_dict(manifest.get("qm_reject_count_by_source", {}))
    qm_hold = _sum_dict(manifest.get("qm_hold_count_by_source", {}))
    qm_recovery = _sum_dict(manifest.get("qm_recovery_count_by_source", {}))
    qm_fallback = _sum_dict(manifest.get("qm_fallback_count_by_source", {}))
    yaw_update = int(float(manifest.get("yaw_update_count", 0) or 0))
    # Runtime yaw_NORMAL/yaw_DOWNWEIGHT/yaw_REJECT are diagnostic event counters
    # and can overlap in source-aware/QM paths. Accepted must therefore be
    # derived from update attempts minus final rejected attempts.
    accepted = max(0, yaw_update - yaw_reject)
    return {
        "a1_yaw_update_count": yaw_update,
        "a1_yaw_accepted_count": accepted,
        "a1_yaw_downweighted_count": min(yaw_down, accepted),
        "a1_yaw_rejected_count": yaw_reject,
        "bad_a1_accepted_count": "",
        "bad_a1_downweighted_count": "",
        "bad_a1_rejected_count": "",
        "qm_state_normal_count": qm_normal,
        "qm_state_downweight_count": qm_down,
        "qm_state_reject_count": qm_reject,
        "qm_state_hold_count": qm_hold,
        "qm_state_recovery_count": qm_recovery,
        "qm_state_fallback_count": qm_fallback,
        "qm_trace_required": bool(qm_trace_required),
        "qm_trace_file_exists": bool(qm_trace_file_exists),
        "qm_trace_has_state_actions": any(value > 0 for value in [qm_down, qm_reject, qm_hold, qm_recovery, qm_fallback]),
        "qm_trace_not_required": not bool(qm_trace_required),
        "legacy_bad_a1_consumed_count_deprecated": True,
        "legacy_bad_a1_consumed_count_valid_for_claim": False,
    }


def _sum_dict(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for item in value.values():
        try:
            total += int(float(item))
        except (TypeError, ValueError):
            continue
    return total
