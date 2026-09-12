"""Read-only 541 x 11 Canonical registry and active-route preflight."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .ablation_registry import ABLATION_METHODS, FULL_ALIAS, validate_canonical_ablation_config
from .authorization import RUNTIME_ROLE, STAGE_ID, load_execution_authorization
from .case_manifest import build_case_manifest
from .full_method_registry import FEATURE_FIELDS, FULL_METHODS, validate_canonical_full_config
from .run_registry import build_logical_queues, resolve_execution_aliases


def _anchors() -> list[dict[str, Any]]:
    return [
        {"seed_index": f"seed_{index:02d}", "anchor_time_s": 100.0 + index,
         "selection_status": "identity_preflight_only"}
        for index in range(9)
    ]


def run_registry_preflight(repo_root: str | Path, *, code_freeze_commit: str | None = None,
                           executable_sha256: str | None = None) -> dict[str, Any]:
    repo = Path(repo_root).resolve(strict=True)
    contract = load_execution_authorization(repo)
    validate_canonical_full_config(repo / "configs/paper_rebuild/canonical_by2_full_method_modes.yaml")
    validate_canonical_ablation_config(repo / "configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml")
    cases = build_case_manifest(_anchors())
    full, ablation = build_logical_queues(cases)
    logical = [*full, *ablation]
    method_hashes: dict[tuple[str, str], str] = {}
    runtime_hashes: dict[tuple[str, str], str] = {}
    for row in logical:
        signature = "".join("1" if bool(row[field]) else "0" for field in FEATURE_FIELDS)
        pair = (str(row["method_id"]), str(row["case_id"]))
        method_hashes[pair] = hashlib.sha256(f"{row['case_id']}:{signature}".encode()).hexdigest()
        runtime_hashes[pair] = hashlib.sha256(signature.encode()).hexdigest()
    resolved, unique = resolve_execution_aliases(
        logical, method_bound_provider_hashes=method_hashes,
        runtime_config_hashes=runtime_hashes, executable_hash="e" * 64,
    )
    effective = {tuple(bool(row[field]) for field in FEATURE_FIELDS) for row in resolved}
    canonical_profiles = {
        "single_antenna_EKF", "basic_dual_yaw_EKF", "AB0000", "AB1111",
        "AB0111", "AB1011", "AB1101", "AB1110", "AB1100", "AB1000", "AB0100",
    }
    declared_profiles = {row.effective_profile for row in (*FULL_METHODS, *ABLATION_METHODS)}
    loader = (repo / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text(encoding="utf-8")
    runtime = (repo / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").read_text(encoding="utf-8")
    hardcoded_rejections = int(
        'options.stage_id == "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD" &&\n             options.algorithm_id.size()' in runtime
    )
    clean1_overwrites = int('options.port_role =\n        options.stage_id ==' in runtime)
    passed = (
        len(cases) == 541 and len({row["case_id"] for row in cases}) == 541
        and len(resolved) == 7033 and len(unique) == 5951 and len(effective) == 11
        and declared_profiles == canonical_profiles and FULL_ALIAS == {"A01": "F04", "A02": "F03"}
        and contract["runtime_role"] == RUNTIME_ROLE and contract["stage_id"] == STAGE_ID
        and STAGE_ID in loader and RUNTIME_ROLE in loader
        and hardcoded_rejections == 0 and clean1_overwrites == 0
    )
    result = {
        "schema_version": "paper_rebuild.canonical541_registry_preflight.v1",
        "stage_id": STAGE_ID,
        "runtime_role": RUNTIME_ROLE,
        "case_count": len(cases),
        "expected_identity_count": len(unique),
        "logical_row_count": len(resolved),
        "effective_config_count": len(effective),
        "duplicate_identity_count": len(unique) - len({row["execution_key"] for row in unique}),
        "missing_identity_count": 5951 - len(unique),
        "invalid_algorithm_role_route_count": 0 if STAGE_ID in loader and RUNTIME_ROLE in loader else 1,
        "hard_coded_clean2_only_rejection_count": hardcoded_rejections,
        "clean1_role_overwrite_count": clean1_overwrites,
        "method_flags_valid": declared_profiles == canonical_profiles,
        "case_bindings_valid": len(cases) == 541,
        "aliases_valid": FULL_ALIAS == {"A01": "F04", "A02": "F03"},
        "trace_open_count": 0,
        "passed": passed,
    }
    if code_freeze_commit is not None or executable_sha256 is not None:
        if (code_freeze_commit is None or len(code_freeze_commit) != 40
                or executable_sha256 is None or len(executable_sha256) != 64):
            raise ValueError("preflight freeze/executable bindings must be supplied together")
        result.update(code_freeze_commit=code_freeze_commit,
                      executable_sha256=executable_sha256)
    return result
