"""Fail-closed CLEAN1 provider bundle and Raw Doppler backend contracts.

This module intentionally does not discover or synthesize a backend. A wrapper
must provide an exact pinned tool/source report and an explicit artifact map.
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .evidence import (
    BY2_BODY_RELATIVE_PATH,
    BY2_FIX_PREFIX,
    BY2_RAW_RELATIVE_PATHS,
    BY2_TRACE_RELATIVE_PATH,
    EvidenceContractError,
    validate_provider_source_read_set,
)
from .manifest import git_code_state, read_hash_lock, sha256_file, verify_raw_sources
from .paths import CleanPaths, guard_path


PINNED_RTKLIB_REMOTE = "https://github.com/tomojitakasu/RTKLIB.git"
PINNED_RTKLIB_COMMIT = "180043ee24b6d2b168f98b64be15f69d50046b1a"
RAW_DOPPLER_TIME_CONVERSION = (
    "clean_seconds_of_UTC_day=GPST_TOW-"
    "GPS_day_index_from_UTC_date*86400-leap_seconds"
)
RAW_DOPPLER_COVARIANCE_POLICY = "conservative_isotropic_max_ecef_std_floor_0p2_mps"

V1_REQUIRED_FORMAL_PROVIDER_ROLES = (
    "imu_runtime_input",
    "gnss_runtime_input",
    "dual_yaw_provider",
    "raw_doppler_provider",
    "go2_attitude_prior",
    "go2_horizontal_velocity_prior",
    "source_quality_metadata",
)
V2_REQUIRED_FORMAL_PROVIDER_ROLES = (
    *V1_REQUIRED_FORMAL_PROVIDER_ROLES,
    "kick_alignment_contract",
    "kick_alignment_report",
    "kick_event_diagnostic",
    "kick_maintained_initial_segment",
    "common_start_time_contract",
)
# The active tracked protocol is V2; V1 remains an explicit compatibility set.
REQUIRED_FORMAL_PROVIDER_ROLES = V2_REQUIRED_FORMAL_PROVIDER_ROLES

V1_MAINTAINED_SHARED_SOURCE_FILES = (
    "src/legsa_gins/datasets/by2/go2_body_state_parser.py",
    "src/legsa_gins/datasets/by2/unitree_imu_semantics.py",
    "src/legsa_gins/go2_prior/go2_contact_state.py",
    "src/legsa_gins/go2_prior/go2_velocity_frame_review.py",
    "src/legsa_gins/go2_prior/go2_velocity_quality.py",
    "src/legsa_gins/input_generation/imu_txt_builder.py",
    "src/legsa_gins/input_generation/process_data_compat.py",
    "src/legsa_gins/input_generation/process_data_coverage.py",
    "src/legsa_gins/input_generation/status_yaw_builder.py",
    "src/legsa_gins/input_generation/ubx_nav_pvt.py",
    "src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py",
    "src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py",
    "src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py",
    "src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py",
)
V2_MAINTAINED_SHARED_SOURCE_FILES = (
    "src/legsa_gins/paper_rebuild/kick_alignment.py",
    *V1_MAINTAINED_SHARED_SOURCE_FILES,
    "src/legsa_gins/time_alignment/event_normalization.py",
    "src/legsa_gins/time_alignment/time_domain_audit.py",
)
MAINTAINED_SHARED_SOURCE_FILES = V2_MAINTAINED_SHARED_SOURCE_FILES

AUDIT_ONLY_PROVIDER_ROLES = frozenset(
    {
        "dual_yaw_provider",
        "source_quality_metadata",
        "kick_alignment_contract",
        "kick_alignment_report",
        "kick_event_diagnostic",
        "kick_maintained_initial_segment",
        "common_start_time_contract",
    }
)

FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS = (
    f"{BY2_FIX_PREFIX}/gnss1-status.csv",
    f"{BY2_FIX_PREFIX}/gnss2-status.csv",
    f"{BY2_FIX_PREFIX}/gnss1-raw.csv",
    BY2_BODY_RELATIVE_PATH,
)

FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES = {
    f"{BY2_FIX_PREFIX}/gnss1-status.csv": (
        "gnss_position_and_raw_doppler_approx_position_date_source"
    ),
    f"{BY2_FIX_PREFIX}/gnss2-status.csv": "fixed_physical_dual_yaw_source",
    f"{BY2_FIX_PREFIX}/gnss1-raw.csv": (
        "receiver_velocity_nav_pvt_and_rawx_sfrbx_raw_doppler_observation_source"
    ),
    BY2_BODY_RELATIVE_PATH: "propagation_imu_source",
}

REPORT_ONLY_DESCENDANT_PATHS = frozenset(
    {"docs/paper_rebuild/CLEAN1_STATUS.md"}
)

RAW_DOPPLER_REQUIRED_FIELDS = (
    "schema_version",
    "raw_doppler_backend_lineage_proven",
    "raw_doppler_backend_id",
    "raw_doppler_backend_source_files",
    "raw_doppler_backend_source_hashes",
    "helper_source_files",
    "helper_source_hashes",
    "helper_executable_hash",
    "obs_source_hash",
    "nav_source_hash",
    "conversion_config_hash",
    "conversion_contract",
    "raw_epoch_count",
    "valid_epoch_count",
    "invalid_epoch_count",
    "sat_count_min",
    "sat_count_median",
    "sat_count_max",
    "covariance_policy",
    "rtklib_source_mode",
    "rtklib_remote",
    "rtklib_commit",
    "rtklib_tracked_source_dirty",
    "rtklib_untracked_build_outputs_present",
    "rtklib_source_files",
    "rtklib_source_hashes",
    "helper_compiled_rtklib_source_files",
    "convbin_compiled_source_files",
    "convbin_executable_hash",
    "rebuilt_ubx_hash",
    "compiler_version",
    "convbin_clean_build",
    "convbin_preexisting_output_count",
    "retained_backend_artifacts",
    "retained_backend_bundle_hash",
    "runtime_patch_applied",
    "external_ephemeris_downloaded",
    "time_conversion_formula",
    "time_conversion_inputs_source_backed",
    "approx_position_source_relative_path",
    "approx_position_source_hash",
    "approx_position_geodetic_deg_m",
    "selected_status_row_number",
    "selected_status_fields_sha256",
    "gps_week",
    "first_epoch_fit_used",
    "rtklib_position_solution_used_as_solver_input",
    "nav_pvt_velocity_used_as_raw_doppler",
    "gnss_velocity_used_as_raw_doppler",
    "status_fallback_used",
    "legacy_provider_used",
    "source_discovery_used",
    "sat_count_semantics",
    "helper_source_hash",
)

RAW_OBSERVATION_SOURCE_NAMES = frozenset(
    {
        "gnss1-raw.csv",
        "gnss2-raw.csv",
    }
)


class FormalProviderError(EvidenceContractError):
    """Formal provider lineage is incomplete or contaminated."""


def _provider_protocol_suffix(provider_root: Path) -> str:
    """Resolve a canonical or guarded hidden-attempt provider identity."""

    identities = (
        "CLEAN1_BY2_CLEAN_NORMAL_V1",
        "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED",
    )
    name = provider_root.name
    if name in identities:
        return name
    for identity in identities:
        prefix = f".{identity}.attempt-"
        if not name.startswith(prefix):
            continue
        token = name.removeprefix(prefix)
        if len(token) == 32 and all(
            character in "0123456789abcdef" for character in token
        ):
            return identity
    raise FormalProviderError(
        "Formal provider root is not canonical or a guarded attempt"
    )


def _assert_exact_provider_artifact_roles(
    artifacts: Mapping[str, Any],
    required_roles: tuple[str, ...] = REQUIRED_FORMAL_PROVIDER_ROLES,
) -> None:
    """Validate the exact JSON-object key set without relying on key order."""

    if set(artifacts) != set(required_roles):
        raise FormalProviderError("Formal provider artifact role set mismatch")


@dataclass(frozen=True)
class FormalProviderBundle:
    root: Path
    artifacts: dict[str, Path]
    provider_relpaths: dict[str, str]
    provider_hashes: dict[str, str]
    raw_source_hashes: dict[str, str]
    actual_source_read_set: tuple[dict[str, Any], ...]
    generator_code_commit: str
    generator_config_hash: str
    local_path_config_hash: str
    raw_doppler_report: dict[str, Any]
    provider_bundle_hash: str


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def load_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalProviderError(f"Cannot read provider JSON {source.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FormalProviderError(f"Provider JSON must be an object: {source.name}")
    return payload


def validate_raw_doppler_backend_report(
    report: Mapping[str, Any],
    *,
    verified_raw_hashes: Mapping[str, str],
) -> dict[str, Any]:
    missing = [field for field in RAW_DOPPLER_REQUIRED_FIELDS if field not in report]
    if missing:
        raise FormalProviderError("Raw Doppler backend report missing fields: " + ",".join(missing))
    if report.get("schema_version") != "paper-rebuild-raw-doppler-backend-v1":
        raise FormalProviderError("Raw Doppler backend schema mismatch")
    if report.get("raw_doppler_backend_lineage_proven") is not True:
        raise FormalProviderError("BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN")

    backend_id = report.get("raw_doppler_backend_id")
    if not isinstance(backend_id, str) or not backend_id.strip():
        raise FormalProviderError("Raw Doppler backend id is empty")
    lowered = backend_id.casefold()
    if any(token in lowered for token in ("status", "nav_pvt", "receiver_velocity", "legacy")):
        raise FormalProviderError("Raw Doppler backend id describes a forbidden alias/fallback")

    source_files = report.get("raw_doppler_backend_source_files")
    source_hashes = report.get("raw_doppler_backend_source_hashes")
    if not isinstance(source_files, list) or not source_files or not isinstance(source_hashes, Mapping):
        raise FormalProviderError("Raw Doppler source file/hash mappings are incomplete")
    normalized_files = [str(value).replace("\\", "/") for value in source_files]
    if len(set(normalized_files)) != len(normalized_files):
        raise FormalProviderError("Raw Doppler source file list contains duplicates")
    if BY2_TRACE_RELATIVE_PATH in normalized_files:
        raise FormalProviderError("Trace entered Raw Doppler generation")
    if not any(Path(relative).name in RAW_OBSERVATION_SOURCE_NAMES for relative in normalized_files):
        raise FormalProviderError("Raw Doppler backend has no raw observation source")
    for relative in normalized_files:
        if relative not in BY2_RAW_RELATIVE_PATHS:
            raise FormalProviderError(f"Raw Doppler source is outside exact BY2 lock: {relative}")
        expected = verified_raw_hashes.get(relative)
        if not expected or source_hashes.get(relative) != expected:
            raise FormalProviderError(f"Raw Doppler source hash mismatch: {relative}")

    helper_sources = report.get("helper_source_files")
    helper_hashes = report.get("helper_source_hashes")
    if not isinstance(helper_sources, list) or not helper_sources or not isinstance(helper_hashes, Mapping):
        raise FormalProviderError("Raw Doppler helper source lineage is incomplete")
    for relative in helper_sources:
        value = str(relative).replace("\\", "/")
        if value.startswith("/") or ".." in Path(value).parts or not _is_sha256(helper_hashes.get(value)):
            raise FormalProviderError("Raw Doppler helper source must be tracked-relative and hashed")
    for field in (
        "helper_executable_hash",
        "obs_source_hash",
        "nav_source_hash",
        "conversion_config_hash",
        "convbin_executable_hash",
        "rebuilt_ubx_hash",
        "helper_source_hash",
        "selected_status_fields_sha256",
    ):
        if not _is_sha256(report.get(field)):
            raise FormalProviderError(f"Raw Doppler lineage hash is invalid: {field}")

    rtklib_sources = report.get("rtklib_source_files")
    rtklib_hashes = report.get("rtklib_source_hashes")
    if not isinstance(rtklib_sources, list) or not rtklib_sources or not isinstance(rtklib_hashes, Mapping):
        raise FormalProviderError("Pinned RTKLIB source file/hash lineage is incomplete")
    for relative in rtklib_sources:
        value = str(relative).replace("\\", "/")
        if value.startswith("/") or ".." in Path(value).parts or not _is_sha256(rtklib_hashes.get(value)):
            raise FormalProviderError("Pinned RTKLIB source path/hash is invalid")
    compiled_helper_sources = report.get("helper_compiled_rtklib_source_files")
    compiled_convbin_sources = report.get("convbin_compiled_source_files")
    if not isinstance(compiled_helper_sources, list) or not compiled_helper_sources:
        raise FormalProviderError("Exact RTKLIB helper compile-source list is missing")
    if not isinstance(compiled_convbin_sources, list) or not compiled_convbin_sources:
        raise FormalProviderError("Exact convbin compile-source list is missing")
    if not set(compiled_helper_sources).issubset(rtklib_hashes) or not set(compiled_convbin_sources).issubset(rtklib_hashes):
        raise FormalProviderError("Compiled RTKLIB source list is not hash-closed")
    if not isinstance(report.get("compiler_version"), str) or not report["compiler_version"].strip():
        raise FormalProviderError("Raw Doppler compiler identity is missing")
    if report.get("runtime_patch_applied") != []:
        raise FormalProviderError("Formal Raw Doppler helper may not use runtime source patches")
    if report.get("convbin_clean_build") is not True or report.get("convbin_preexisting_output_count") != 0:
        raise FormalProviderError("Formal convbin was not built from a clean pinned build root")

    if report.get("rtklib_source_mode") not in {"explicit_local_pinned_root", "clean_root_materialized_pinned"}:
        raise FormalProviderError("RTKLIB source mode permits unpinned discovery")
    if report.get("rtklib_remote") != PINNED_RTKLIB_REMOTE:
        raise FormalProviderError("RTKLIB remote is not the pinned official remote")
    if report.get("rtklib_commit") != PINNED_RTKLIB_COMMIT:
        raise FormalProviderError("RTKLIB commit mismatch")
    if report.get("rtklib_tracked_source_dirty") is not False:
        raise FormalProviderError("RTKLIB tracked source tree is dirty")
    if not isinstance(report.get("rtklib_untracked_build_outputs_present"), bool):
        raise FormalProviderError("RTKLIB untracked build-output state is not recorded")
    if report.get("external_ephemeris_downloaded") is not False:
        raise FormalProviderError("Unhashed external ephemeris is forbidden")
    if report.get("time_conversion_formula") != RAW_DOPPLER_TIME_CONVERSION:
        raise FormalProviderError("Raw Doppler time conversion formula mismatch")
    if report.get("time_conversion_inputs_source_backed") is not True:
        raise FormalProviderError("Raw Doppler time conversion inputs are not source-backed")
    if report.get("source_discovery_used") is not False:
        raise FormalProviderError("Raw Doppler helper used source discovery")
    if report.get("sat_count_semantics") != "distinct_satellites_with_nonzero_doppler_observation":
        raise FormalProviderError("Raw Doppler satellite count is not Doppler-observation-backed")
    approx_relative = report.get("approx_position_source_relative_path")
    if approx_relative not in normalized_files or report.get("approx_position_source_hash") != source_hashes.get(approx_relative):
        raise FormalProviderError("Raw Doppler approximate-position source lineage is incomplete")
    approx = report.get("approx_position_geodetic_deg_m")
    if not isinstance(approx, list) or len(approx) != 3:
        raise FormalProviderError("Raw Doppler approximate position is incomplete")
    try:
        approx_values = [float(value) for value in approx]
        selected_row = int(report.get("selected_status_row_number"))
        gps_week = int(report.get("gps_week"))
    except (TypeError, ValueError) as exc:
        raise FormalProviderError("Raw Doppler approximate-position/time identity is invalid") from exc
    if not all(math.isfinite(value) for value in approx_values) or selected_row < 2 or gps_week <= 0:
        raise FormalProviderError("Raw Doppler approximate-position/time identity is invalid")
    conversion = report.get("conversion_contract")
    if not isinstance(conversion, Mapping):
        raise FormalProviderError("Raw Doppler conversion contract is missing")
    canonical_conversion = json.dumps(dict(conversion), sort_keys=True, separators=(",", ":"))
    import hashlib
    if hashlib.sha256(canonical_conversion.encode("utf-8")).hexdigest() != report.get("conversion_config_hash"):
        raise FormalProviderError("Raw Doppler conversion contract hash mismatch")
    if conversion.get("approx_position_geodetic_deg_m") != approx or conversion.get("gps_week") != gps_week:
        raise FormalProviderError("Raw Doppler conversion contract omits position/time inputs")
    for field in (
        "first_epoch_fit_used",
        "rtklib_position_solution_used_as_solver_input",
        "nav_pvt_velocity_used_as_raw_doppler",
        "gnss_velocity_used_as_raw_doppler",
        "status_fallback_used",
        "legacy_provider_used",
    ):
        if report.get(field) is not False:
            raise FormalProviderError(f"Forbidden Raw Doppler backend field is not false: {field}")

    try:
        raw_epochs = int(report["raw_epoch_count"])
        valid = int(report["valid_epoch_count"])
        invalid = int(report["invalid_epoch_count"])
        sat_min = int(report["sat_count_min"])
        sat_median = float(report["sat_count_median"])
        sat_max = int(report["sat_count_max"])
    except (TypeError, ValueError) as exc:
        raise FormalProviderError("Raw Doppler epoch/satellite counts are invalid") from exc
    if raw_epochs <= 0 or valid <= 0 or invalid < 0 or valid + invalid != raw_epochs or not (0 < sat_min <= sat_median <= sat_max):
        raise FormalProviderError("Raw Doppler epoch/satellite counts fail the formal gate")
    if report.get("covariance_policy") != RAW_DOPPLER_COVARIANCE_POLICY:
        raise FormalProviderError("Raw Doppler covariance policy must conservatively isotropize ECEF std")
    retained = report.get("retained_backend_artifacts")
    expected_retained_roles = {
        "helper_executable",
        "helper_source",
        "convbin_executable",
        "rebuilt_ubx",
        "rinex_obs",
        "rinex_nav",
        "formal_raw_doppler_provider",
    }
    if not isinstance(retained, Mapping) or set(retained) != expected_retained_roles:
        raise FormalProviderError("Retained Raw Doppler backend artifact set is incomplete")
    for role, entry in retained.items():
        if not isinstance(entry, Mapping):
            raise FormalProviderError(f"Retained Raw Doppler artifact entry is invalid: {role}")
        relative = entry.get("relative_path")
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise FormalProviderError(f"Retained Raw Doppler artifact path is unsafe: {role}")
        if not _is_sha256(entry.get("sha256")):
            raise FormalProviderError(f"Retained Raw Doppler artifact hash is invalid: {role}")
    canonical_retained = json.dumps(dict(retained), sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical_retained.encode("utf-8")).hexdigest() != report.get(
        "retained_backend_bundle_hash"
    ):
        raise FormalProviderError("Retained Raw Doppler backend bundle hash mismatch")
    top_level_cross_map = {
        "helper_executable_hash": "helper_executable",
        "helper_source_hash": "helper_source",
        "convbin_executable_hash": "convbin_executable",
        "rebuilt_ubx_hash": "rebuilt_ubx",
        "obs_source_hash": "rinex_obs",
        "nav_source_hash": "rinex_nav",
    }
    for field, role in top_level_cross_map.items():
        if report.get(field) != retained[role].get("sha256"):
            raise FormalProviderError(
                f"Raw Doppler top-level/retained artifact hash mismatch: {field}"
            )
    return dict(report)


def _assert_code_commit_relation(
    code_root: Path,
    *,
    generator_commit: str,
    current_commit: str,
    allow_report_only_descendant: bool,
) -> None:
    """Permit only the explicitly authorized docs-only report successor."""

    if current_commit == generator_commit:
        return
    if not allow_report_only_descendant:
        raise FormalProviderError("Formal provider does not match the clean committed worktree")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", generator_commit, current_commit],
        cwd=code_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if ancestor.returncode != 0:
        raise FormalProviderError("Provider generator commit is not an ancestor of report HEAD")
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{generator_commit}..{current_commit}"],
        cwd=code_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.splitlines()
    if not changed or not set(changed).issubset(REPORT_ONLY_DESCENDANT_PATHS):
        raise FormalProviderError(
            "Post-execution commits are not confined to the report-doc allowlist"
        )


def validate_formal_provider_manifest(
    paths: CleanPaths,
    manifest: Mapping[str, Any],
    *,
    allow_report_only_descendant: bool = False,
) -> FormalProviderBundle:
    if manifest.get("schema_version") != "paper-rebuild-clean1-input-v1":
        raise FormalProviderError("Formal provider manifest schema mismatch")
    if manifest.get("data_mode") != "real_by2_raw":
        raise FormalProviderError("Formal provider data mode mismatch")
    identity_by_suffix = {
        "CLEAN1_BY2_CLEAN_NORMAL_V1": (
            "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
            "CLEAN1_BY2_CLEAN_NORMAL_V1",
        ),
        "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED": (
            "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION",
            "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED",
        ),
    }
    protocol_suffix = _provider_protocol_suffix(paths.provider_root)
    expected_identity = identity_by_suffix.get(protocol_suffix)
    declared_identity = (manifest.get("stage_id"), manifest.get("protocol_id"))
    v1_legacy_manifest = (
        protocol_suffix == "CLEAN1_BY2_CLEAN_NORMAL_V1"
        and declared_identity == (None, None)
    )
    if expected_identity is None or (
        not v1_legacy_manifest and declared_identity != expected_identity
    ):
        raise FormalProviderError("Formal provider stage/protocol identity mismatch")
    is_v2 = protocol_suffix == "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"
    required_roles = (
        V2_REQUIRED_FORMAL_PROVIDER_ROLES
        if is_v2
        else V1_REQUIRED_FORMAL_PROVIDER_ROLES
    )
    maintained_files = (
        V2_MAINTAINED_SHARED_SOURCE_FILES
        if is_v2
        else V1_MAINTAINED_SHARED_SOURCE_FILES
    )
    for field in (
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
        "legacy_provider_used",
    ):
        if manifest.get(field) is not False:
            raise FormalProviderError(f"Formal provider forbidden flag is not false: {field}")
    for field in (
        "old_runtime_input_count",
        "legacy_provider_input_count",
        "legacy_row_input_count",
        "legacy_aggregate_input_count",
    ):
        if manifest.get(field) != 0:
            raise FormalProviderError(f"Formal provider reports forbidden prior evidence: {field}")
    if manifest.get("generator_worktree_dirty") is not False:
        raise FormalProviderError("Formal provider generator worktree was dirty")
    maintained_hashes = manifest.get("maintained_shared_source_hashes")
    if not isinstance(maintained_hashes, Mapping) or set(maintained_hashes) != set(maintained_files):
        raise FormalProviderError("Maintained shared-source dependency set is incomplete")
    if manifest.get("maintained_shared_source_commit") != manifest.get("generator_code_commit"):
        raise FormalProviderError("Maintained shared-source commit differs from provider generator commit")
    for relative in maintained_files:
        source = paths.code_root / relative
        if not source.is_file() or maintained_hashes.get(relative) != sha256_file(source):
            raise FormalProviderError(f"Maintained shared-source hash mismatch: {relative}")

    root = guard_path(paths.provider_root, role="CLEAN1 formal provider root", allowed_root=paths.clean_root)
    raw_hashes = manifest.get("raw_source_hashes")
    if not isinstance(raw_hashes, Mapping) or set(raw_hashes) != set(BY2_RAW_RELATIVE_PATHS):
        raise FormalProviderError("Formal provider must retain the exact 22-file raw lock map")
    raw_roles = manifest.get("raw_source_roles")
    if not isinstance(raw_roles, Mapping) or set(raw_roles) != set(BY2_RAW_RELATIVE_PATHS):
        raise FormalProviderError("Formal provider raw-source role map is not the exact 22-file set")
    lock = read_hash_lock(paths.raw_hash_lock)
    by2_lock = {relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"}
    if set(by2_lock) != set(BY2_RAW_RELATIVE_PATHS):
        raise FormalProviderError("Formal provider raw lock no longer contains the exact BY2 set")
    locked_hashes = {relative: str(row.get("sha256") or "") for relative, row in by2_lock.items()}
    if dict(raw_hashes) != locked_hashes:
        raise FormalProviderError("Formal provider raw hashes do not match the exact BY2 lock")

    read_set = manifest.get("actual_source_read_set")
    if not isinstance(read_set, list):
        raise FormalProviderError("Formal provider actual source read set is missing")
    normalized_reads = validate_provider_source_read_set(read_set, locked_hashes)
    if tuple(entry["relative_path"] for entry in normalized_reads) != FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS:
        raise FormalProviderError("Formal provider actual source set/order differs from the four-file freeze")
    actual_roles = {entry["relative_path"]: entry["role"] for entry in normalized_reads}
    if actual_roles != FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES:
        raise FormalProviderError(
            "Formal provider actual source roles differ from the frozen lineage"
        )
    actual_relpaths = [entry["relative_path"] for entry in normalized_reads]
    actual_verified = verify_raw_sources(paths.raw_root, actual_relpaths, lock)
    if any(actual_verified.get(relative) != locked_hashes.get(relative) for relative in actual_relpaths):
        raise FormalProviderError("Formal provider actual source changed after generation")
    propagation = [entry for entry in normalized_reads if entry["role"] == "propagation_imu_source"]
    if len(propagation) != 1:
        raise FormalProviderError("Formal provider must identify exactly one Go2 propagation IMU source")

    raw_doppler = manifest.get("raw_doppler_backend")
    if not isinstance(raw_doppler, Mapping):
        raise FormalProviderError("Formal provider Raw Doppler backend report is missing")
    raw_doppler_report = validate_raw_doppler_backend_report(
        raw_doppler, verified_raw_hashes=locked_hashes
    )
    for role, entry in raw_doppler_report["retained_backend_artifacts"].items():
        candidate = guard_path(
            root / entry["relative_path"],
            role=f"retained Raw Doppler backend artifact {role}",
            allowed_root=root,
            must_exist=True,
            regular_file=True,
        )
        if sha256_file(candidate) != entry["sha256"]:
            raise FormalProviderError(f"Retained Raw Doppler backend artifact changed: {role}")
    for relative in raw_doppler_report["helper_source_files"]:
        if relative not in maintained_hashes and relative != "src/legsa_gins/paper_rebuild/formal_generation.py":
            raise FormalProviderError(f"Raw Doppler helper dependency is outside audited source set: {relative}")
        if raw_doppler_report["helper_source_hashes"].get(relative) != sha256_file(paths.code_root / relative):
            raise FormalProviderError(f"Raw Doppler helper source changed: {relative}")

    artifacts = manifest.get("artifacts")
    declared_hashes = manifest.get("provider_hashes")
    if not isinstance(artifacts, Mapping) or not isinstance(declared_hashes, Mapping):
        raise FormalProviderError("Formal provider artifacts/hash mappings are missing")
    _assert_exact_provider_artifact_roles(artifacts, required_roles)
    if set(declared_hashes) != set(required_roles):
        raise FormalProviderError("Formal provider hash role set mismatch")
    resolved: dict[str, Path] = {}
    relpaths: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for role in required_roles:
        entry = artifacts[role]
        relative = entry.get("relative_path") if isinstance(entry, Mapping) else entry
        expected_solver_input = role not in AUDIT_ONLY_PROVIDER_ROLES
        if not isinstance(entry, Mapping) or entry.get("solver_input") is not expected_solver_input:
            raise FormalProviderError(f"Formal provider solver-input role mismatch: {role}")
        expected_artifact_role = (
            "potential_formal_solver_input" if expected_solver_input else "audit_only_lineage"
        )
        if entry.get("artifact_role") != expected_artifact_role:
            raise FormalProviderError(f"Formal provider artifact role mismatch: {role}")
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise FormalProviderError(f"Formal provider relative path invalid: {role}")
        candidate = guard_path(
            root / relative,
            role=f"formal provider {role}",
            allowed_root=root,
            must_exist=True,
            regular_file=True,
        )
        actual = sha256_file(candidate)
        if declared_hashes.get(role) != actual:
            raise FormalProviderError(f"Formal provider hash mismatch: {role}")
        resolved[role] = candidate
        relpaths[role] = relative.replace("\\", "/")
        hashes[role] = actual
    if is_v2:
        kick = manifest.get("kick_alignment")
        if not isinstance(kick, Mapping):
            raise FormalProviderError("CLEAN1R1C kick-alignment manifest is missing")
        expected_kick_hashes = {
            "kick_alignment_contract_hash": hashes["kick_alignment_contract"],
            "kick_alignment_report_hash": hashes["kick_alignment_report"],
            "kick_diagnostic_hash": hashes["kick_event_diagnostic"],
            "maintained_candidate_derived_csv_hash": hashes[
                "kick_maintained_initial_segment"
            ],
            "common_start_contract_hash": hashes["common_start_time_contract"],
        }
        if any(kick.get(field) != digest for field, digest in expected_kick_hashes.items()):
            raise FormalProviderError("CLEAN1R1C kick artifact hash mismatch")
        for field in (
            "trace_used_for_alignment",
            "offset_search_performed",
            "method_specific_shift",
            "optional_streams_delay_start",
        ):
            if kick.get(field) is not False:
                raise FormalProviderError(f"CLEAN1R1C kick forbidden field is not false: {field}")
        if float(kick.get("fixed_event_alignment_offset", math.nan)) != 0.0:
            raise FormalProviderError("CLEAN1R1C kick offset is not the frozen zero mapping")
    if raw_doppler_report["retained_backend_artifacts"][
        "formal_raw_doppler_provider"
    ]["sha256"] != hashes["raw_doppler_provider"]:
        raise FormalProviderError(
            "Retained Raw Doppler provider hash differs from provider bundle"
        )

    commit = manifest.get("generator_code_commit")
    config_hash = manifest.get("generator_config_hash")
    local_hash = manifest.get("local_path_config_hash")
    if not isinstance(commit, str) or not commit or not _is_sha256(config_hash) or not _is_sha256(local_hash):
        raise FormalProviderError("Formal provider generator provenance is incomplete")
    current_commit, dirty = git_code_state(paths.code_root)
    if dirty:
        raise FormalProviderError("Formal provider does not match the clean committed worktree")
    _assert_code_commit_relation(
        paths.code_root,
        generator_commit=commit,
        current_commit=current_commit,
        allow_report_only_descendant=allow_report_only_descendant,
    )
    if sha256_file(paths.config_path) != local_hash:
        raise FormalProviderError("Formal provider local path config changed")
    bundle_hash = manifest.get("provider_bundle_hash")
    canonical = json.dumps(hashes, sort_keys=True, separators=(",", ":"))
    import hashlib

    computed_bundle_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if bundle_hash != computed_bundle_hash:
        raise FormalProviderError("Formal provider bundle hash mismatch")
    return FormalProviderBundle(
        root=root,
        artifacts=resolved,
        provider_relpaths=relpaths,
        provider_hashes=hashes,
        raw_source_hashes=locked_hashes,
        actual_source_read_set=tuple(normalized_reads),
        generator_code_commit=commit,
        generator_config_hash=config_hash,
        local_path_config_hash=local_hash,
        raw_doppler_report=raw_doppler_report,
        provider_bundle_hash=computed_bundle_hash,
    )


def load_formal_provider_bundle(
    paths: CleanPaths,
    *,
    allow_report_only_descendant: bool = False,
) -> FormalProviderBundle:
    manifest_path = guard_path(
        paths.provider_root / "CLEAN_INPUT_MANIFEST.json",
        role="CLEAN1 formal input manifest",
        allowed_root=paths.clean_root,
        must_exist=True,
        regular_file=True,
    )
    manifest = load_json_object(manifest_path)
    backend_path = guard_path(
        paths.provider_root / "RAW_DOPPLER_BACKEND_REPORT.json",
        role="CLEAN1 Raw Doppler backend report",
        allowed_root=paths.provider_root,
        must_exist=True,
        regular_file=True,
    )
    backend = load_json_object(backend_path)
    if backend != manifest.get("raw_doppler_backend"):
        raise FormalProviderError("Standalone and embedded Raw Doppler backend reports differ")
    if manifest.get("raw_doppler_backend_report_sha256") != sha256_file(backend_path):
        raise FormalProviderError("Standalone Raw Doppler backend report hash mismatch")
    return validate_formal_provider_manifest(
        paths,
        manifest,
        allow_report_only_descendant=allow_report_only_descendant,
    )
