"""构建 CLEAN2R2A1 的 18 行 clean-only 正式配置注册表。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clean2r2a_ablation import (
    BIT_ORDER,
    CASE_ID,
    DATA_MODE,
    STAGE_ID,
    AblationProfile,
    assert_canonical_method_identities,
    canonical_ablation_profiles,
    load_ablation_contract,
)
from .methods import EXPECTED_FEATURES, FEATURE_FIELDS
from .paths import load_yaml_mapping


FORMAL_CONFIGURATION_ORDER = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    *(f"AB{value:04b}" for value in range(16)),
)


class Clean2R2ARegistryError(ValueError):
    """clean 注册表不是严格的 18 配置闭包。"""


@dataclass(frozen=True)
class CleanRunProfile:
    configuration_id: str
    algorithm_id: str
    role: str
    backbone_method_id: str
    bit_string: str | None
    feature_flags: Mapping[str, bool]
    canonical_equivalent_method_id: str | None


def _profile_hash(profile: CleanRunProfile) -> str:
    # 配置身份包含 configuration_id；不能因 canonical 等价而折叠正式运行。
    payload = {
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "configuration_id": profile.configuration_id,
        "algorithm_id": profile.algorithm_id,
        "backbone_method_id": profile.backbone_method_id,
        "bit_string": profile.bit_string,
        "feature_flags": dict(profile.feature_flags),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _baseline_profiles() -> tuple[CleanRunProfile, CleanRunProfile]:
    return (
        CleanRunProfile(
            configuration_id="single_antenna_EKF",
            algorithm_id="single_antenna_EKF",
            role="structural_baseline",
            backbone_method_id="single_antenna_EKF",
            bit_string=None,
            feature_flags=dict(EXPECTED_FEATURES["single_antenna_EKF"]),
            canonical_equivalent_method_id="single_antenna_EKF",
        ),
        CleanRunProfile(
            configuration_id="basic_dual_yaw_EKF",
            algorithm_id="basic_dual_yaw_EKF",
            role="structural_baseline",
            backbone_method_id="basic_dual_yaw_EKF",
            bit_string=None,
            feature_flags=dict(EXPECTED_FEATURES["basic_dual_yaw_EKF"]),
            canonical_equivalent_method_id="basic_dual_yaw_EKF",
        ),
    )


def _ablation_run_profile(profile: AblationProfile) -> CleanRunProfile:
    return CleanRunProfile(
        configuration_id=profile.configuration_id,
        # 中文说明：formal algorithm_id 保留 AB 身份；backbone 字段单独锁定 strong。
        algorithm_id=profile.configuration_id,
        role="ablation_configuration",
        backbone_method_id="strong_dual_yaw_EKF",
        bit_string=profile.bit_string,
        feature_flags=dict(profile.feature_flags),
        canonical_equivalent_method_id=(
            profile.canonical_equivalent_method_id
        ),
    )


def build_clean_run_registry(
    ablation_contract_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    profiles = (
        load_ablation_contract(ablation_contract_path)
        if ablation_contract_path is not None
        else canonical_ablation_profiles()
    )
    assert_canonical_method_identities(profiles)
    run_profiles = (*_baseline_profiles(), *(_ablation_run_profile(item) for item in profiles))
    rows: list[dict[str, Any]] = []
    for order, profile in enumerate(run_profiles, start=1):
        rows.append(
            {
                "run_order": order,
                "run_id": f"{order:02d}_{profile.configuration_id}",
                "stage_id": STAGE_ID,
                "case_id": CASE_ID,
                "data_mode": DATA_MODE,
                "configuration_id": profile.configuration_id,
                "algorithm_id": profile.algorithm_id,
                "role": profile.role,
                "backbone_method_id": profile.backbone_method_id,
                "bit_string": profile.bit_string or "NOT_APPLICABLE",
                "canonical_equivalent_method_id": profile.canonical_equivalent_method_id or "NONE",
                **dict(profile.feature_flags),
                "synthetic_data_used": False,
                "semisynthetic_data_used": False,
                "trace_used_online": False,
                "per_case_tuning": False,
                "metric_driven_rerun": False,
                "profile_identity_hash": _profile_hash(profile),
            }
        )
    validate_clean_run_registry(rows)
    return rows


def validate_clean_run_registry(rows: Sequence[Mapping[str, Any]]) -> None:
    if len(rows) != 18:
        raise Clean2R2ARegistryError("clean run registry must contain exactly 18 rows")
    observed = tuple(str(row.get("configuration_id")) for row in rows)
    if observed != FORMAL_CONFIGURATION_ORDER:
        raise Clean2R2ARegistryError("clean run order or identity mismatch")
    run_ids = [str(row.get("run_id")) for row in rows]
    hashes = [str(row.get("profile_identity_hash")) for row in rows]
    if len(set(run_ids)) != 18 or len(set(hashes)) != 18:
        raise Clean2R2ARegistryError("all 18 run identities must be unique")
    feature_signatures = {
        tuple(row.get(field) for field in FEATURE_FIELDS)
        for row in rows
    }
    if len(feature_signatures) != 18:
        raise Clean2R2ARegistryError("all 18 effective feature identities must be unique")
    for order, row in enumerate(rows, start=1):
        if row.get("run_order") != order:
            raise Clean2R2ARegistryError("run order is not contiguous")
        if row.get("data_mode") != DATA_MODE:
            raise Clean2R2ARegistryError("clean data mode drifted")
        if any(row.get(field) is not False for field in (
            "synthetic_data_used",
            "semisynthetic_data_used",
            "trace_used_online",
            "per_case_tuning",
            "metric_driven_rerun",
        )):
            raise Clean2R2ARegistryError("forbidden clean-run flag is not false")
        if tuple(field for field in FEATURE_FIELDS if field in row) != FEATURE_FIELDS:
            raise Clean2R2ARegistryError("feature flag closure mismatch")


def _walk_keys(value: Any) -> tuple[str, ...]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return tuple(keys)


def validate_execution_protocol(path: str | Path) -> dict[str, Any]:
    payload = load_yaml_mapping(path)
    if payload.get("schema_version") != "paper_rebuild.clean2r2a1_execution.v1":
        raise Clean2R2ARegistryError("execution protocol schema mismatch")
    if payload.get("stage_id") != STAGE_ID or payload.get("case_id") != CASE_ID:
        raise Clean2R2ARegistryError("execution protocol identity mismatch")
    if payload.get("protocol_id") != "CLEAN2R2A1_BY2_CLEAN_MODULE_ABLATION_RESUME":
        raise Clean2R2ARegistryError("execution protocol id mismatch")
    if (
        payload.get("solver_parent_stage_id") != "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
        or payload.get("solver_parent_protocol_id") != "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION"
        or payload.get("provider_stage_id") != "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
        or payload.get("provider_protocol_id") != "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION"
        or payload.get("provider_freeze_commit") != "91793894a43c8ba83c25d8da698b7ee16e31b80e"
    ):
        raise Clean2R2ARegistryError("solver/provider parent identity mismatch")
    if payload.get("data_mode") != DATA_MODE:
        raise Clean2R2ARegistryError("execution protocol is not clean BY2 raw")
    if payload.get("formal_configuration_count") != 18:
        raise Clean2R2ARegistryError("execution protocol count mismatch")
    if tuple(payload.get("formal_order") or ()) != FORMAL_CONFIGURATION_ORDER:
        raise Clean2R2ARegistryError("execution protocol order mismatch")
    scope = payload.get("scope")
    execution = payload.get("execution")
    trace = payload.get("trace_policy")
    if not isinstance(scope, Mapping) or not isinstance(execution, Mapping) or not isinstance(trace, Mapping):
        raise Clean2R2ARegistryError("execution protocol sections are missing")
    if scope.get("clean_case_only") is not True or scope.get("non_clean_case_count") != 0:
        raise Clean2R2ARegistryError("execution protocol is not clean-only")
    if scope.get("non_clean_execution_authorized") is not False:
        raise Clean2R2ARegistryError("non-clean execution was authorized")
    if execution.get("metric_driven_rerun") is not False or execution.get("per_case_tuning") is not False:
        raise Clean2R2ARegistryError("metric-driven execution is forbidden")
    if trace.get("trace_used_online") is not False or trace.get("trace_open_before_all_outputs_sealed") is not False:
        raise Clean2R2ARegistryError("trace embargo is not closed")
    forbidden_key_fragments = ("degradation", "perturbation", "seed")
    if any(fragment in key.casefold() for key in _walk_keys(payload) for fragment in forbidden_key_fragments):
        raise Clean2R2ARegistryError("non-clean axis appeared in the clean protocol")
    return dict(payload)
