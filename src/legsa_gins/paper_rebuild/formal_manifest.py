"""Strict CLEAN1 formal-run manifest validation and module activation gates."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

from .methods import FORMAL_METHOD_ORDER, MethodCatalog
from .protocol import CASE_ID, DATA_MODE, PROTOCOL_ID, STAGE_ID
from .paths import load_yaml_mapping


FORMAL_SCHEMA_VERSION = "paper-rebuild-formal-run-manifest-v1"

MODULE_COUNTER_FIELDS = (
    "position_update_count",
    "receiver_velocity_update_count",
    "dual_yaw_update_count",
    "raw_doppler_update_count",
    "source_aware_evaluation_count",
    "source_aware_weight_changed_count",
    "go2_roll_pitch_update_count",
    "go2_horizontal_velocity_update_count",
    "selected_fgo_feedback_update_count",
    "nine_factor_fgo_update_count",
    "qa_fallback_count",
    "multi_state_qm_update_count",
    "contact_fk_update_count",
)

FORMAL_REQUIRED_FIELDS = (
    "schema_version",
    "stage_id",
    "protocol_id",
    "case_id",
    "data_mode",
    "run_id",
    "algorithm_id",
    "method_role",
    "code_commit",
    "code_worktree_dirty_at_run",
    "executable_hash",
    "runtime_config_hash",
    "methods_yaml_hash",
    "window_contract_hash",
    "evaluator_contract_hash",
    "raw_source_hashes",
    "provider_hashes",
    "provider_generator_commit",
    "provider_generation_config_hash",
    "local_path_config_hash",
    "actual_solver_input_paths",
    "actual_solver_input_roles",
    "synthetic_data_used",
    "semisynthetic_data_used",
    "trace_used_online",
    "receiver_imu_as_body_imu",
    "final_v23_output_solver_input",
    "LegSA_output_solver_input",
    "per_case_tuning",
    "output_only_correction",
    "epoch_deleted_for_metric",
    "old_runtime_input_count",
    "legacy_provider_input_count",
    "legacy_row_input_count",
    "legacy_aggregate_input_count",
    "status_fallback_used",
    "go2_position_truth_claim",
    "go2_velocity_truth_claim",
    "go2_yaw_truth_claim",
    "go2_contact_truth_claim",
    "common_initialization",
    "common_initialization_dual_yaw_used",
    "solver_returncode",
    "runtime_seconds",
    "module_update_counts",
    "output_files",
    "output_hashes",
    "terminal_status",
    "paper_performance_claim",
)

FALSE_FIELDS = (
    "code_worktree_dirty_at_run",
    "synthetic_data_used",
    "semisynthetic_data_used",
    "trace_used_online",
    "receiver_imu_as_body_imu",
    "final_v23_output_solver_input",
    "LegSA_output_solver_input",
    "per_case_tuning",
    "output_only_correction",
    "epoch_deleted_for_metric",
    "status_fallback_used",
    "go2_position_truth_claim",
    "go2_velocity_truth_claim",
    "go2_yaw_truth_claim",
    "go2_contact_truth_claim",
    "paper_performance_claim",
)

ZERO_FIELDS = (
    "old_runtime_input_count",
    "legacy_provider_input_count",
    "legacy_row_input_count",
    "legacy_aggregate_input_count",
)

FORBIDDEN_COUNTER_FIELDS = (
    "selected_fgo_feedback_update_count",
    "nine_factor_fgo_update_count",
    "qa_fallback_count",
    "multi_state_qm_update_count",
    "contact_fk_update_count",
)

SOLVER_COUNTER_MAP = {
    "position_update_count": "position_update_count",
    "receiver_velocity_update_count": "receiver_velocity_update_count",
    "dual_yaw_update_count": "dual_yaw_update_count",
    "raw_doppler_update_count": "raw_doppler_update_count",
    "source_aware_evaluation_count": "source_aware_evaluation_count",
    "source_aware_weight_changed_count": "source_aware_weight_changed_count",
    "go2_roll_pitch_update_count": "go2_roll_pitch_update_count",
    "go2_horizontal_velocity_update_count": "go2_horizontal_velocity_update_count",
    "selected_fgo_feedback_update_count": "selected_fgo_feedback_update_count",
    "nine_factor_fgo_update_count": "nine_factor_fgo_update_count",
    "qa_fallback_count": "qa_fallback_count",
    "multi_state_qm_update_count": "multi_state_qm_update_count",
    "contact_fk_update_count": "contact_fk_update_count",
}


class FormalManifestError(ValueError):
    """A formal manifest is missing proof or contradicts its method contract."""


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def normalize_solver_module_counts(solver_manifest: Mapping[str, Any]) -> dict[str, int]:
    """Require explicit core counters; enabled flags never substitute for activation."""

    result: dict[str, int] = {}
    missing: list[str] = []
    for formal_name, solver_name in SOLVER_COUNTER_MAP.items():
        if solver_name not in solver_manifest:
            missing.append(solver_name)
            continue
        value = solver_manifest[solver_name]
        if isinstance(value, bool):
            raise FormalManifestError(f"Solver module counter is boolean: {solver_name}")
        try:
            count = int(value)
        except (TypeError, ValueError) as exc:
            raise FormalManifestError(f"Solver module counter is invalid: {solver_name}") from exc
        if count < 0:
            raise FormalManifestError(f"Solver module counter is negative: {solver_name}")
        result[formal_name] = count
    if missing:
        raise FormalManifestError("Solver manifest lacks explicit module counters: " + ",".join(missing))
    return result


def validate_module_activation_counts(method_id: str, counters: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if method_id not in FORMAL_METHOD_ORDER:
        return ["unknown_algorithm_id"]
    for field in MODULE_COUNTER_FIELDS:
        value = counters.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issues.append(f"invalid_module_counter:{field}")
    if issues:
        return issues
    positive: set[str] = {"position_update_count"}
    zero: set[str] = set(FORBIDDEN_COUNTER_FIELDS)
    if method_id == "single_antenna_EKF":
        positive.add("receiver_velocity_update_count")
        zero.update(
            {
                "dual_yaw_update_count",
                "raw_doppler_update_count",
                "source_aware_evaluation_count",
                "source_aware_weight_changed_count",
                "go2_roll_pitch_update_count",
                "go2_horizontal_velocity_update_count",
            }
        )
    elif method_id == "basic_dual_yaw_EKF":
        positive.add("dual_yaw_update_count")
        zero.update(
            {
                "receiver_velocity_update_count",
                "raw_doppler_update_count",
                "source_aware_evaluation_count",
                "source_aware_weight_changed_count",
                "go2_roll_pitch_update_count",
                "go2_horizontal_velocity_update_count",
            }
        )
    elif method_id == "strong_dual_yaw_EKF":
        positive.update({"receiver_velocity_update_count", "dual_yaw_update_count"})
        zero.update(
            {
                "raw_doppler_update_count",
                "source_aware_evaluation_count",
                "source_aware_weight_changed_count",
                "go2_roll_pitch_update_count",
                "go2_horizontal_velocity_update_count",
            }
        )
    elif method_id == "LegSA_Paper_V1":
        positive.update(
            {
                "receiver_velocity_update_count",
                "dual_yaw_update_count",
                "raw_doppler_update_count",
                "source_aware_evaluation_count",
                "go2_roll_pitch_update_count",
                "go2_horizontal_velocity_update_count",
            }
        )
        # source_aware_weight_changed_count may be zero, but evaluation must be positive.
    for field in sorted(positive):
        if counters.get(field, 0) <= 0:
            issues.append(f"required_module_not_activated:{field}")
    for field in sorted(zero):
        if counters.get(field) != 0:
            issues.append(f"forbidden_module_activated:{field}")
    return issues


def validate_formal_run_manifest(
    manifest: Mapping[str, Any],
    catalog: MethodCatalog,
    *,
    require_pass: bool = True,
) -> list[str]:
    issues: list[str] = []
    for field in FORMAL_REQUIRED_FIELDS:
        if field not in manifest:
            issues.append(f"missing_field:{field}")
    expected_scalars = {
        "schema_version": FORMAL_SCHEMA_VERSION,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
    }
    for field, expected in expected_scalars.items():
        if manifest.get(field) != expected:
            issues.append(f"field_mismatch:{field}")
    method_id = manifest.get("algorithm_id")
    if method_id not in FORMAL_METHOD_ORDER:
        issues.append("algorithm_id_outside_frozen_set")
    else:
        if manifest.get("method_role") != catalog.method(str(method_id)).get("role"):
            issues.append("method_role_mismatch")
    for field in FALSE_FIELDS:
        if manifest.get(field) is not False:
            issues.append(f"forbidden_flag_not_false:{field}")
    for field in ZERO_FIELDS:
        if manifest.get(field) != 0:
            issues.append(f"forbidden_count_not_zero:{field}")
    if manifest.get("common_initialization") is not True:
        issues.append("common_initialization_not_true")
    if manifest.get("common_initialization_dual_yaw_used") is not True:
        issues.append("common_initialization_dual_yaw_not_explicit")
    if manifest.get("solver_returncode") != 0:
        issues.append("solver_returncode_not_zero")
    runtime = manifest.get("runtime_seconds")
    if not isinstance(runtime, (int, float)) or isinstance(runtime, bool) or runtime < 0:
        issues.append("runtime_seconds_invalid")
    if require_pass and manifest.get("terminal_status") != "PASS":
        issues.append("terminal_status_not_pass")
    run_id = manifest.get("run_id")
    expected_run_ids = {
        "single_antenna_EKF": "01_single_antenna_EKF",
        "basic_dual_yaw_EKF": "02_basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF": "03_strong_dual_yaw_EKF",
        "LegSA_Paper_V1": "04_LegSA_Paper_V1",
    }
    if method_id in expected_run_ids and run_id != expected_run_ids[method_id]:
        issues.append("run_id_method_order_mismatch")
    for field in ("code_commit", "provider_generator_commit"):
        value = manifest.get(field)
        if not isinstance(value, str) or len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            issues.append(f"invalid_git_commit:{field}")

    for field in (
        "executable_hash",
        "runtime_config_hash",
        "methods_yaml_hash",
        "window_contract_hash",
        "evaluator_contract_hash",
        "provider_generation_config_hash",
        "local_path_config_hash",
    ):
        if not _valid_sha256(manifest.get(field)):
            issues.append(f"invalid_sha256:{field}")
    for field in ("raw_source_hashes", "provider_hashes", "output_hashes"):
        mapping = manifest.get(field)
        if not isinstance(mapping, Mapping) or not mapping:
            issues.append(f"empty_hash_mapping:{field}")
        elif any(not isinstance(key, str) or not _valid_sha256(value) for key, value in mapping.items()):
            issues.append(f"invalid_hash_mapping:{field}")
    roles = manifest.get("actual_solver_input_roles")
    paths = manifest.get("actual_solver_input_paths")
    if not isinstance(roles, list) or not roles or "trace" in roles:
        issues.append("actual_solver_input_roles_invalid")
    if not isinstance(paths, Mapping) or set(paths) != set(roles or []):
        issues.append("actual_solver_input_path_closure_failed")
    elif any("trace" in str(value).casefold() for value in paths.values()):
        issues.append("trace_in_actual_solver_input_paths")
    elif any(
        not isinstance(value, str)
        or value.startswith("/")
        or ".." in value.replace("\\", "/").split("/")
        for value in paths.values()
    ):
        issues.append("actual_solver_input_path_not_safe_relative")

    counters = manifest.get("module_update_counts")
    if not isinstance(counters, Mapping):
        issues.append("module_update_counts_missing")
    elif method_id in FORMAL_METHOD_ORDER:
        issues.extend(validate_module_activation_counts(str(method_id), counters))
    output_files = manifest.get("output_files")
    output_hashes = manifest.get("output_hashes")
    if not isinstance(output_files, Mapping) or not isinstance(output_hashes, Mapping):
        issues.append("output_file_hash_closure_missing")
    elif set(output_files) != set(output_hashes):
        issues.append("output_file_hash_role_mismatch")
    elif any(
        not isinstance(value, str)
        or value.startswith("/")
        or ".." in value.replace("\\", "/").split("/")
        for value in output_files.values()
    ):
        issues.append("output_file_path_not_safe_relative")
    return sorted(set(issues))


def validate_formal_schema_contract(schema_path: str, manifest: Mapping[str, Any]) -> list[str]:
    """Load the tracked schema and require it to mirror the executable validator."""

    schema = load_yaml_mapping(schema_path)
    issues: list[str] = []
    if schema.get("$id") != "paper_rebuild.formal_run_manifest.v1":
        issues.append("formal_schema_id_mismatch")
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        issues.append("formal_schema_object_boundary_mismatch")
    if tuple(schema.get("required") or ()) != FORMAL_REQUIRED_FIELDS:
        issues.append("formal_schema_required_fields_mismatch")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping) or set(properties) != set(FORMAL_REQUIRED_FIELDS):
        issues.append("formal_schema_properties_mismatch")
        return issues
    for field, definition in properties.items():
        if not isinstance(definition, Mapping):
            issues.append(f"formal_schema_property_invalid:{field}")
            continue
        if "const" in definition and manifest.get(field) != definition["const"]:
            issues.append(f"formal_schema_const_mismatch:{field}")
        if "enum" in definition and manifest.get(field) not in definition["enum"]:
            issues.append(f"formal_schema_enum_mismatch:{field}")
    module_schema = properties.get("module_update_counts")
    if not isinstance(module_schema, Mapping) or tuple(module_schema.get("required") or ()) != MODULE_COUNTER_FIELDS:
        issues.append("formal_schema_module_counter_fields_mismatch")
    issues.extend(_validate_schema_value("manifest", manifest, schema))
    return issues


def _validate_schema_value(path: str, value: Any, definition: Mapping[str, Any]) -> list[str]:
    """Execute the bounded JSON-schema keywords used by the tracked formal schema."""

    issues: list[str] = []
    expected_type = definition.get("type")
    type_ok = True
    if expected_type == "object":
        type_ok = isinstance(value, Mapping)
    elif expected_type == "array":
        type_ok = isinstance(value, list)
    elif expected_type == "string":
        type_ok = isinstance(value, str)
    elif expected_type == "number":
        type_ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    elif expected_type == "integer":
        type_ok = isinstance(value, int) and not isinstance(value, bool)
    if not type_ok:
        return [f"formal_schema_type_mismatch:{path}"]
    if "const" in definition and value != definition["const"]:
        issues.append(f"formal_schema_const_mismatch:{path}")
    if "enum" in definition and value not in definition["enum"]:
        issues.append(f"formal_schema_enum_mismatch:{path}")
    if isinstance(value, str):
        if len(value) < int(definition.get("minLength", 0)):
            issues.append(f"formal_schema_min_length:{path}")
        pattern = definition.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            issues.append(f"formal_schema_pattern_mismatch:{path}")
    if isinstance(value, Mapping):
        if len(value) < int(definition.get("minProperties", 0)):
            issues.append(f"formal_schema_min_properties:{path}")
        required = definition.get("required") or []
        for field in required:
            if field not in value:
                issues.append(f"formal_schema_missing:{path}.{field}")
        properties = definition.get("properties")
        if isinstance(properties, Mapping):
            if definition.get("additionalProperties") is False:
                for field in set(value) - set(properties):
                    issues.append(f"formal_schema_additional_property:{path}.{field}")
            for field, child_definition in properties.items():
                if field in value and isinstance(child_definition, Mapping):
                    issues.extend(
                        _validate_schema_value(
                            f"{path}.{field}", value[field], child_definition
                        )
                    )
    if isinstance(value, list):
        if len(value) < int(definition.get("minItems", 0)):
            issues.append(f"formal_schema_min_items:{path}")
        if definition.get("uniqueItems") is True:
            normalized = [repr(item) for item in value]
            if len(normalized) != len(set(normalized)):
                issues.append(f"formal_schema_unique_items:{path}")
    if "minimum" in definition and isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) < float(definition["minimum"]):
            issues.append(f"formal_schema_minimum:{path}")
    return issues


def assert_formal_run_manifest(
    manifest: Mapping[str, Any],
    catalog: MethodCatalog,
    *,
    require_pass: bool = True,
    schema_path: str | None = None,
) -> None:
    issues = validate_formal_run_manifest(manifest, catalog, require_pass=require_pass)
    resolved_schema = schema_path or str(catalog.path.with_name("formal_manifest_schema.yaml"))
    issues.extend(validate_formal_schema_contract(resolved_schema, manifest))
    if issues:
        raise FormalManifestError(";".join(sorted(set(issues))))
