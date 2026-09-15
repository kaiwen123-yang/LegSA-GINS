"""Tracked authorization and ordering guard for the repaired Canonical-541 run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONTRACT = "configs/paper_rebuild/canonical541_repaired_execution_authorization.yaml"
STAGE_ID = "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"
PROTOCOL_ID = "CANONICAL541_BY2_CONTROLLED_DEGRADATION"
RUNTIME_ROLE = "canonical541_formal_controlled_degradation_solver"


class CanonicalAuthorizationError(RuntimeError):
    pass


def validate_attempt_root(path: str | Path) -> Path:
    """Require the repaired runtime owner to be one hidden attempt below STAGE_ID."""

    root = Path(path).resolve(strict=True)
    if root.parent.name != STAGE_ID or not root.name.startswith(".attempt_"):
        raise CanonicalAuthorizationError(
            f"runtime_root must be exactly <{STAGE_ID}>/.attempt_<timestamp>"
        )
    suffix = root.name.removeprefix(".attempt_")
    if not suffix or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in suffix):
        raise CanonicalAuthorizationError("attempt timestamp contains unsafe characters")
    return root


def load_execution_authorization(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve(strict=True)
    payload = yaml.safe_load((root / CONTRACT).read_text(encoding="utf-8"))
    forbidden = payload.get("forbidden") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "paper_rebuild.canonical541_repaired_execution_authorization.v1"
        or payload.get("stage_id") != STAGE_ID
        or payload.get("protocol_id") != PROTOCOL_ID
        or payload.get("runtime_role") != RUNTIME_ROLE
        or payload.get("execution_authorized") is not True
        or payload.get("solver_allowed_after_readiness_freeze") is not True
        or payload.get("evaluator_allowed_after_output_seal") is not True
        or payload.get("trace_allowed_online") is not False
        or payload.get("human_approval_required") is not False
        or payload.get("old_method_bound_formal_reuse_allowed") is not False
        or payload.get("method_bound_rebuild_required") is not True
        or not isinstance(forbidden, dict)
        or any(forbidden.get(key) is not False for key in (
            "trace_used_online", "receiver_imu_as_body_imu",
            "final_v23_output_solver_input", "LegSA_output_solver_input",
            "per_case_tuning", "output_only_correction",
            "epoch_deleted_for_metric", "metric_driven_rerun",
        ))
        or forbidden.get("old_runtime_input_count") != 0
        or forbidden.get("legacy_provider_input_count") != 0
    ):
        raise CanonicalAuthorizationError("repaired Canonical-541 authorization drift")
    return payload


def authorize_operation(repo_root: str | Path, operation: str) -> dict[str, Any]:
    payload = load_execution_authorization(repo_root)
    required = {
        "solver": "full_algorithm_execution_allowed",
        "internal_ablation": "internal_ablation_execution_allowed",
        "offline_evaluator": "evaluator_allowed_after_output_seal",
    }
    field = required.get(operation)
    if field is None or payload.get(field) is not True:
        raise CanonicalAuthorizationError(f"operation is not authorized: {operation}")
    if operation == "offline_evaluator" and payload.get("trace_allowed_online") is not False:
        raise CanonicalAuthorizationError("offline evaluator ordering guard drift")
    return payload
