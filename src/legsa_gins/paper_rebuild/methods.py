"""Machine-readable CLEAN1 method contracts sourced only from methods.yaml."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .manifest import sha256_file, sha256_text, write_json_atomic
from .paths import load_yaml_mapping


FORMAL_METHOD_ORDER = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    "strong_dual_yaw_EKF",
    "LegSA_Paper_V1",
)

FEATURE_FIELDS = (
    "enable_dual_yaw",
    "enable_receiver_velocity",
    "enable_raw_doppler",
    "enable_source_aware",
    "enable_go2_roll_pitch_prior",
    "enable_go2_horizontal_velocity_prior",
)

EXPECTED_FEATURES: dict[str, dict[str, bool]] = {
    "single_antenna_EKF": {
        "enable_dual_yaw": False,
        "enable_receiver_velocity": True,
        "enable_raw_doppler": False,
        "enable_source_aware": False,
        "enable_go2_roll_pitch_prior": False,
        "enable_go2_horizontal_velocity_prior": False,
    },
    "basic_dual_yaw_EKF": {
        "enable_dual_yaw": True,
        "enable_receiver_velocity": False,
        "enable_raw_doppler": False,
        "enable_source_aware": False,
        "enable_go2_roll_pitch_prior": False,
        "enable_go2_horizontal_velocity_prior": False,
    },
    "strong_dual_yaw_EKF": {
        "enable_dual_yaw": True,
        "enable_receiver_velocity": True,
        "enable_raw_doppler": False,
        "enable_source_aware": False,
        "enable_go2_roll_pitch_prior": False,
        "enable_go2_horizontal_velocity_prior": False,
    },
    "LegSA_Paper_V1": {
        "enable_dual_yaw": True,
        "enable_receiver_velocity": True,
        "enable_raw_doppler": True,
        "enable_source_aware": True,
        "enable_go2_roll_pitch_prior": True,
        "enable_go2_horizontal_velocity_prior": True,
    },
}

FORBIDDEN_DEFAULT_FIELDS = (
    "trace_used_online",
    "final_v23_output_solver_input",
    "LegSA_output_solver_input",
    "per_case_tuning",
    "output_only_correction",
    "epoch_deleted_for_metric",
    "enable_selected_fgo_feedback",
    "enable_no_feedback_fgo",
    "enable_active_nine_factor_fgo",
    "enable_multi_state_qm",
    "enable_qa_fallback",
    "enable_go2_joint_factor",
    "enable_go2_position_truth",
    "enable_go2_velocity_truth",
    "enable_go2_yaw_truth",
    "enable_go2_contact_truth",
)

EXPECTED_DUAL_YAW_SOURCE_CONTRACT: dict[str, Any] = {
    "baseline_vector": "gnss2_minus_gnss1",
    "lateral_body_offset_deg": 90.0,
    "residual": "wrap_safe",
    "trace_selects_sign_or_offset": False,
    "by2_clean_median_length_gate_m": [0.20, 0.60],
    "forbidden_four_meter_regression_band_m": [3.5, 4.5],
    "per_epoch_out_of_band_action": "label_only_not_metric_deletion",
    "applicability": "BY2_clean_contract_not_universal_dataset_range",
}

COMMON_YAW_CONTRACT: dict[str, Any] = {
    "baseline_vector": "gnss2_minus_gnss1",
    "lateral_body_offset_deg": 90.0,
    "residual": "wrap_safe",
    "trace_selects_sign_or_offset": False,
}

EXPECTED_METHOD_CONTRACTS: dict[str, dict[str, Any]] = {
    "single_antenna_EKF": {
        "role": "baseline",
        "required_inputs": ["imu", "gnss_position", "receiver_velocity"],
        "optional_inputs": [],
        "features": EXPECTED_FEATURES["single_antenna_EKF"],
        "claim_scope": "baseline_only",
    },
    "basic_dual_yaw_EKF": {
        "role": "baseline",
        "required_inputs": ["imu", "gnss_position", "dual_antenna_body_yaw"],
        "optional_inputs": [],
        "yaw_contract": {**COMMON_YAW_CONTRACT, "fixed_std_deg": 1.5},
        "features": EXPECTED_FEATURES["basic_dual_yaw_EKF"],
        "claim_scope": "baseline_only",
    },
    "strong_dual_yaw_EKF": {
        "role": "strong_baseline",
        "required_inputs": ["imu", "gnss_position", "receiver_velocity", "dual_antenna_body_yaw"],
        "optional_inputs": [],
        "yaw_contract": COMMON_YAW_CONTRACT,
        "features": EXPECTED_FEATURES["strong_dual_yaw_EKF"],
        "claim_scope": "strong_baseline_only",
    },
    "LegSA_Paper_V1": {
        "role": "proposed_method",
        "required_inputs": [
            "imu",
            "gnss_position",
            "receiver_velocity",
            "dual_antenna_body_yaw",
            "raw_doppler_velocity",
            "go2_roll_pitch_weak_prior",
            "go2_horizontal_velocity_weak_prior",
        ],
        "optional_inputs": [],
        "yaw_contract": COMMON_YAW_CONTRACT,
        "features": EXPECTED_FEATURES["LegSA_Paper_V1"],
        "excluded_features": [
            "selected_fgo_feedback",
            "active_nine_factor_fgo",
            "multi_state_qm_as_main_innovation",
            "qa_fallback",
            "complete_contact_or_fk_factor",
            "go2_truth",
        ],
        "claim_scope": "no_performance_claim_until_fresh_clean_multidataset_review",
    },
}

PERMITTED_RUNTIME_DIFFERENCE_FIELDS = frozenset(
    {
        "algorithm_id",
        "method_role",
        "run_id",
        "run_label",
        "output_dir_alias",
        "enable_basic_dual_yaw_baseline",
        "basic_dual_yaw_fixed_std_deg",
        *FEATURE_FIELDS,
    }
)

REQUIRED_COMMON_RUNTIME_FIELDS = (
    "dataset",
    "case_id",
    "code_commit",
    "provider_bundle_hash",
    "window_contract_hash",
    "common_initialization_hash",
    "base_parameters_hash",
    "frame_contract_hash",
    "antenna_geometry_hash",
    "evaluator_contract_hash",
    "numerical_precision",
    "executable_hash",
    "environment_hash",
    "timeout_seconds",
)


class MethodContractError(ValueError):
    """The tracked method catalog or an effective runtime config diverged."""


@dataclass(frozen=True)
class MethodCatalog:
    path: Path
    payload: dict[str, Any]
    source_sha256: str

    def method(self, method_id: str) -> dict[str, Any]:
        methods = self.payload["methods"]
        if method_id not in methods:
            raise MethodContractError(f"Unknown formal method: {method_id}")
        return dict(methods[method_id])

    def features(self, method_id: str) -> dict[str, bool]:
        return dict(self.method(method_id)["features"])


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MethodContractError(f"{label} must be a mapping")
    return value


def load_method_catalog(path: str | Path) -> MethodCatalog:
    """Load and fully validate the sole machine-readable method source."""

    source = Path(path).resolve(strict=True)
    payload = load_yaml_mapping(source)
    if payload.get("schema_version") != "paper_rebuild.methods.v1":
        raise MethodContractError("methods.yaml schema_version mismatch")
    if payload.get("paper_method_id") != "LegSA_Paper_V1":
        raise MethodContractError("methods.yaml paper_method_id mismatch")

    if set(payload) != {"schema_version", "paper_method_id", "defaults", "dual_yaw_source_contract", "methods"}:
        raise MethodContractError("methods.yaml top-level fields differ from the frozen contract")
    defaults = _require_mapping(payload.get("defaults"), "defaults")
    expected_defaults = {"solver_namespace": "legsa_gins.paper_rebuild"}
    expected_defaults.update({field: False for field in FORBIDDEN_DEFAULT_FIELDS})
    if dict(defaults) != expected_defaults:
        raise MethodContractError("methods.yaml defaults differ from the frozen clean contract")

    dual = _require_mapping(payload.get("dual_yaw_source_contract"), "dual_yaw_source_contract")
    if dict(dual) != EXPECTED_DUAL_YAW_SOURCE_CONTRACT:
        raise MethodContractError("Dual-yaw source contract differs from the frozen contract")

    methods = _require_mapping(payload.get("methods"), "methods")
    if tuple(methods.keys()) != FORMAL_METHOD_ORDER:
        raise MethodContractError("Formal method set/order must exactly match the CLEAN1 freeze")
    for method_id in FORMAL_METHOD_ORDER:
        method = _require_mapping(methods[method_id], f"methods.{method_id}")
        expected_method = EXPECTED_METHOD_CONTRACTS[method_id]
        if set(method) != set(expected_method):
            raise MethodContractError(f"Method fields differ from the frozen contract: {method_id}")
        features = _require_mapping(method.get("features"), f"methods.{method_id}.features")
        if tuple(features.keys()) != FEATURE_FIELDS:
            raise MethodContractError(f"Feature fields/order mismatch for {method_id}")
        if dict(features) != EXPECTED_FEATURES[method_id]:
            raise MethodContractError(f"Frozen feature matrix mismatch for {method_id}")
        if dict(method) != expected_method:
            raise MethodContractError(f"Method contract value mismatch: {method_id}")
    return MethodCatalog(path=source, payload=payload, source_sha256=sha256_file(source))


def effective_method_rows(catalog: MethodCatalog) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    defaults = catalog.payload["defaults"]
    for index, method_id in enumerate(FORMAL_METHOD_ORDER, start=1):
        method = catalog.method(method_id)
        row: dict[str, Any] = {
            "method_order": index,
            "algorithm_id": method_id,
            "method_role": method["role"],
            **catalog.features(method_id),
            "fixed_dual_yaw_std_deg": (
                method.get("yaw_contract", {}).get("fixed_std_deg", "NOT_METHOD_SPECIFIC")
            ),
        }
        row.update({field: defaults[field] for field in FORBIDDEN_DEFAULT_FIELDS})
        rows.append(row)
    return rows


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(
        dict(payload),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def audit_effective_config_differences(
    catalog: MethodCatalog,
    effective_configs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Fail closed if any non-method field differs or a feature flag drifts."""

    issues: list[str] = []
    if tuple(effective_configs.keys()) != FORMAL_METHOD_ORDER:
        issues.append("method_set_or_order_mismatch")
    for method_id in FORMAL_METHOD_ORDER:
        config = effective_configs.get(method_id)
        if not isinstance(config, Mapping):
            issues.append(f"missing_effective_config:{method_id}")
            continue
        for field in REQUIRED_COMMON_RUNTIME_FIELDS:
            if field not in config:
                issues.append(f"missing_common_field:{method_id}:{field}")
        for field, expected in EXPECTED_FEATURES[method_id].items():
            if config.get(field) is not expected:
                issues.append(f"feature_mismatch:{method_id}:{field}")
        if config.get("method_role") != EXPECTED_METHOD_CONTRACTS[method_id]["role"]:
            issues.append(f"method_role_mismatch:{method_id}")
        expected_basic = method_id == "basic_dual_yaw_EKF"
        if config.get("enable_basic_dual_yaw_baseline") is not expected_basic:
            issues.append(f"basic_dual_yaw_derived_flag_mismatch:{method_id}")
        expected_std: Any = 1.5 if expected_basic else "NOT_METHOD_SPECIFIC"
        if config.get("basic_dual_yaw_fixed_std_deg") != expected_std:
            issues.append(f"basic_dual_yaw_fixed_std_mismatch:{method_id}")
        for field in FORBIDDEN_DEFAULT_FIELDS:
            if config.get(field) is not False:
                issues.append(f"forbidden_effective_flag_not_false:{method_id}:{field}")

    all_fields = sorted({field for config in effective_configs.values() for field in config})
    allowed_fields = set(REQUIRED_COMMON_RUNTIME_FIELDS) | set(PERMITTED_RUNTIME_DIFFERENCE_FIELDS) | set(FORBIDDEN_DEFAULT_FIELDS)
    for field in all_fields:
        if field not in allowed_fields:
            issues.append(f"unexpected_effective_config_field:{field}")
    differences: dict[str, dict[str, Any]] = {}
    for field in all_fields:
        values = {method_id: effective_configs.get(method_id, {}).get(field) for method_id in FORMAL_METHOD_ORDER}
        encoded = {json.dumps(value, ensure_ascii=False, sort_keys=True, default=str) for value in values.values()}
        if len(encoded) > 1:
            differences[field] = values
            if field not in PERMITTED_RUNTIME_DIFFERENCE_FIELDS:
                issues.append(f"unpermitted_method_difference:{field}")
    for field in REQUIRED_COMMON_RUNTIME_FIELDS:
        values = [effective_configs.get(method_id, {}).get(field) for method_id in FORMAL_METHOD_ORDER]
        if len({json.dumps(value, sort_keys=True, default=str) for value in values}) != 1:
            issues.append(f"common_field_mismatch:{field}")
    return {
        "schema_version": "paper-rebuild-method-config-diff-audit-v1",
        "evidence_layer": "preexecution_derived_from_methods_yaml_and_frozen_common_contracts",
        "postparse_runtime_manifest_check_required": True,
        "method_order": list(FORMAL_METHOD_ORDER),
        "permitted_difference_fields": sorted(PERMITTED_RUNTIME_DIFFERENCE_FIELDS),
        "observed_differences": differences,
        "issues": sorted(set(issues)),
        "passed": not issues,
    }


def assert_effective_config_differences(
    catalog: MethodCatalog,
    effective_configs: Mapping[str, Mapping[str, Any]],
) -> None:
    audit = audit_effective_config_differences(catalog, effective_configs)
    if not audit["passed"]:
        raise MethodContractError(";".join(audit["issues"]))


def write_method_freeze(
    catalog: MethodCatalog,
    output_dir: str | Path,
    *,
    effective_configs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    snapshot = destination / "METHODS_SNAPSHOT.yaml"
    snapshot.write_text(_dump_yaml(catalog.payload), encoding="utf-8")
    snapshot_hash = sha256_file(snapshot)
    (destination / "METHODS_SNAPSHOT.sha256").write_text(
        f"{snapshot_hash}  METHODS_SNAPSHOT.yaml\n", encoding="utf-8"
    )

    rows = effective_method_rows(catalog)
    matrix = destination / "EFFECTIVE_METHOD_FLAG_MATRIX.csv"
    with matrix.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    audit = (
        audit_effective_config_differences(catalog, effective_configs)
        if effective_configs is not None
        else {
            "schema_version": "paper-rebuild-method-config-diff-audit-v1",
            "method_order": list(FORMAL_METHOD_ORDER),
            "status": "PENDING_EFFECTIVE_RUNTIME_CONFIGS",
            "passed": False,
            "issues": ["effective_runtime_configs_not_supplied"],
        }
    )
    audit_path = write_json_atomic(destination / "METHOD_CONFIG_DIFF_AUDIT.json", audit)
    return {
        "methods_yaml_hash": catalog.source_sha256,
        "methods_snapshot_hash": snapshot_hash,
        "effective_matrix_hash": sha256_file(matrix),
        "config_diff_audit_hash": sha256_file(audit_path),
    }


def canonical_config_hash(config: Mapping[str, Any]) -> str:
    return sha256_text(json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def ordered_method_ids(value: Sequence[str]) -> tuple[str, ...]:
    result = tuple(value)
    if result != FORMAL_METHOD_ORDER:
        raise MethodContractError("Requested methods are not the exact frozen CLEAN1 order")
    return result
