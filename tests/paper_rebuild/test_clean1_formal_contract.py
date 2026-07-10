from __future__ import annotations

import csv
import hashlib
import inspect
import json
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.evaluator import (
    EvaluatorContractError,
    aggregate_row_level,
    aggregate_row_level_independent,
    build_row_level_errors,
    crosscheck_aggregates,
    freeze_evaluator_contract,
    load_frozen_evaluator,
    evaluate_formal_output,
    read_persisted_row_level,
    reference_yaw_enu_to_solver_ned_deg,
    wrap_signed_deg,
)
from legsa_gins.paper_rebuild.evidence import (
    BY2_BODY_RELATIVE_PATH,
    BY2_FIX_PREFIX,
    BY2_RAW_RELATIVE_PATHS,
    BY2_TRACE_RELATIVE_PATH,
    FAILED_CLEAN1_EXPECTED_RAW_READS,
    FAILED_CLEAN1_ATTEMPT_SPECS,
    FAILED_CLEAN1_GIT_METADATA_SCAN_PATHS,
    FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES,
    FAILED_CLEAN1_PARTIAL_STAGE_FILES,
    EvidenceContractError,
    RawAudit,
    assert_export_text_is_redacted,
    canonical_file_tree_digest,
    parse_strace_openat_paths,
    validate_provider_source_read_set,
    validate_failed_clean1_attempt_evidence,
    write_source_role_manifests,
    verify_by2_raw_22,
)
from legsa_gins.paper_rebuild import formal_generation
from legsa_gins.paper_rebuild import providers as clean_providers
from legsa_gins.paper_rebuild.formal_generation import (
    _reuse_generated_dual_yaw_artifact,
    _source_gps_time_contract,
    _upgrade_gnss_to_formal_18_columns,
    gpst_tow_to_clean_seconds_of_utc_day,
)
from legsa_gins.paper_rebuild.formal_manifest import (
    assert_formal_run_manifest,
    validate_formal_run_manifest,
)
from legsa_gins.paper_rebuild.formal_provider import (
    FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS,
    FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES,
    PINNED_RTKLIB_COMMIT,
    PINNED_RTKLIB_REMOTE,
    RAW_DOPPLER_COVARIANCE_POLICY,
    RAW_DOPPLER_TIME_CONVERSION,
    REQUIRED_FORMAL_PROVIDER_ROLES,
    FormalProviderError,
    _assert_exact_provider_artifact_roles,
    _assert_code_commit_relation,
    validate_raw_doppler_backend_report,
)
from legsa_gins.paper_rebuild.formal_runner import FormalFourMethodRunner
from legsa_gins.paper_rebuild.methods import (
    FORMAL_METHOD_ORDER,
    REQUIRED_COMMON_RUNTIME_FIELDS,
    FORBIDDEN_DEFAULT_FIELDS,
    audit_effective_config_differences,
    load_method_catalog,
)
from legsa_gins.paper_rebuild.protocol import (
    REQUIRED_WINDOW_STREAMS,
    compute_full_common_window,
    build_common_covariance_contract,
    coverage_from_timestamps,
    load_clean1_protocol,
)
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import ubx_checksum


ROOT = Path(__file__).resolve().parents[2]
DIGEST = "a" * 64
STABLE_FAILED_CLEAN1_COMMITS = tuple(
    commit
    for commit, specification in FAILED_CLEAN1_ATTEMPT_SPECS.items()
    if specification.get("failure_state") == "stable_exported_stage"
)


def _catalog():
    return load_method_catalog(ROOT / "configs" / "paper_rebuild" / "methods.yaml")


def _common_initialization() -> dict[str, object]:
    protocol = load_clean1_protocol(ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml")
    covariance = build_common_covariance_contract(protocol.payload["solver_common"])
    return {
        "position_geodetic_deg_m": [40.0, 116.0, 10.0],
        "velocity_ned_mps": [0.0, 0.0, 0.0],
        "roll_pitch_deg": [1.0, 2.0],
        "yaw_ned_deg": 90.0,
        "bias_scale_state": [0.0] * 12,
        "covariance_diagonal": covariance["covariance_diagonal_internal"],
        "covariance_contract": covariance,
        "position_velocity_source_role": "gnss_source_at_common_start",
        "roll_pitch_source_role": "go2_body_attitude_at_common_start",
        "yaw_source_role": "fixed_physical_dual_yaw_at_common_start",
        "trace_used": False,
        "method_specific": False,
        "common_initialization_dual_yaw_used": True,
    }


def test_methods_yaml_is_unique_ordered_source_and_extra_diff_fails() -> None:
    catalog = _catalog()
    assert tuple(catalog.payload["methods"]) == FORMAL_METHOD_ORDER
    configs = {}
    for method in FORMAL_METHOD_ORDER:
        config = {field: "same" for field in REQUIRED_COMMON_RUNTIME_FIELDS}
        config.update(catalog.features(method))
        config.update({field: False for field in FORBIDDEN_DEFAULT_FIELDS})
        config.update(
            {
                "algorithm_id": method,
                "method_role": catalog.method(method)["role"],
                "run_id": f"run-{method}",
                "run_label": f"run-{method}",
                "output_dir_alias": f"<RUNTIME_ROOT>/{method}",
                "enable_basic_dual_yaw_baseline": method == "basic_dual_yaw_EKF",
                "basic_dual_yaw_fixed_std_deg": (
                    1.5 if method == "basic_dual_yaw_EKF" else "NOT_METHOD_SPECIFIC"
                ),
            }
        )
        configs[method] = config
    assert audit_effective_config_differences(catalog, configs)["passed"] is True
    configs["LegSA_Paper_V1"]["unapproved_tuning"] = 1.0
    assert "unpermitted_method_difference:unapproved_tuning" in audit_effective_config_differences(catalog, configs)["issues"]
    configs["LegSA_Paper_V1"].pop("unapproved_tuning")
    configs["basic_dual_yaw_EKF"]["basic_dual_yaw_fixed_std_deg"] = 2.0
    assert "basic_dual_yaw_fixed_std_mismatch:basic_dual_yaw_EKF" in audit_effective_config_differences(catalog, configs)["issues"]


def test_methods_catalog_rejects_unknown_method_field(tmp_path: Path) -> None:
    text = (ROOT / "configs/paper_rebuild/methods.yaml").read_text(encoding="utf-8")
    text = text.replace("    claim_scope: baseline_only\n", "    unapproved_parameter: 1\n    claim_scope: baseline_only\n", 1)
    candidate = tmp_path / "methods.yaml"
    candidate.write_text(text, encoding="utf-8")
    with pytest.raises(Exception, match="Method fields differ"):
        load_method_catalog(candidate)


def test_full_common_window_is_not_smoke_truncated() -> None:
    protocol = load_clean1_protocol(ROOT / "configs" / "paper_rebuild" / "clean1_by2_clean_protocol.yaml")
    assert protocol.payload["window"]["smoke_truncation_seconds"] is None
    coverages = [
        coverage_from_timestamps(
            role,
            [float(index), float(index + 100)],
            source_alias="<PROVIDER_ROOT>",
            relative_path=f"providers/{role}.csv",
            source_sha256=DIGEST,
        )
        for index, role in enumerate(REQUIRED_WINDOW_STREAMS)
    ]
    window = compute_full_common_window(
        coverages,
        source_time_origin_seconds=1772755200.0,
        common_initialization=_common_initialization(),
    )
    assert window.t_start == 6.0
    assert window.t_end == 100.0
    assert window.duration_seconds == 94.0
    assert len(window.common_initialization["covariance_diagonal"]) == 21


def test_exact_by2_registry_has_22_and_trace_is_evaluator_only() -> None:
    assert len(BY2_RAW_RELATIVE_PATHS) == 22
    assert len(set(BY2_RAW_RELATIVE_PATHS)) == 22
    assert BY2_TRACE_RELATIVE_PATH in BY2_RAW_RELATIVE_PATHS
    assert sum(path.endswith(".bag") for path in BY2_RAW_RELATIVE_PATHS) == 1
    assert sum(path.endswith(".fpl") for path in BY2_RAW_RELATIVE_PATHS) == 1


def test_provider_registry_rejects_trace_and_non_go2_propagation_imu() -> None:
    raw = next(path for path in BY2_RAW_RELATIVE_PATHS if path.endswith("/gnss1-raw.csv"))
    entry = {
        "relative_path": raw,
        "role": "propagation_imu_source",
        "expected_sha256": DIGEST,
        "actual_sha256": DIGEST,
        "reader_component": "fixture",
        "reason": "negative fixture",
        "output_provider_lineage": "fixture",
    }
    with pytest.raises(EvidenceContractError, match="Only the Go2 body source"):
        validate_provider_source_read_set([entry], {raw: DIGEST})
    entry["relative_path"] = BY2_TRACE_RELATIVE_PATH
    with pytest.raises(EvidenceContractError):
        validate_provider_source_read_set([entry], {BY2_TRACE_RELATIVE_PATH: DIGEST})


def test_formal_provider_source_roles_pin_receiver_velocity_to_nav_pvt_raw() -> None:
    assert tuple(FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES) == FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS
    status = next(path for path in FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS if path.endswith("gnss1-status.csv"))
    raw = next(path for path in FORMAL_PROVIDER_ACTUAL_SOURCE_PATHS if path.endswith("gnss1-raw.csv"))
    assert "receiver_velocity" not in FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES[status]
    assert "receiver_velocity_nav_pvt" in FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES[raw]
    assert "rawx_sfrbx_raw_doppler_observation" in FORMAL_PROVIDER_ACTUAL_SOURCE_ROLES[raw]


def test_provider_artifact_json_object_uses_exact_set_not_serialized_order() -> None:
    sorted_mapping = {
        role: {"relative_path": role}
        for role in sorted(REQUIRED_FORMAL_PROVIDER_ROLES)
    }
    assert tuple(sorted_mapping) != REQUIRED_FORMAL_PROVIDER_ROLES
    _assert_exact_provider_artifact_roles(sorted_mapping)
    sorted_mapping.pop("raw_doppler_provider")
    with pytest.raises(FormalProviderError, match="role set mismatch"):
        _assert_exact_provider_artifact_roles(sorted_mapping)


def test_formal_dual_yaw_reuses_one_artifact_without_case_only_copy(
    tmp_path: Path,
) -> None:
    provider = tmp_path / "provider"
    source = provider / "providers/dual_yaw_provider.csv"
    source.parent.mkdir(parents=True)
    source.write_text("time,body_yaw_ned_deg\n0,90\n", encoding="utf-8")
    result = _reuse_generated_dual_yaw_artifact(
        provider,
        {"dual_yaw_provider": {"relative_path": "providers/dual_yaw_provider.csv"}},
    )
    assert result == {
        "relative_path": "providers/dual_yaw_provider.csv",
        "source_generated": True,
    }
    assert not (provider / "providers/DUAL_YAW_PROVIDER.csv").exists()


def test_report_only_descendant_commit_is_narrowly_allowed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "clean1-test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "CLEAN1 Test"], cwd=repo, check=True)
    (repo / "code.txt").write_text("freeze\n", encoding="utf-8")
    subprocess.run(["git", "add", "code.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "freeze"], cwd=repo, check=True)
    freeze = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    report = repo / "docs/paper_rebuild/CLEAN1_STATUS.md"
    report.parent.mkdir(parents=True)
    report.write_text("blocked\n", encoding="utf-8")
    subprocess.run(["git", "add", str(report.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "report"], cwd=repo, check=True)
    report_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    _assert_code_commit_relation(
        repo,
        generator_commit=freeze,
        current_commit=report_commit,
        allow_report_only_descendant=True,
    )
    with pytest.raises(FormalProviderError):
        _assert_code_commit_relation(
            repo,
            generator_commit=freeze,
            current_commit=report_commit,
            allow_report_only_descendant=False,
        )
    (repo / "code.txt").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "add", "code.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "forbidden"], cwd=repo, check=True)
    forbidden = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    with pytest.raises(FormalProviderError, match="report-doc allowlist"):
        _assert_code_commit_relation(
            repo,
            generator_commit=freeze,
            current_commit=forbidden,
            allow_report_only_descendant=True,
        )


def test_blocked_provider_attempt_can_emit_empty_actual_read_manifest(tmp_path: Path) -> None:
    audit = RawAudit(
        rows=(),
        summary={},
        verified_hashes={relative: DIGEST for relative in BY2_RAW_RELATIVE_PATHS},
    )
    with pytest.raises(EvidenceContractError, match="read set is empty"):
        write_source_role_manifests(tmp_path / "strict", audit, [])
    paths = write_source_role_manifests(
        tmp_path / "blocked",
        audit,
        [],
        allow_empty_actual_for_blocked_attempt=True,
    )
    assert paths["actual"].read_text(encoding="utf-8").count("\n") == 1


def test_post_raw_mismatch_returns_auditable_failed_rows(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    rows = []
    for relative in BY2_RAW_RELATIVE_PATHS:
        path = raw / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
        rows.append(
            {
                "relative_path": relative,
                "dataset": "BY2",
                "role": "fixture",
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    lock = tmp_path / "RAW_FILE_HASH_LOCK.csv"
    with lock.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest()
    (raw / BY2_RAW_RELATIVE_PATHS[0]).write_bytes(b"mutated")
    audit = verify_by2_raw_22(
        raw,
        lock,
        expected_lock_sha256=lock_hash,
        expected_full_rows=22,
        expected_by2_rows=22,
        audit_phase="post_generation",
        return_failed_file_audit=True,
    )
    assert audit.summary["passed"] is False
    assert audit.summary["mismatch"] == 1
    assert len(audit.rows) == 22


def _raw_doppler_report(source: str, status_source: str) -> dict[str, object]:
    conversion = {
        "approx_position_geodetic_deg_m": [40.0, 116.0, 10.0],
        "gps_week": 2408,
    }
    conversion_hash = hashlib.sha256(
        json.dumps(conversion, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    retained = {
        role: {"relative_path": f"raw_doppler_backend/{role}", "sha256": DIGEST}
        for role in (
            "helper_executable",
            "helper_source",
            "convbin_executable",
            "rebuilt_ubx",
            "rinex_obs",
            "rinex_nav",
            "formal_raw_doppler_provider",
        )
    }
    return {
        "schema_version": "paper-rebuild-raw-doppler-backend-v1",
        "raw_doppler_backend_lineage_proven": True,
        "raw_doppler_backend_id": "rtklib_b34_pntpos_estvel_fresh_gnss1_rawx_sfrbx",
        "raw_doppler_backend_source_files": [source, status_source],
        "raw_doppler_backend_source_hashes": {source: DIGEST, status_source: DIGEST},
        "helper_source_files": ["src/legsa_gins/paper_rebuild/formal_generation.py"],
        "helper_source_hashes": {"src/legsa_gins/paper_rebuild/formal_generation.py": DIGEST},
        "helper_executable_hash": DIGEST,
        "obs_source_hash": DIGEST,
        "nav_source_hash": DIGEST,
        "conversion_config_hash": conversion_hash,
        "conversion_contract": conversion,
        "raw_epoch_count": 1509,
        "valid_epoch_count": 1248,
        "invalid_epoch_count": 261,
        "sat_count_min": 5,
        "sat_count_median": 7,
        "sat_count_max": 8,
        "covariance_policy": RAW_DOPPLER_COVARIANCE_POLICY,
        "rtklib_source_mode": "explicit_local_pinned_root",
        "rtklib_remote": PINNED_RTKLIB_REMOTE,
        "rtklib_commit": PINNED_RTKLIB_COMMIT,
        "rtklib_tracked_source_dirty": False,
        "rtklib_untracked_build_outputs_present": True,
        "rtklib_source_files": ["src/pntpos.c"],
        "rtklib_source_hashes": {"src/pntpos.c": DIGEST},
        "helper_compiled_rtklib_source_files": ["src/pntpos.c"],
        "convbin_compiled_source_files": ["src/pntpos.c"],
        "convbin_executable_hash": DIGEST,
        "rebuilt_ubx_hash": DIGEST,
        "compiler_version": "gcc test fixture",
        "convbin_clean_build": True,
        "convbin_preexisting_output_count": 0,
        "retained_backend_artifacts": retained,
        "retained_backend_bundle_hash": hashlib.sha256(
            json.dumps(retained, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "runtime_patch_applied": [],
        "external_ephemeris_downloaded": False,
        "time_conversion_formula": RAW_DOPPLER_TIME_CONVERSION,
        "time_conversion_inputs_source_backed": True,
        "approx_position_source_relative_path": status_source,
        "approx_position_source_hash": DIGEST,
        "approx_position_geodetic_deg_m": [40.0, 116.0, 10.0],
        "selected_status_row_number": 2,
        "selected_status_fields_sha256": DIGEST,
        "gps_week": 2408,
        "first_epoch_fit_used": False,
        "rtklib_position_solution_used_as_solver_input": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
        "status_fallback_used": False,
        "legacy_provider_used": False,
        "source_discovery_used": False,
        "sat_count_semantics": "distinct_satellites_with_nonzero_doppler_observation",
        "helper_source_hash": DIGEST,
    }


def test_raw_doppler_lineage_requires_pinned_no_fallback_and_fixed_time() -> None:
    source = next(path for path in BY2_RAW_RELATIVE_PATHS if path.endswith("/gnss1-raw.csv"))
    status = next(path for path in BY2_RAW_RELATIVE_PATHS if path.endswith("/gnss1-status.csv"))
    report = _raw_doppler_report(source, status)
    assert validate_raw_doppler_backend_report(
        report, verified_raw_hashes={source: DIGEST, status: DIGEST}
    )["valid_epoch_count"] == 1248
    report["status_fallback_used"] = True
    with pytest.raises(FormalProviderError, match="status_fallback_used"):
        validate_raw_doppler_backend_report(
            report, verified_raw_hashes={source: DIGEST, status: DIGEST}
        )
    report = _raw_doppler_report(source, status)
    report["helper_executable_hash"] = "b" * 64
    with pytest.raises(FormalProviderError, match="top-level/retained"):
        validate_raw_doppler_backend_report(
            report, verified_raw_hashes={source: DIGEST, status: DIGEST}
        )
    assert gpst_tow_to_clean_seconds_of_utc_day(
        460874.0,
        {"utc_year": 2026, "utc_month": 3, "utc_day": 6, "leap_seconds": 18},
    ) == 28856.0


def test_source_gps_leap_seconds_are_decoded_from_hash_locked_ubx(tmp_path: Path) -> None:
    payload = struct.pack("<IihbBI", 460874000, 0, 2408, 18, 7, 1)
    body = bytes([0x01, 0x20]) + len(payload).to_bytes(2, "little") + payload
    checksum = bytes(ubx_checksum(body))
    frame = b"\xb5\x62" + body + checksum
    source = tmp_path / "gnss1-raw.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "data"])
        writer.writeheader()
        writer.writerow({"name": "UBX-NAV-TIMEGPS", "data": repr(frame)})
    assert _source_gps_time_contract(source) == {"gps_week": 2408, "leap_seconds": 18}


def test_clean_source_aware_alias_executes_conservative_branch(tmp_path: Path) -> None:
    source = tmp_path / "source_aware_alias_test.cpp"
    source.write_text(
        r'''
#include "legsa_v23_port_core/source_aware/source_aware_policy.hpp"
#include <cmath>

int main() {
  using namespace legsa_v23_port_core::source_aware;
  SourceAwarePolicyConfig clean;
  clean.enable_source_aware_weighting = true;
  clean.source_aware_mode = "lsim_oim";
  clean.source_aware_policy_version = "clean_v1_conservative_innovation_covariance";
  clean.source_aware_method_family = "clean_v1_conservative_quadratic";
  SourceAwarePolicyConfig legacy = clean;
  legacy.source_aware_policy_version = "n6b_conservative_innovation_covariance";
  legacy.source_aware_method_family = "n6b_conservative_quadratic";
  SourceAwarePolicy clean_policy(clean);
  SourceAwarePolicy legacy_policy(legacy);
  if (clean_policy.branchId() != "conservative_innovation_covariance_v1") return 2;
  SourceMetadata metadata;
  metadata.source = MeasurementSource::kReceiverVelocity;
  ObservationInnovation innovation;
  innovation.normalized_innovation = 3.0;
  innovation.residual_norm = 3.0;
  innovation.base_R_trace = 1.0;
  innovation.hph_trace = 1.0;
  innovation.innovation_cov_trace = 2.0;
  innovation.used_innovation_covariance = true;
  const auto clean_result = clean_policy.evaluate(metadata, innovation);
  const auto legacy_result = legacy_policy.evaluate(metadata, innovation);
  if (std::fabs(clean_result.combined_R_scale - legacy_result.combined_R_scale) > 1.0e-12) return 3;
  return clean_result.combined_R_scale >= 1.0 ? 0 : 4;
}
''',
        encoding="utf-8",
    )
    executable = tmp_path / "source_aware_alias_test"
    compile_result = subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-I",
            str(ROOT / "cpp/legsa_v23_port_core/include"),
            str(source),
            str(ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp"),
            str(ROOT / "cpp/legsa_v23_port_core/src/common/types.cpp"),
            "-o",
            str(executable),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr
    assert subprocess.run([str(executable)], check=False).returncode == 0


def test_formal_gnss_validity_preserves_natural_dropouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "formal.gnss"
    target.write_text("\n".join(" ".join([str(t), *(["0"] * 14)]) for t in (0, 1, 2)) + "\n")
    monkeypatch.setattr(
        formal_generation,
        "extract_pvt_velocity_rows",
        lambda *args, **kwargs: [{"time": 0.0}, {"time": 2.0}],
    )
    monkeypatch.setattr(
        formal_generation,
        "build_a1_dual_diff_yaw_rows",
        lambda *args, **kwargs: ([{"aligned_time": 1.0}, {"aligned_time": 2.0}], {}),
    )
    report = _upgrade_gnss_to_formal_18_columns(
        target,
        gnss1_status=tmp_path / "g1.csv",
        gnss2_status=tmp_path / "g2.csv",
        gnss1_raw=tmp_path / "raw.csv",
        base_time=0.0,
        receiver_velocity_match_tolerance_seconds=0.1,
        dual_yaw_match_tolerance_seconds=0.6,
    )
    flags = [line.split()[-3:] for line in target.read_text().splitlines()]
    assert flags == [["1", "1", "0"], ["1", "0", "1"], ["1", "1", "1"]]
    assert report["receiver_velocity_dropout_count"] == 1
    assert report["dual_yaw_dropout_count"] == 1


def test_evaluator_freeze_uses_max_interval_and_blocks_unproven_reference_point(tmp_path: Path) -> None:
    trace = tmp_path / "trace.csv"
    with trace.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "lat", "lon", "height", "yaw", "pitch", "roll"])
        writer.writeheader()
        writer.writerows(
            [
                {"time": 100.0, "lat": 40, "lon": 116, "height": 10, "yaw": 0, "pitch": 0, "roll": 0},
                {"time": 100.005, "lat": 40, "lon": 116, "height": 10, "yaw": 0, "pitch": 0, "roll": 0},
                {"time": 100.112, "lat": 40, "lon": 116, "height": 10, "yaw": 0, "pitch": 0, "roll": 0},
            ]
        )
    trace_hash = hashlib.sha256(trace.read_bytes()).hexdigest()
    frozen = freeze_evaluator_contract(
        ROOT / "configs" / "paper_rebuild" / "evaluator_contract.yaml",
        trace,
        tmp_path / "freeze",
        reference_relative_path="BY2/trace.csv",
        expected_reference_sha256=trace_hash,
    )
    assert frozen.ready is False
    payload = load_frozen_evaluator(frozen.contract_path, require_ready=False)
    assert payload["reference"]["max_allowed_matching_gap_seconds"] == pytest.approx(0.11)
    with pytest.raises(EvaluatorContractError, match="BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED"):
        load_frozen_evaluator(frozen.contract_path, require_ready=True)
    assert reference_yaw_enu_to_solver_ned_deg(0.0) == 90.0
    assert payload["reference_attitude_frame_contract_proven"] is False


def test_evaluator_spoofed_ready_contracts_remain_blocked(tmp_path: Path) -> None:
    trace = tmp_path / "trace.csv"
    trace.write_text(
        "time,lat,lon,height,yaw,pitch,roll\n100,40,116,10,0,0,0\n100.1,40,116,10,0,0,0\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(trace.read_bytes()).hexdigest()
    point = {
        "reference_point_contract_proven": True,
        "source_backed": True,
        "solver_output_reference_point": "imu",
        "evaluation_reference_point": "reference",
        "transform_or_identity_contract": "identity:test",
        "source_hashes": {"BY2/fake.csv": DIGEST},
        "trace_fit_or_alignment_used": False,
    }
    frame = {
        "reference_attitude_frame_contract_proven": True,
        "source_backed": True,
        "reference_attitude_frame": "ENU",
        "solver_attitude_frame": "NED_FRD",
        "conversion_formula": "wrap(90_deg-reference_yaw_ENU_deg)",
        "source_hashes": {"BY2/fake.csv": DIGEST},
        "trace_fit_or_axis_selection_used": False,
    }
    with pytest.raises(EvaluatorContractError, match="proof injection is not authorized"):
        freeze_evaluator_contract(
            ROOT / "configs/paper_rebuild/evaluator_contract.yaml",
            trace,
            tmp_path / "freeze",
            reference_relative_path="BY2/trace.csv",
            expected_reference_sha256=digest,
            reference_point_contract=point,
            reference_frame_contract=frame,
            verified_source_hashes={"BY2/trace.csv": DIGEST},
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("  translation_alignment: false", "  translation_alignment: true"),
        ("  metric_driven_epoch_deletion: false", "  metric_driven_epoch_deletion: true"),
        ("  trace_based_time_offset_search: false", "  trace_based_time_offset_search: true"),
    ],
)
def test_evaluator_forbidden_contract_switch_fails(
    tmp_path: Path, old: str, new: str
) -> None:
    tracked = (ROOT / "configs/paper_rebuild/evaluator_contract.yaml").read_text(
        encoding="utf-8"
    )
    candidate = tmp_path / "evaluator.yaml"
    candidate.write_text(tracked.replace(old, new), encoding="utf-8")
    trace = tmp_path / "trace.csv"
    trace.write_text(
        "time,lat,lon,height,yaw,pitch,roll\n100,40,116,10,0,0,0\n100.1,40,116,10,0,0,0\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(trace.read_bytes()).hexdigest()
    with pytest.raises(EvaluatorContractError):
        freeze_evaluator_contract(
            candidate,
            trace,
            tmp_path / "freeze",
            reference_relative_path="BY2/trace.csv",
            expected_reference_sha256=digest,
        )


def test_persisted_row_level_is_reloaded_for_aggregate(tmp_path: Path) -> None:
    path = tmp_path / "ROW_LEVEL_ERRORS.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "matched",
                "horizontal_position_error_m",
                "vertical_error_m",
                "position_3d_error_m",
                "yaw_error_deg",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "matched": True,
                "horizontal_position_error_m": 1.0,
                "vertical_error_m": 2.0,
                "position_3d_error_m": 3.0,
                "yaw_error_deg": 4.0,
            }
        )
    rows = read_persisted_row_level(path)
    assert aggregate_row_level(rows) == aggregate_row_level_independent(
        read_persisted_row_level(path)
    )


def test_evaluator_output_hash_mutation_fails_without_artifacts(tmp_path: Path) -> None:
    solver = tmp_path / "EVAL_NAV.csv"
    solver.write_text("mutated\n", encoding="utf-8")
    reference = tmp_path / "trace.csv"
    reference.write_text("reference\n", encoding="utf-8")
    reference_hash = hashlib.sha256(reference.read_bytes()).hexdigest()
    evaluator = tmp_path / "EVALUATOR_CONTRACT.yaml"
    evaluator.write_text(
        json.dumps(
            {
                "schema_version": "paper-rebuild-frozen-evaluator-contract-v1",
                "method_output_read_during_freeze": False,
                "reference_point_contract_proven": True,
                "reference_attitude_frame_contract_proven": True,
                "formal_metrics_authorized": True,
                "reference": {"sha256": reference_hash},
            }
        ),
        encoding="utf-8",
    )
    window = tmp_path / "WINDOW_CONTRACT.yaml"
    window.write_text(
        json.dumps(
            {
                "schema_version": "paper-rebuild-window-contract-v1",
                "policy": "full_common_required_stream_interval",
                "smoke_truncation_applied": False,
                "trace_or_method_output_used_to_select_window": False,
                "t_start": 0.0,
                "t_end": 1.0,
                "common_initialization": _common_initialization(),
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "metrics"
    with pytest.raises(EvaluatorContractError, match="FINAL_OUTPUT_OR_METRIC"):
        evaluate_formal_output(
            solver,
            reference,
            window,
            evaluator,
            output,
            expected_output_sha256=DIGEST,
        )
    assert not output.exists()


def test_blocked_evaluator_entry_creates_no_artifact(tmp_path: Path) -> None:
    solver = tmp_path / "EVAL_NAV.csv"
    reference = tmp_path / "trace.csv"
    window = tmp_path / "WINDOW_CONTRACT.yaml"
    evaluator = tmp_path / "EVALUATOR_CONTRACT.yaml"
    for path in (solver, reference, window):
        path.write_text("fixture\n", encoding="utf-8")
    evaluator.write_text(
        json.dumps(
            {
                "schema_version": "paper-rebuild-frozen-evaluator-contract-v1",
                "method_output_read_during_freeze": False,
                "reference_point_contract_proven": False,
                "reference_attitude_frame_contract_proven": False,
                "formal_metrics_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "blocked-metrics"
    with pytest.raises(EvaluatorContractError, match="BLOCKED_CLEAN1_EVALUATOR"):
        evaluate_formal_output(
            solver,
            reference,
            window,
            evaluator,
            output,
            expected_output_sha256=DIGEST,
        )
    assert not output.exists()


def test_incomplete_four_method_set_creates_no_metrics(tmp_path: Path) -> None:
    from scripts.paper_rebuild.evaluate_clean1_by2 import main as evaluate_main

    raw = tmp_path / "raw"
    fix = raw / BY2_FIX_PREFIX
    clean = tmp_path / "clean"
    body = raw / BY2_BODY_RELATIVE_PATH
    for directory in (fix, body.parent, clean):
        directory.mkdir(parents=True)
    body.write_text("fixture", encoding="utf-8")
    provider = clean / "04_PROVIDER_FREEZE/CLEAN1_BY2_CLEAN_NORMAL_V1"
    runtime = clean / "05_BY2_CLEAN/CLEAN1_BY2_CLEAN_NORMAL_V1"
    config = tmp_path / "paths.local.yaml"
    config.write_text(
        json.dumps(
            {
                "paths": {
                    "code_root": str(ROOT),
                    "raw_root": str(raw),
                    "by2_fix_root": str(fix),
                    "by2_go2_body": str(body),
                    "clean_root": str(clean),
                    "provider_root": str(provider),
                    "runtime_root": str(runtime),
                }
            }
        ),
        encoding="utf-8",
    )
    protocol_dir = clean / "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION/02_PROTOCOL_FREEZE"
    protocol_dir.mkdir(parents=True)
    (protocol_dir / "WINDOW_CONTRACT.yaml").write_text("window", encoding="utf-8")
    (protocol_dir / "EVALUATOR_CONTRACT.yaml").write_text("evaluator", encoding="utf-8")
    with pytest.raises(RuntimeError, match="FOUR_METHOD_SET_INCOMPLETE"):
        evaluate_main(["--config", str(config)])
    evaluation = clean / "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION/07_EVALUATION"
    assert not evaluation.exists()


def test_evaluator_retains_unmatched_and_wraps_yaw() -> None:
    solver = [
        {"time": "0", "lat_deg": "40", "lon_deg": "116", "height_m": "10", "yaw_deg": "179"},
        {"time": "10", "lat_deg": "40", "lon_deg": "116", "height_m": "10", "yaw_deg": "0"},
    ]
    reference = [
        {"time": "100", "lat": "40", "lon": "116", "height": "10", "yaw": "-89"},
        {"time": "101", "lat": "40", "lon": "116", "height": "10", "yaw": "-89"},
    ]
    rows = build_row_level_errors(
        solver,
        reference,
        source_time_origin_seconds=100.0,
        max_gap_seconds=0.1,
    )
    assert rows[0]["matched"] is True
    assert rows[0]["yaw_error_deg"] == pytest.approx(0.0)
    assert rows[1]["matched"] is False
    assert len(rows) == 2
    assert wrap_signed_deg(181.0) == -179.0


def test_formal_runner_is_separate_and_evaluator_gate_creates_no_runtime(tmp_path: Path) -> None:
    from types import SimpleNamespace
    raw = tmp_path / "raw"
    fix = raw / "fix"
    clean = tmp_path / "clean"
    for path in (fix, clean):
        path.mkdir(parents=True)
    body = raw / "by2.txt"
    body.write_text("fixture", encoding="utf-8")
    config = tmp_path / "paths.local.yaml"
    runtime = clean / "runtime"
    config.write_text(
        json.dumps(
            {
                "paths": {
                    "code_root": str(ROOT),
                    "raw_root": str(raw),
                    "by2_fix_root": str(fix),
                    "by2_go2_body": str(body),
                    "clean_root": str(clean),
                    "provider_root": str(clean / "provider"),
                    "runtime_root": str(runtime),
                }
            }
        ),
        encoding="utf-8",
    )
    evaluator = tmp_path / "frozen_evaluator.json"
    evaluator.write_text(
        json.dumps(
            {
                "schema_version": "paper-rebuild-frozen-evaluator-contract-v1",
                "method_output_read_during_freeze": False,
                "reference_point_contract_proven": False,
                "reference_attitude_frame_contract_proven": False,
                "formal_metrics_authorized": False,
                "terminal_status": "BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED",
                "tracked_contract_sha256": hashlib.sha256(
                    (ROOT / "configs/paper_rebuild/evaluator_contract.yaml").read_bytes()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    evaluator.with_suffix(".sha256").write_text(
        f"{hashlib.sha256(evaluator.read_bytes()).hexdigest()}  {evaluator.name}\n",
        encoding="utf-8",
    )
    window = tmp_path / "window.json"
    window.write_text("{}", encoding="utf-8")
    runner = FormalFourMethodRunner(
        config,
        window_contract=window,
        evaluator_contract=evaluator,
        protocol_config=ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml",
        methods_config=ROOT / "configs/paper_rebuild/methods.yaml",
        attempt_ledger=clean / "attempts.csv",
    )
    with pytest.raises(Exception, match="BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED"):
        runner.run()
    assert not runtime.exists()
    assert "start + 10" not in (ROOT / "src/legsa_gins/paper_rebuild/formal_runner.py").read_text()
    child_source = (
        ROOT / "scripts/paper_rebuild/materialize_clean1_by2_provider.py"
    ).read_text(encoding="utf-8")
    formal_source = (
        ROOT / "src/legsa_gins/paper_rebuild/formal_generation.py"
    ).read_text(encoding="utf-8")
    parent_source = (
        ROOT / "scripts/paper_rebuild/generate_clean1_by2_inputs.py"
    ).read_text(encoding="utf-8")
    assert "git_code_state" not in child_source
    assert "load_formal_provider_bundle" not in child_source
    assert "git_code_state" not in formal_source
    assert '"--expected-code-commit"' in child_source
    assert "before_commit, before_dirty = git_code_state" in parent_source
    assert "after_commit, after_dirty = git_code_state" in parent_source
    assert "bundle = load_formal_provider_bundle(attempt_paths)" in parent_source
    assert (
        inspect.signature(clean_providers.generate_clean_by2_inputs)
        .parameters["expected_code_commit"]
        .default
        is None
    )
    assert (
        inspect.signature(formal_generation.generate_formal_clean1_inputs)
        .parameters["expected_code_commit"]
        .default
        is inspect.Parameter.empty
    )
    nonformal_paths = SimpleNamespace(
        clean_root=tmp_path / "formal-stage-guard",
        provider_root=tmp_path / "formal-stage-guard/provider",
        code_root=ROOT,
    )
    with pytest.raises(
        clean_providers.ProviderGenerationError,
        match="only valid for the CLEAN1 formal stage",
    ):
        clean_providers.generate_clean_by2_inputs(
            nonformal_paths,
            expected_code_commit="a" * 40,
            stage_id="PAPER10_CLEAN0",
        )


def test_export_leak_guard_rejects_local_absolute_paths() -> None:
    assert_export_text_is_redacted("alias=<RAW_ROOT>/BY2/source.csv")
    assert_export_text_is_redacted("schema=https://json-schema.org/draft/2020-12/schema")
    assert_export_text_is_redacted("fixed physical alternatives are +/-90 deg")
    assert_export_text_is_redacted(
        "relative=BY2_BY3/2026-03-06/高层数据/by2.txt"
    )
    with pytest.raises(EvidenceContractError, match="absolute_local_path"):
        absolute = str(Path("/") / "mnt" / "g" / "private" / "source.csv")
        assert_export_text_is_redacted(f"path={absolute}")
    with pytest.raises(EvidenceContractError, match="absolute_local_path"):
        assert_export_text_is_redacted("path=/mnt/g/中文/source.csv")


def test_strace_parser_resolves_utf8_octal_and_decoded_dirfd(tmp_path: Path) -> None:
    traced = tmp_path / "openat.trace"
    traced.write_text(
        'openat(AT_FDCWD, "/tmp/\\346\\265\\213\\350\\257\\225.csv", O_RDONLY) = 3\n'
        f'openat(3<{tmp_path}>, "relative.csv", O_RDONLY) = 4\n',
        encoding="utf-8",
    )
    opened = parse_strace_openat_paths(traced, cwd=ROOT)
    assert Path("/tmp/测试.csv") in opened
    assert (tmp_path / "relative.csv").resolve(strict=False) in opened
    filtered = parse_strace_openat_paths(
        traced, cwd=ROOT, required_substring='"/tmp/'
    )
    assert filtered == [Path("/tmp/测试.csv")]


def test_attempt_ledger_preserves_prior_sessions(tmp_path: Path) -> None:
    from scripts.paper_rebuild.run_clean1_by2_four_methods import (
        _completed_current_session_count,
    )
    code = tmp_path / "code"
    raw = tmp_path / "raw"
    fix = raw / "fix"
    clean = tmp_path / "clean"
    for path in (code, fix, clean):
        path.mkdir(parents=True)
    body = raw / "by2.txt"
    body.write_text("fixture", encoding="utf-8")
    config = tmp_path / "paths.local.yaml"
    config.write_text(
        json.dumps(
            {
                "paths": {
                    "code_root": str(code),
                    "raw_root": str(raw),
                    "by2_fix_root": str(fix),
                    "by2_go2_body": str(body),
                    "clean_root": str(clean),
                    "provider_root": str(clean / "provider"),
                    "runtime_root": str(clean / "runtime"),
                }
            }
        ),
        encoding="utf-8",
    )
    evaluator = tmp_path / "evaluator.json"
    evaluator.write_text("{}", encoding="utf-8")
    window = tmp_path / "window.json"
    window.write_text("{}", encoding="utf-8")
    ledger = clean / "attempts.csv"
    first = FormalFourMethodRunner(
        config,
        window_contract=window,
        evaluator_contract=evaluator,
        protocol_config=ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml",
        methods_config=ROOT / "configs/paper_rebuild/methods.yaml",
        attempt_ledger=ledger,
    )
    first._write_attempts(
        [
            {
                "attempt": 1,
                "algorithm_id": "single_antenna_EKF",
                "returncode": 0,
                "failure_class": "manifest_missing",
                "terminal_success": False,
                "metric_driven_rerun": False,
            }
        ]
    )
    second = FormalFourMethodRunner(
        config,
        window_contract=window,
        evaluator_contract=evaluator,
        protocol_config=ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml",
        methods_config=ROOT / "configs/paper_rebuild/methods.yaml",
        attempt_ledger=ledger,
    )
    second._write_attempts(
        [
            {
                "attempt": 1,
                "algorithm_id": "single_antenna_EKF",
                "returncode": 0,
                "failure_class": "",
                "terminal_success": True,
                "metric_driven_rerun": False,
            }
        ]
    )
    with ledger.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["terminal_success"] == "False"
    assert rows[1]["terminal_success"] == "True"
    assert rows[0]["session_id"] != rows[1]["session_id"]
    assert _completed_current_session_count(ledger, first.attempt_session_id) == 0
    assert _completed_current_session_count(ledger, second.attempt_session_id) == 1
    before = ledger.read_bytes()
    with pytest.raises(Exception, match="FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH"):
        second._write_attempts(
            [
                {
                    "attempt": 1,
                    "algorithm_id": "basic_dual_yaw_EKF",
                    "returncode": 0,
                    "failure_class": "",
                    "terminal_success": True,
                    "metric_driven_rerun": False,
                }
            ]
        )
    assert ledger.read_bytes() == before
    assert not list(ledger.parent.glob(f".{ledger.name}.tmp-*"))


def test_process_guard_terminates_whole_group_and_classifies_launch_failure(
    tmp_path: Path,
) -> None:
    child_pid = tmp_path / "child.pid"
    program = (
        "import pathlib,subprocess,sys,time;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid));"
        "time.sleep(60)"
    )
    started = time.monotonic()
    completed = run_process_group(
        [sys.executable, "-c", program, str(child_pid)],
        cwd=tmp_path,
        timeout_seconds=0.25,
        timeout_message="fixture timeout",
        launch_failure_message="fixture launch failure",
        termination_grace_seconds=0.25,
    )
    assert completed.returncode == 124
    assert "fixture timeout" in completed.stderr
    assert time.monotonic() - started < 5.0
    pid = int(child_pid.read_text(encoding="utf-8"))
    proc_stat = Path(f"/proc/{pid}/stat")
    deadline = time.monotonic() + 2.0
    while proc_stat.exists() and time.monotonic() < deadline:
        if proc_stat.read_text(encoding="utf-8").split()[2] == "Z":
            break
        time.sleep(0.02)
    assert not proc_stat.exists() or proc_stat.read_text(encoding="utf-8").split()[2] == "Z"

    launch = run_process_group(
        [str(tmp_path / "does-not-exist")],
        cwd=tmp_path,
        timeout_seconds=1,
        timeout_message="fixture timeout",
        launch_failure_message="fixture launch failure",
    )
    assert launch.returncode == 127
    assert "fixture launch failure" in launch.stderr


def test_stable_post_raw_blocker_promotes_evidence_but_not_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate

    repo = tmp_path / "repo"
    claim = repo / "docs/paper_rebuild/CLAIM_BOUNDARY.md"
    claim.parent.mkdir(parents=True)
    claim.write_text("No broad claim.\n", encoding="utf-8")
    monkeypatch.setattr(generate, "REPO_ROOT", repo)
    stage = tmp_path / ".stage-attempt"
    final = tmp_path / "stage-final"
    for relative in generate.EVIDENCE_SUBDIRS:
        (stage / relative).mkdir(parents=True, exist_ok=True)
    (stage / "00_AUTHORIZATION/AUTHORIZATION.md").write_text(
        "authorized\n", encoding="utf-8"
    )
    (stage / "01_GIT_FREEZE/GIT_STATE.json").write_text("{}\n", encoding="utf-8")
    (stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt").write_text(
        "1" * 40 + "\n", encoding="utf-8"
    )
    (stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json").write_text(
        '{"passed": false}\n', encoding="utf-8"
    )
    (stage / "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json").write_text(
        '{"raw_mutation": 1}\n', encoding="utf-8"
    )
    decision = generate._finalize_stable_blocked_stage(
        stage,
        final,
        terminal_status="BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED",
        code_commit="1" * 40,
        pre_verified=22,
        post_verified=21,
        raw_mutation_count=1,
        provider_attempt_generated=True,
        raw_doppler_backend_lineage_proven=True,
        blocked_component="post_generation_raw_hash_and_mutation_gate",
        claim_boundary="Raw integrity blocked.",
        narrative="Raw mutation detected; provider was not promoted.",
    )
    assert not stage.exists()
    assert final.is_dir()
    assert decision["provider_promoted"] is False
    assert decision["formal_run_count"] == 0
    assert (final / "10_EXPORT/CLEAN1_CONTEXT_FOR_GPT.zip").is_file()
    assert (final / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256").is_file()


def test_raw_blocker_derives_preserved_provider_attempt_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate

    stage = tmp_path / "stage"
    (stage / "04_PROVIDER_AUDIT").mkdir(parents=True)
    (stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json").write_text(
        '{"failed_attempt_preserved": true}\n', encoding="utf-8"
    )
    pre = SimpleNamespace(verified_hashes={str(index): DIGEST for index in range(22)})
    post = SimpleNamespace(verified_hashes={str(index): DIGEST for index in range(22)})
    monkeypatch.setattr(
        generate,
        "_write_post_raw_evidence",
        lambda *args, **kwargs: (post, {"passed": True, "raw_mutation": 0}),
    )
    captured: dict[str, object] = {}

    def capture(*args, **kwargs):
        captured.update(kwargs)
        return dict(kwargs)

    monkeypatch.setattr(generate, "_finalize_stable_blocked_stage", capture)
    generate._finalize_raw_doppler_blocked_stage(
        stage,
        tmp_path / "final",
        SimpleNamespace(raw_root=tmp_path / "raw"),
        object(),
        pre,
        "1" * 40,
    )
    assert captured["provider_attempt_generated"] is True


def _write_failed_attempt_fixture(
    tmp_path: Path,
    old_commit: str,
    *,
    prior_record: dict[str, object] | None = None,
):
    from legsa_gins.paper_rebuild.paths import CleanPaths
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate

    clean = tmp_path / "clean"
    raw = tmp_path / "raw"
    code = tmp_path / "code"
    code.mkdir(exist_ok=True)
    stage = clean / generate.STAGE_DIR_NAME
    for relative in (
        "08_EVIDENCE_AUDIT",
        "06_RUN_MANIFESTS",
        "03_DATA_HASH_AND_ROLES",
        "09_REPORT",
        "04_PROVIDER_AUDIT",
        "10_EXPORT",
    ):
        (stage / relative).mkdir(parents=True, exist_ok=True)
    for relative in FAILED_CLEAN1_EXPECTED_RAW_READS:
        source = raw / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("fixture\n", encoding="utf-8")
    provider_attempt = (
        clean
        / f"04_PROVIDER_FREEZE/.CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-{old_commit[:12]}"
    )
    for relative in (
        "RAW_DOPPLER_BACKEND_REPORT.json",
        "providers/RAW_DOPPLER_VELOCITY.csv",
        "providers/dual_yaw_provider.csv",
        "runtime_inputs/BY2_PROCESS_DATA_COMPAT.gnss",
        "runtime_inputs/BY2_PROCESS_DATA_COMPAT.imu",
    ):
        target = provider_attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture\n", encoding="utf-8")
    (provider_attempt / "CLEAN_INPUT_MANIFEST.json").write_text(
        json.dumps({"generator_code_commit": old_commit}) + "\n",
        encoding="utf-8",
    )
    terminal = "BLOCKED_CLEAN1_RAW_DOPPLER_BACKEND_LINEAGE_NOT_PROVEN"
    payloads = {
        "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json": {
            "code_freeze_commit": old_commit,
            "terminal_status": terminal,
            "formal_run_count": 0,
            "provider_promoted": False,
            "provider_attempt_generated": True,
            "raw_pre_verified": 22,
            "raw_post_verified": 22,
            "raw_mutation_count": 0,
        },
        "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json": {
            "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
            "formal_run_count": 0,
            "method_count_required": 4,
            "metric_driven_rerun": False,
            "terminal_status": terminal,
            "paper_performance_claim": False,
        },
        "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json": {
            "passed": True,
            "pre_verified": 22,
            "post_verified": 22,
            "raw_mutation": 0,
        },
        "09_REPORT/CLEAN1_FULL_REPORT.json": {
            "terminal_decision": terminal,
            "formal_run_count": 0,
            "metrics_generated": False,
            "paper_figure_count": 0,
        },
    }
    for relative, payload in payloads.items():
        (stage / relative).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    git_freeze = stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt"
    git_freeze.parent.mkdir(parents=True)
    git_freeze.write_text(old_commit + "\n", encoding="utf-8")
    if prior_record is not None:
        prior_path = stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json"
        prior_path.parent.mkdir(parents=True)
        prior_path.write_text(json.dumps(prior_record) + "\n", encoding="utf-8")
    trace = stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
    trace.write_text(
        "".join(
            f"openat(AT_FDCWD, {json.dumps(str(raw / relative), ensure_ascii=False)}, O_RDONLY) = 3\n"
            for relative in FAILED_CLEAN1_EXPECTED_RAW_READS
        ),
        encoding="utf-8",
    )
    trace_hash = hashlib.sha256(trace.read_bytes()).hexdigest()
    (stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json").write_text(
        json.dumps(
            {
                "terminal_status": terminal,
                "returncode": 1,
                "provider_final_root_created": False,
                "failed_attempt_preserved": True,
                "strace_available": True,
                "strace_sha256": trace_hash,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_ACTUAL_READ_AUDIT.json").write_text(
        json.dumps(
            {
                "strace_available": True,
                "observed_partial_failed_attempt_raw_reads": sorted(
                    FAILED_CLEAN1_EXPECTED_RAW_READS
                ),
                "unexpected_raw_reads": [],
                "promoted_provider_actual_read_set": [],
                "passed": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_STDERR.txt").write_text(
        " | ".join(FAILED_CLEAN1_ATTEMPT_SPECS[old_commit]["stderr_markers"])
        + "\n",
        encoding="utf-8",
    )
    report_source = stage / "09_REPORT/CLEAN1_FULL_REPORT.json"
    claim = b"No broad claim.\n"
    export_rows = [
        {
            "archive_path": "09_REPORT/CLEAN1_FULL_REPORT.json",
            "sha256": hashlib.sha256(report_source.read_bytes()).hexdigest(),
            "size_bytes": report_source.stat().st_size,
        },
        {
            "archive_path": "CLAIM_BOUNDARY.md",
            "sha256": hashlib.sha256(claim).hexdigest(),
            "size_bytes": len(claim),
        },
    ]
    export_manifest = stage / "10_EXPORT/EXPORT_SHA256_MANIFEST.csv"
    with export_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(export_rows[0]))
        writer.writeheader()
        writer.writerows(export_rows)
    with zipfile.ZipFile(
        stage / "10_EXPORT/CLEAN1_CONTEXT_FOR_GPT.zip",
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as handle:
        handle.write(report_source, "09_REPORT/CLEAN1_FULL_REPORT.json")
        handle.writestr("CLAIM_BOUNDARY.md", claim)
        handle.write(export_manifest, "EXPORT_SHA256_MANIFEST.csv")
    excluded = {
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv",
        "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256",
    }
    evidence_rows = []
    for source in sorted(path for path in stage.rglob("*") if path.is_file()):
        relative = source.relative_to(stage).as_posix()
        if relative in excluded:
            continue
        evidence_rows.append(
            {
                "relative_path": relative,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "size_bytes": source.stat().st_size,
                "tracked": False,
            }
        )
    evidence = stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.csv"
    with evidence.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0]))
        writer.writeheader()
        writer.writerows(evidence_rows)
    evidence_hash = hashlib.sha256(evidence.read_bytes()).hexdigest()
    (stage / "08_EVIDENCE_AUDIT/EVIDENCE_MANIFEST.sha256").write_text(
        f"{evidence_hash}  EVIDENCE_MANIFEST.csv\n", encoding="utf-8"
    )
    paths = CleanPaths(
        config_path=tmp_path / "paths.local.yaml",
        code_root=code,
        raw_root=raw,
        by2_fix_root=raw / "fix",
        by2_go2_body=raw / "by2.txt",
        clean_root=clean,
        provider_root=clean / "04_PROVIDER_FREEZE/CLEAN1_BY2_CLEAN_NORMAL_V1",
        runtime_root=clean / "05_BY2_CLEAN/CLEAN1_BY2_CLEAN_NORMAL_V1",
    )
    return paths, stage, provider_attempt


def _write_partial_failed_attempt_fixture(
    tmp_path: Path,
    *,
    prior_record: dict[str, object] | None = None,
):
    from legsa_gins.paper_rebuild.paths import CleanPaths
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate

    commit = "0aff9ea4c0b8103974591b060ea2b5627a6941ba"
    clean = tmp_path / "clean"
    raw = tmp_path / "raw"
    code = tmp_path / "code"
    code.mkdir(parents=True, exist_ok=True)
    raw_hashes: dict[str, str] = {}
    for index, relative in enumerate(BY2_RAW_RELATIVE_PATHS):
        source = raw / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"raw-{index}-{relative}\n".encode("utf-8"))
        raw_hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    raw_lock = clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv"
    raw_lock.parent.mkdir(parents=True, exist_ok=True)
    raw_lock.write_text("fixture lock\n", encoding="utf-8")

    stage = clean / (
        f".{generate.STAGE_DIR_NAME}.attempt-partial-fixture"
    )
    for relative in generate.EVIDENCE_SUBDIRS:
        (stage / relative).mkdir(parents=True, exist_ok=False)
    provider_attempt = (
        clean
        / "04_PROVIDER_FREEZE/.CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-partial-fixture"
    )
    artifact_paths = {
        "imu_runtime_input": "runtime_inputs/BY2_PROCESS_DATA_COMPAT.imu",
        "gnss_runtime_input": "runtime_inputs/BY2_PROCESS_DATA_COMPAT.gnss",
        "dual_yaw_provider": "providers/dual_yaw_provider.csv",
        "raw_doppler_provider": "providers/RAW_DOPPLER_VELOCITY.csv",
        "go2_attitude_prior": "providers/GO2_ATTITUDE_WEAK_PRIORS.csv",
        "go2_horizontal_velocity_prior": "providers/GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv",
        "source_quality_metadata": "providers/SOURCE_QUALITY_METADATA.csv",
    }
    provider_hashes: dict[str, str] = {}
    artifacts: dict[str, dict[str, object]] = {}
    for role, relative in artifact_paths.items():
        target = provider_attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{role}\n", encoding="utf-8")
        provider_hashes[role] = hashlib.sha256(target.read_bytes()).hexdigest()
        solver_input = role not in {"dual_yaw_provider", "source_quality_metadata"}
        artifacts[role] = {
            "relative_path": relative,
            "source_generated": True,
            "solver_input": solver_input,
            "artifact_role": (
                "potential_formal_solver_input"
                if solver_input
                else "audit_only_lineage"
            ),
        }
    retained_relative_paths = {
        "helper_executable": "raw_doppler_backend/helper/helper_executable",
        "helper_source": "raw_doppler_backend/helper/helper_source.c",
        "convbin_executable": "raw_doppler_backend/tools/convbin",
        "rebuilt_ubx": "raw_doppler_backend/gnss1_rebuilt.ubx",
        "rinex_obs": "raw_doppler_backend/rinex/gnss1.obs",
        "rinex_nav": "raw_doppler_backend/rinex/gnss1.nav",
        "formal_raw_doppler_provider": artifact_paths["raw_doppler_provider"],
    }
    retained: dict[str, dict[str, str]] = {}
    for role, relative in retained_relative_paths.items():
        target = provider_attempt / relative
        if role != "formal_raw_doppler_provider":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"retained-{role}\n", encoding="utf-8")
        retained[role] = {
            "relative_path": relative,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
    raw_observation = next(
        relative
        for relative in BY2_RAW_RELATIVE_PATHS
        if relative.endswith("/gnss1-raw.csv")
    )
    status_source = next(
        relative
        for relative in BY2_RAW_RELATIVE_PATHS
        if relative.endswith("/gnss1-status.csv")
    )
    backend = _raw_doppler_report(raw_observation, status_source)
    backend["raw_doppler_backend_source_hashes"] = {
        raw_observation: raw_hashes[raw_observation],
        status_source: raw_hashes[status_source],
    }
    backend["approx_position_source_hash"] = raw_hashes[status_source]
    backend["retained_backend_artifacts"] = retained
    backend["retained_backend_bundle_hash"] = hashlib.sha256(
        json.dumps(retained, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    backend["helper_executable_hash"] = retained["helper_executable"]["sha256"]
    backend["helper_source_hash"] = retained["helper_source"]["sha256"]
    backend["convbin_executable_hash"] = retained["convbin_executable"]["sha256"]
    backend["rebuilt_ubx_hash"] = retained["rebuilt_ubx"]["sha256"]
    backend["obs_source_hash"] = retained["rinex_obs"]["sha256"]
    backend["nav_source_hash"] = retained["rinex_nav"]["sha256"]
    backend_path = provider_attempt / "RAW_DOPPLER_BACKEND_REPORT.json"
    backend_path.write_text(json.dumps(backend) + "\n", encoding="utf-8")
    actual_reads = []
    for relative in FAILED_CLEAN1_EXPECTED_RAW_READS:
        role = (
            "propagation_imu_source"
            if relative == BY2_BODY_RELATIVE_PATH
            else "fixed_physical_dual_yaw_source"
            if relative.endswith("gnss2-status.csv")
            else "source_observation"
        )
        actual_reads.append(
            {
                "relative_path": relative,
                "role": role,
                "expected_sha256": raw_hashes[relative],
                "actual_sha256": raw_hashes[relative],
                "reader_component": "paper_rebuild.fixture",
                "reason": "strict partial-attempt fixture",
                "output_provider_lineage": "fixture provider",
            }
        )
    bundle_hash = hashlib.sha256(
        json.dumps(provider_hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest = {
        "schema_version": "paper-rebuild-clean1-input-v1",
        "generator_code_commit": commit,
        "generator_worktree_dirty": False,
        "raw_source_hashes": raw_hashes,
        "actual_source_read_set": actual_reads,
        "artifacts": artifacts,
        "provider_hashes": provider_hashes,
        "provider_bundle_hash": bundle_hash,
        "raw_doppler_backend": backend,
        "raw_doppler_backend_report_sha256": hashlib.sha256(
            backend_path.read_bytes()
        ).hexdigest(),
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0,
        "status_fallback_used": False,
        "legacy_provider_used": False,
    }
    (provider_attempt / "CLEAN_INPUT_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (provider_attempt / "PROVIDER_HASH_MANIFEST.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "provider_role",
                "relative_path",
                "sha256",
                "solver_input",
                "artifact_role",
            ],
        )
        writer.writeheader()
        for role in sorted(FAILED_CLEAN1_PARTIAL_PROVIDER_ROLES):
            writer.writerow(
                {
                    "provider_role": role,
                    "relative_path": artifacts[role]["relative_path"],
                    "sha256": provider_hashes[role],
                    "solver_input": artifacts[role]["solver_input"],
                    "artifact_role": artifacts[role]["artifact_role"],
                }
            )

    (stage / "00_AUTHORIZATION/AUTHORIZATION.md").write_text(
        "# Fixture authorization\n", encoding="utf-8"
    )
    (stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json").write_text(
        json.dumps(prior_record or {}) + "\n", encoding="utf-8"
    )
    (stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt").write_text(
        commit + "\n", encoding="utf-8"
    )
    (stage / "01_GIT_FREEZE/GIT_STATE.json").write_text(
        json.dumps({"code_freeze_commit": commit, "worktree_clean": True}) + "\n",
        encoding="utf-8",
    )
    (stage / "01_GIT_FREEZE/TRACKED_FILE_HASH_MANIFEST.csv").write_text(
        "relative_path,sha256,code_commit\n", encoding="utf-8"
    )
    (stage / "02_PROTOCOL_FREEZE/SCOPE_LOCK.yaml").write_text(
        "stage_id: CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION\n", encoding="utf-8"
    )
    raw_fields = [
        "audit_phase",
        "relative_path",
        "dataset",
        "lock_role",
        "expected_size_bytes",
        "expected_sha256",
        "exists",
        "regular_file",
        "realpath_confined",
        "actual_size_bytes",
        "actual_sha256",
        "status",
        "reason",
    ]
    for phase, name in (
        ("pre_generation", "BY2_RAW_22_PRE_HASH_AUDIT.csv"),
        ("post_generation", "BY2_RAW_22_POST_HASH_AUDIT.csv"),
    ):
        with (stage / "03_DATA_HASH_AND_ROLES" / name).open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=raw_fields)
            writer.writeheader()
            for relative in BY2_RAW_RELATIVE_PATHS:
                source = raw / relative
                writer.writerow(
                    {
                        "audit_phase": phase,
                        "relative_path": relative,
                        "dataset": "BY2",
                        "lock_role": "fixture",
                        "expected_size_bytes": source.stat().st_size,
                        "expected_sha256": raw_hashes[relative],
                        "exists": True,
                        "regular_file": True,
                        "realpath_confined": True,
                        "actual_size_bytes": source.stat().st_size,
                        "actual_sha256": raw_hashes[relative],
                        "status": "PASS",
                        "reason": "",
                    }
                )
    raw_summary = {
        "passed": True,
        "pre_verified": 22,
        "post_verified": 22,
        "raw_mutation": 0,
    }
    (stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json").write_text(
        json.dumps(raw_summary) + "\n", encoding="utf-8"
    )
    mutation = {
        "passed": True,
        "pre_verified": 22,
        "post_verified": 22,
        "raw_mutation": 0,
        "changed_relative_paths": [],
    }
    (stage / "03_DATA_HASH_AND_ROLES/RAW_MUTATION_AUDIT.json").write_text(
        json.dumps(mutation) + "\n", encoding="utf-8"
    )
    for name in (
        "BY2_RAW_22_ROLE_MANIFEST.csv",
        "CLEAN1_HARD_DENYLIST.csv",
        "EVALUATOR_ONLY_ALLOWLIST.csv",
        "HASH_VERIFIED_NOT_SOLVER_INPUT.csv",
    ):
        (stage / "03_DATA_HASH_AND_ROLES" / name).write_text(
            "fixture\n", encoding="utf-8"
        )
    (stage / "03_DATA_HASH_AND_ROLES/PROVIDER_SOLVER_SOURCE_ALLOWLIST.csv").write_text(
        "relative_path,role,expected_sha256,actual_sha256,reader_component,reason,output_provider_lineage\n",
        encoding="utf-8",
    )

    trace_lines = []
    for relative in FAILED_CLEAN1_EXPECTED_RAW_READS:
        trace_lines.append(
            f"100 openat(AT_FDCWD, {json.dumps(str(raw / relative), ensure_ascii=False)}, O_RDONLY) = 3\n"
        )
    for iteration in range(5):
        for relative in sorted(FAILED_CLEAN1_GIT_METADATA_SCAN_PATHS):
            trace_lines.append(
                f"{200 + iteration} openat(AT_FDCWD<{code}>, "
                f"{json.dumps(relative)}, O_RDONLY|O_DIRECTORY) = 5<{code / relative}>\n"
            )
    trace = stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_FILE_OPEN_TRACE.raw"
    trace.write_text("".join(trace_lines), encoding="utf-8")
    trace_hash = hashlib.sha256(trace.read_bytes()).hexdigest()
    crosscheck = {
        "schema_version": "paper-rebuild-provider-file-open-crosscheck-v1",
        "strace_sha256": trace_hash,
        "strace_available": True,
        "provider_process_isolated": True,
        "expected_raw_relative_paths": list(FAILED_CLEAN1_EXPECTED_RAW_READS),
        "observed_expected_raw_open_counts": {
            relative: 1 for relative in FAILED_CLEAN1_EXPECTED_RAW_READS
        },
        "missing_expected_raw_opens": [],
        "unexpected_raw_root_relative_paths": [],
        "unexpected_clean_root_relative_paths": [],
        "trace_opened_by_provider_process": False,
        "legacy_path_read_count": 45,
        "opened_path_count": 49,
        "passed": False,
    }
    (stage / "04_PROVIDER_AUDIT/PROVIDER_FILE_OPEN_CROSSCHECK.json").write_text(
        json.dumps(crosscheck, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    terminal = "FAIL_CLEAN1_EVIDENCE_CONTAMINATION"
    (stage / "04_PROVIDER_AUDIT/PROVIDER_ATTEMPT_BLOCKED.json").write_text(
        json.dumps(
            {
                "terminal_status": terminal,
                "provider_final_root_created": False,
                "failed_attempt_preserved": True,
                "file_open_crosscheck_passed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (stage / "04_PROVIDER_AUDIT/PROVIDER_FAILED_ACTUAL_READ_AUDIT.json").write_text(
        json.dumps(
            {
                "strace_available": True,
                "observed_partial_failed_attempt_raw_reads": sorted(
                    FAILED_CLEAN1_EXPECTED_RAW_READS
                ),
                "unexpected_raw_reads": [],
                "promoted_provider_actual_read_set": [],
                "passed": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    run_gate = {
        "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
        "formal_run_count": 0,
        "method_count_required": 4,
        "metric_driven_rerun": False,
        "terminal_status": terminal,
        "paper_performance_claim": False,
    }
    (stage / "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json").write_text(
        json.dumps(run_gate) + "\n", encoding="utf-8"
    )
    decision = {
        "code_freeze_commit": commit,
        "terminal_status": terminal,
        "formal_run_count": 0,
        "provider_promoted": False,
        "provider_attempt_generated": True,
        "raw_pre_verified": 22,
        "raw_post_verified": 22,
        "raw_mutation_count": 0,
    }
    (stage / "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json").write_text(
        json.dumps(decision) + "\n", encoding="utf-8"
    )
    report = {
        "code_freeze_commit": commit,
        "terminal_decision": terminal,
        "formal_run_count": 0,
        "metrics_generated": False,
        "paper_figure_count": 0,
        "provider_promoted": False,
    }
    (stage / "09_REPORT/CLEAN1_FULL_REPORT.json").write_text(
        json.dumps(report) + "\n", encoding="utf-8"
    )
    (stage / "09_REPORT/CLEAN1_FULL_REPORT.md").write_text(
        "# Partial technical failure\n", encoding="utf-8"
    )
    assert {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_file()
    } == FAILED_CLEAN1_PARTIAL_STAGE_FILES
    paths = CleanPaths(
        config_path=tmp_path / "paths.local.yaml",
        code_root=code,
        raw_root=raw,
        by2_fix_root=raw / "fix",
        by2_go2_body=raw / "by2.txt",
        clean_root=clean,
        provider_root=clean / "04_PROVIDER_FREEZE/CLEAN1_BY2_CLEAN_NORMAL_V1",
        runtime_root=clean / "05_BY2_CLEAN/CLEAN1_BY2_CLEAN_NORMAL_V1",
    )
    return paths, stage, provider_attempt


@pytest.mark.parametrize("failed_commit", STABLE_FAILED_CLEAN1_COMMITS)
def test_failed_attempt_validator_rehashes_full_stage_and_rejects_metrics(
    tmp_path: Path, failed_commit: str,
) -> None:
    paths, stage, provider_attempt = _write_failed_attempt_fixture(
        tmp_path, failed_commit
    )
    validated = validate_failed_clean1_attempt_evidence(
        stage,
        raw_root=paths.raw_root,
        code_root=paths.code_root,
        provider_attempt=provider_attempt,
        expected_code_commit=failed_commit,
    )
    assert validated["evidence_file_count"] > 0
    metric = stage / "07_EVALUATION/ROW_LEVEL_ERRORS.csv"
    metric.parent.mkdir()
    metric.write_text("forbidden\n", encoding="utf-8")
    with pytest.raises(EvidenceContractError):
        validate_failed_clean1_attempt_evidence(
            stage,
            raw_root=paths.raw_root,
            code_root=paths.code_root,
            provider_attempt=provider_attempt,
            expected_code_commit=failed_commit,
        )


def test_failed_attempt_validator_rejects_empty_required_provider_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate

    paths, stage, provider_attempt = _write_failed_attempt_fixture(
        tmp_path, generate.FAILED_ATTEMPT_CODE_FREEZE_COMMIT
    )
    (provider_attempt / "providers/RAW_DOPPLER_VELOCITY.csv").write_bytes(b"")
    with pytest.raises(EvidenceContractError, match="provider attempt is incomplete"):
        validate_failed_clean1_attempt_evidence(
            stage,
            raw_root=paths.raw_root,
            code_root=paths.code_root,
            provider_attempt=provider_attempt,
            expected_code_commit=generate.FAILED_ATTEMPT_CODE_FREEZE_COMMIT,
        )

    partial_paths, partial_stage, partial_provider = (
        _write_partial_failed_attempt_fixture(tmp_path / "partial")
    )
    partial_commit = "0aff9ea4c0b8103974591b060ea2b5627a6941ba"
    monkeypatch.setitem(
        FAILED_CLEAN1_ATTEMPT_SPECS[partial_commit],
        "expected_canonical_stage_tree_sha256",
        canonical_file_tree_digest(
            partial_stage, FAILED_CLEAN1_PARTIAL_STAGE_FILES
        ),
    )
    monkeypatch.setitem(
        FAILED_CLEAN1_ATTEMPT_SPECS[partial_commit],
        "expected_provider_manifest_sha256",
        hashlib.sha256(
            (partial_provider / "CLEAN_INPUT_MANIFEST.json").read_bytes()
        ).hexdigest(),
    )
    validated = validate_failed_clean1_attempt_evidence(
        partial_stage,
        raw_root=partial_paths.raw_root,
        code_root=partial_paths.code_root,
        provider_attempt=partial_provider,
        expected_code_commit=partial_commit,
    )
    assert validated["partial_stage_preserved"] is True
    assert validated["evidence_file_count"] == 23
    assert validated["export_member_count"] == 0
    assert len(validated["canonical_stage_tree_sha256"]) == 64

    manifest_path = partial_provider / "CLEAN_INPUT_MANIFEST.json"
    original_manifest = manifest_path.read_bytes()
    coordinated = json.loads(original_manifest)
    coordinated["otherwise_unchecked_field"] = "tampered"
    manifest_path.write_text(
        json.dumps(coordinated, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with pytest.raises(EvidenceContractError, match="provider manifest hash differs"):
        validate_failed_clean1_attempt_evidence(
            partial_stage,
            raw_root=partial_paths.raw_root,
            code_root=partial_paths.code_root,
            provider_attempt=partial_provider,
            expected_code_commit=partial_commit,
        )
    manifest_path.write_bytes(original_manifest)

    for unexpected_name in (
        "ROW_LEVEL_ERRORS.csv",
        "AGGREGATE_METRICS.json",
    ):
        unexpected = partial_provider / unexpected_name
        unexpected.write_text("forbidden\n", encoding="utf-8")
        with pytest.raises(
            EvidenceContractError, match="unexpected result evidence"
        ):
            validate_failed_clean1_attempt_evidence(
                partial_stage,
                raw_root=partial_paths.raw_root,
                code_root=partial_paths.code_root,
                provider_attempt=partial_provider,
                expected_code_commit=partial_commit,
            )
        unexpected.unlink()

    raw_relative = BY2_RAW_RELATIVE_PATHS[0]
    raw_source = partial_paths.raw_root / raw_relative
    original_raw = raw_source.read_bytes()
    same_content_target = partial_paths.raw_root / "same-content-target.bin"
    same_content_target.write_bytes(original_raw)
    raw_source.unlink()
    raw_source.symlink_to(same_content_target)
    with pytest.raises(EvidenceContractError, match="path chain contains a symlink"):
        validate_failed_clean1_attempt_evidence(
            partial_stage,
            raw_root=partial_paths.raw_root,
            code_root=partial_paths.code_root,
            provider_attempt=partial_provider,
            expected_code_commit=partial_commit,
        )
    raw_source.unlink()
    raw_source.write_bytes(original_raw)
    same_content_target.unlink()

    manifest = json.loads(
        (partial_provider / "CLEAN_INPUT_MANIFEST.json").read_text(encoding="utf-8")
    )
    retained = manifest["raw_doppler_backend"]["retained_backend_artifacts"]
    for retained_role in ("rinex_nav", "helper_executable"):
        retained_path = partial_provider / retained[retained_role]["relative_path"]
        original_retained = retained_path.read_bytes()
        retained_path.write_bytes(original_retained + b"tamper\n")
        with pytest.raises(
            EvidenceContractError, match="retained Raw Doppler artifact hash differs"
        ):
            validate_failed_clean1_attempt_evidence(
                partial_stage,
                raw_root=partial_paths.raw_root,
                code_root=partial_paths.code_root,
                provider_attempt=partial_provider,
                expected_code_commit=partial_commit,
            )
        retained_path.write_bytes(original_retained)

    artifact = partial_provider / "providers/RAW_DOPPLER_VELOCITY.csv"
    original = artifact.read_bytes()
    artifact.write_bytes(original + b"tamper\n")
    with pytest.raises(EvidenceContractError, match="artifact hash differs"):
        validate_failed_clean1_attempt_evidence(
            partial_stage,
            raw_root=partial_paths.raw_root,
            code_root=partial_paths.code_root,
            provider_attempt=partial_provider,
            expected_code_commit=partial_commit,
        )
    artifact.write_bytes(original)
    authorization = partial_stage / "00_AUTHORIZATION/AUTHORIZATION.md"
    original_authorization = authorization.read_bytes()
    authorization.write_bytes(original_authorization + b"tamper\n")
    with pytest.raises(EvidenceContractError, match="canonical stage tree differs"):
        validate_failed_clean1_attempt_evidence(
            partial_stage,
            raw_root=partial_paths.raw_root,
            code_root=partial_paths.code_root,
            provider_attempt=partial_provider,
            expected_code_commit=partial_commit,
        )
    authorization.write_bytes(original_authorization)
    extra = partial_stage / "07_EVALUATION/ROW_LEVEL_ERRORS.csv"
    extra.write_text("forbidden\n", encoding="utf-8")
    with pytest.raises(EvidenceContractError, match="exact tree differs"):
        validate_failed_clean1_attempt_evidence(
            partial_stage,
            raw_root=partial_paths.raw_root,
            code_root=partial_paths.code_root,
            provider_attempt=partial_provider,
            expected_code_commit=partial_commit,
        )
    extra.unlink()


def test_exact_raw_blocked_stage_is_archived_and_indexed_without_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate
    from scripts.paper_rebuild import audit_clean1_by2 as audit_script

    old_commit = generate.FAILED_ATTEMPT_CODE_FREEZE_COMMIT
    new_commit = "28ef36d5a9bac87bdeaed2e7567de7bbb9abd238"
    paths, stage, failed_provider_attempt = _write_failed_attempt_fixture(
        tmp_path, old_commit
    )
    monkeypatch.setattr(generate, "_git_first_parent", lambda *args: old_commit)
    monkeypatch.setattr(generate, "_git_commit_is_ancestor", lambda *args: True)
    record = generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
        paths, new_code_commit=new_commit
    )
    archive = paths.clean_root / generate.FAILED_ATTEMPT_DIR_NAME / old_commit
    assert not stage.exists()
    assert archive.is_dir()
    assert record["preserved_without_delete"] is True
    assert record["replacement_code_commit"] == new_commit
    new_stage = paths.clean_root / generate.STAGE_DIR_NAME
    (new_stage / "00_AUTHORIZATION").mkdir(parents=True)
    (new_stage / "01_GIT_FREEZE").mkdir()
    (new_stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt").write_text(
        new_commit + "\n", encoding="utf-8"
    )
    (new_stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    assert record["provider_attempt_alias"].endswith(failed_provider_attempt.name)
    monkeypatch.setattr(
        audit_script.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=f"{new_commit} {old_commit}\n"
        ),
    )
    assert audit_script._assert_prior_technical_attempt_record(new_stage, paths) == 1

    # A crash after the archive rename but before new-stage creation is idempotent.
    new_stage.rename(paths.clean_root / ".new-stage-not-final")
    recovered = generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
        paths, new_code_commit=new_commit
    )
    assert recovered["archive_recovered_after_interruption"] is True

    launch_commit = "b37e0ff1d38a750fb6e035f3b4da3f5b788fbdba"
    third_commit = "0aff9ea4c0b8103974591b060ea2b5627a6941ba"
    paths, second_stage, second_provider_attempt = _write_failed_attempt_fixture(
        tmp_path, new_commit, prior_record=record
    )
    monkeypatch.setattr(
        generate,
        "_git_first_parent",
        lambda _root, commit: (
            launch_commit if commit == third_commit else new_commit
        ),
    )

    def ancestry_result(command, **kwargs):
        commit = command[-1]
        parent = {
            new_commit: old_commit,
            launch_commit: new_commit,
            third_commit: launch_commit,
        }[commit]
        return SimpleNamespace(returncode=0, stdout=f"{commit} {parent}\n")

    monkeypatch.setattr(audit_script.subprocess, "run", ancestry_result)
    second_record = generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
        paths, new_code_commit=third_commit
    )
    assert second_record["inherited_prior_attempt_count"] == 1
    assert len(second_record["intervening_retry_launch_failures"]) == 1
    assert second_record["provider_attempt_alias"].endswith(
        second_provider_attempt.name
    )
    final_stage = paths.clean_root / generate.STAGE_DIR_NAME
    (final_stage / "00_AUTHORIZATION").mkdir(parents=True)
    (final_stage / "01_GIT_FREEZE").mkdir()
    (final_stage / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt").write_text(
        third_commit + "\n", encoding="utf-8"
    )
    (final_stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json").write_text(
        json.dumps(second_record), encoding="utf-8"
    )
    assert audit_script._assert_prior_technical_attempt_record(
        final_stage, paths
    ) == 2
    assert audit_script._count_prior_retry_launch_failures(
        final_stage, paths
    ) == 1

    # The next retry must preserve the exact partial hidden 0aff stage.  A
    # final provider/runtime/stage or a second hidden stage makes selection
    # ambiguous and fails before any rename.
    final_stage.rename(paths.clean_root / ".audit-only-not-final")
    partial_paths, partial_stage, partial_provider = (
        _write_partial_failed_attempt_fixture(tmp_path, prior_record=second_record)
    )
    monkeypatch.setitem(
        FAILED_CLEAN1_ATTEMPT_SPECS[third_commit],
        "expected_canonical_stage_tree_sha256",
        canonical_file_tree_digest(
            partial_stage, FAILED_CLEAN1_PARTIAL_STAGE_FILES
        ),
    )
    monkeypatch.setitem(
        FAILED_CLEAN1_ATTEMPT_SPECS[third_commit],
        "expected_provider_manifest_sha256",
        hashlib.sha256(
            (partial_provider / "CLEAN_INPUT_MANIFEST.json").read_bytes()
        ).hexdigest(),
    )
    fourth_commit = "4" * 40
    monkeypatch.setattr(
        generate,
        "_git_first_parent",
        lambda _root, commit: (
            third_commit
            if commit == fourth_commit
            else launch_commit
            if commit == third_commit
            else new_commit
        ),
    )
    partial_paths.runtime_root.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
            partial_paths, new_code_commit=fourth_commit
        )
    partial_paths.runtime_root.rmdir()
    partial_paths.provider_root.mkdir()
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
            partial_paths, new_code_commit=fourth_commit
        )
    partial_paths.provider_root.rmdir()
    ambiguous_final = partial_paths.clean_root / generate.STAGE_DIR_NAME
    ambiguous_final.mkdir()
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
            partial_paths, new_code_commit=fourth_commit
        )
    ambiguous_final.rmdir()
    extra_hidden = partial_paths.clean_root / (
        f".{generate.STAGE_DIR_NAME}.attempt-unexpected"
    )
    extra_hidden.mkdir()
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
            partial_paths, new_code_commit=fourth_commit
        )
    extra_hidden.rmdir()

    partial_record = generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
        partial_paths, new_code_commit=fourth_commit
    )
    partial_archive = (
        partial_paths.clean_root
        / generate.FAILED_ATTEMPT_DIR_NAME
        / third_commit
    )
    assert not partial_stage.exists()
    assert partial_archive.is_dir()
    assert partial_record["partial_stage_preserved"] is True
    assert partial_record["partial_finalization_reason"] == (
        "unicode_relative_path_export_redaction_false_positive"
    )
    assert partial_record["evidence_manifest_present"] is False
    assert partial_record["export_member_count"] == 0
    assert partial_record["evidence_file_count"] == 23
    assert len(partial_record["canonical_stage_tree_sha256"]) == 64
    assert partial_record["provider_attempt_alias"].endswith(partial_provider.name)
    recovered_partial = generate._preserve_exact_raw_doppler_blocked_stage_for_retry(
        partial_paths, new_code_commit=fourth_commit
    )
    assert recovered_partial["archive_recovered_after_interruption"] is True

    current = partial_paths.clean_root / generate.STAGE_DIR_NAME
    (current / "00_AUTHORIZATION").mkdir(parents=True)
    (current / "01_GIT_FREEZE").mkdir()
    (current / "01_GIT_FREEZE/CODE_FREEZE_COMMIT.txt").write_text(
        fourth_commit + "\n", encoding="utf-8"
    )
    (current / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json").write_text(
        json.dumps(partial_record), encoding="utf-8"
    )

    def full_ancestry_result(command, **kwargs):
        commit = command[-1]
        parent = {
            new_commit: old_commit,
            launch_commit: new_commit,
            third_commit: launch_commit,
            fourth_commit: third_commit,
        }[commit]
        return SimpleNamespace(returncode=0, stdout=f"{commit} {parent}\n")

    monkeypatch.setattr(audit_script.subprocess, "run", full_ancestry_result)
    assert audit_script._assert_prior_technical_attempt_record(
        current, partial_paths
    ) == 3
    assert audit_script._count_prior_retry_launch_failures(
        current, partial_paths
    ) == 1

    archive_backing = partial_archive.with_name(partial_archive.name + ".backing")
    partial_archive.rename(archive_backing)
    partial_archive.symlink_to(archive_backing, target_is_directory=True)
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        audit_script._assert_prior_technical_attempt_record(current, partial_paths)
    partial_archive.unlink()
    archive_backing.rename(partial_archive)

    provider_backing = partial_provider.with_name(partial_provider.name + ".backing")
    partial_provider.rename(provider_backing)
    partial_provider.symlink_to(provider_backing, target_is_directory=True)
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        audit_script._assert_prior_technical_attempt_record(current, partial_paths)
    partial_provider.unlink()
    provider_backing.rename(partial_provider)


def test_promotion_recovery_handles_hidden_stage_and_complete_marker_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from scripts.paper_rebuild import generate_clean1_by2_inputs as generate

    clean = tmp_path / "clean"
    provider_parent = clean / "04_PROVIDER_FREEZE"
    provider_parent.mkdir(parents=True)
    provider_final = provider_parent / "CLEAN1_BY2_CLEAN_NORMAL_V1"
    provider_attempt = provider_parent / ".CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-provider"
    provider_attempt.mkdir()
    stage_attempt = clean / (
        ".06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION.attempt-stage"
    )
    audit = stage_attempt / "08_EVIDENCE_AUDIT"
    audit.mkdir(parents=True)
    bundle_hash = "b" * 64
    (audit / "PROMOTION_JOURNAL.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-rebuild-clean1-promotion-journal-v1",
                "state": "STAGE_ATTEMPT_READY_PROVIDER_PENDING",
                "provider_attempt_root_name": provider_attempt.name,
                "provider_bundle_hash": bundle_hash,
                "provider_final_promoted": False,
                "stage_final_promoted": False,
                "delete_used": False,
            }
        ),
        encoding="utf-8",
    )
    (audit / "PRE_RUN_GATE_DECISION.json").write_text(
        json.dumps(
            {
                "provider_bundle_hash": bundle_hash,
                "formal_runs_authorized_by_all_gates": False,
            }
        ),
        encoding="utf-8",
    )
    from legsa_gins.paper_rebuild.paths import CleanPaths

    paths = CleanPaths(
        config_path=tmp_path / "paths.local.yaml",
        code_root=tmp_path / "code",
        raw_root=tmp_path / "raw",
        by2_fix_root=tmp_path / "raw/fix",
        by2_go2_body=tmp_path / "raw/by2.txt",
        clean_root=clean,
        provider_root=provider_final,
        runtime_root=clean / "05_BY2_CLEAN/CLEAN1_BY2_CLEAN_NORMAL_V1",
    )
    monkeypatch.setattr(
        generate,
        "load_formal_provider_bundle",
        lambda _paths: SimpleNamespace(provider_bundle_hash=bundle_hash),
    )
    decision = generate._recover_pending_promotion(paths)
    stage_final = clean / "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
    marker = stage_final / "08_EVIDENCE_AUDIT/PROMOTION_COMPLETE.json"
    assert decision["promotion_recovered_without_delete"] is True
    assert provider_final.is_dir()
    assert stage_final.is_dir()
    assert marker.is_file()
    marker.unlink()
    recovered_complete = generate._recover_pending_promotion(paths)
    assert recovered_complete["promotion_recovered_without_delete"] is True
    assert marker.is_file()
    with pytest.raises(RuntimeError, match="stage evidence root already exists"):
        generate._recover_pending_promotion(paths)


def test_final_audit_requires_exact_evaluator_and_runner_blocked_closure() -> None:
    from scripts.paper_rebuild.audit_clean1_by2 import (
        BLOCKED_STATUS,
        _assert_exact_blocked_gate_closure,
    )

    decision = {
        "terminal_status": BLOCKED_STATUS,
        "formal_runs_authorized_by_all_gates": False,
        "evaluator_ready": False,
        "paper_performance_claim": False,
    }
    evaluator = {
        "method_output_read_during_freeze": False,
        "reference_point_contract_proven": False,
        "reference_attitude_frame_contract_proven": False,
        "formal_metrics_authorized": False,
        "terminal_status": BLOCKED_STATUS,
    }
    run_blocked = {
        "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
        "formal_run_count": 0,
        "method_count_required": 4,
        "metric_driven_rerun": False,
        "terminal_status": BLOCKED_STATUS,
        "paper_performance_claim": False,
    }
    _assert_exact_blocked_gate_closure(decision, evaluator, run_blocked)
    tampered = dict(run_blocked)
    tampered.pop("formal_run_count")
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        _assert_exact_blocked_gate_closure(decision, evaluator, tampered)
    ready = dict(evaluator)
    ready["formal_metrics_authorized"] = True
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        _assert_exact_blocked_gate_closure(decision, ready, run_blocked)


def test_final_audit_requires_promotion_raw_and_full_window_closure(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace
    from scripts.paper_rebuild.audit_clean1_by2 import (
        _assert_exact_pre_run_gate_closure,
    )
    from scripts.paper_rebuild.generate_clean1_by2_inputs import (
        _build_success_pre_run_decision,
    )

    stage = tmp_path / "stage"
    protocol_dir = stage / "02_PROTOCOL_FREEZE"
    audit_dir = stage / "08_EVIDENCE_AUDIT"
    protocol_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)
    bundle_hash = "b" * 64
    relpaths = {
        "imu_runtime_input": "runtime_inputs/BY2.imu",
        "gnss_runtime_input": "runtime_inputs/BY2.gnss",
        "dual_yaw_provider": "providers/DUAL_YAW_PROVIDER.csv",
        "raw_doppler_provider": "providers/RAW_DOPPLER_PROVIDER.csv",
        "go2_attitude_prior": "providers/GO2_ATTITUDE.csv",
        "go2_horizontal_velocity_prior": "providers/GO2_VELOCITY.csv",
    }
    hashes = {role: hashlib.sha256(role.encode()).hexdigest() for role in relpaths}
    bundle = SimpleNamespace(
        provider_bundle_hash=bundle_hash,
        provider_relpaths=relpaths,
        provider_hashes=hashes,
    )
    attempt_name = ".CLEAN1_BY2_CLEAN_NORMAL_V1.attempt-fixture"
    journal = {
        "schema_version": "paper-rebuild-clean1-promotion-journal-v1",
        "state": "COMPLETE",
        "provider_attempt_root_name": attempt_name,
        "provider_bundle_hash": bundle_hash,
        "provider_final_promoted": True,
        "stage_final_promoted": True,
        "delete_used": False,
    }
    marker = {
        "state": "COMPLETE",
        "provider_bundle_hash": bundle_hash,
        "provider_final_promoted": True,
        "stage_final_promoted": True,
    }
    (audit_dir / "PROMOTION_JOURNAL.json").write_text(
        json.dumps(journal), encoding="utf-8"
    )
    marker_path = audit_dir / "PROMOTION_COMPLETE.json"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    window = {
        "schema_version": "paper-rebuild-window-contract-v1",
        "stage_id": "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        "case_id": "CLEAN1_BY2_CLEAN_NORMAL",
        "protocol_id": "CLEAN1_BY2_CLEAN_NORMAL_V1",
        "data_mode": "real_by2_raw",
        "policy": "full_common_required_stream_interval",
        "t_start_formula": "max(all_required_stream_first_valid_timestamps)",
        "t_end_formula": "min(all_required_stream_last_valid_timestamps)",
        "t_start": 10.0,
        "t_end": 20.0,
        "duration_seconds": 10.0,
        "source_time_origin_seconds": 0.0,
        "internal_dropout_preserved": True,
        "method_specific_window": False,
        "smoke_truncation_applied": False,
        "evaluation_burn_in_seconds": 0.0,
        "trace_or_method_output_used_to_select_window": False,
        "common_initialization": {},
    }
    window_path = protocol_dir / "WINDOW_CONTRACT.yaml"
    window_path.write_text(json.dumps(window), encoding="utf-8")
    (protocol_dir / "WINDOW_CONTRACT.sha256").write_text(
        f"{hashlib.sha256(window_path.read_bytes()).hexdigest()}  WINDOW_CONTRACT.yaml\n",
        encoding="utf-8",
    )
    evaluator_path = protocol_dir / "EVALUATOR_CONTRACT.yaml"
    evaluator_path.write_text("{}\n", encoding="utf-8")
    (protocol_dir / "EVALUATOR_CONTRACT.sha256").write_text(
        f"{hashlib.sha256(evaluator_path.read_bytes()).hexdigest()}  EVALUATOR_CONTRACT.yaml\n",
        encoding="utf-8",
    )
    role_to_artifact = {
        "propagation_imu": "imu_runtime_input",
        "gnss_position": "gnss_runtime_input",
        "receiver_velocity": "gnss_runtime_input",
        "dual_yaw": "dual_yaw_provider",
        "raw_doppler": "raw_doppler_provider",
        "go2_roll_pitch_prior": "go2_attitude_prior",
        "go2_horizontal_velocity_prior": "go2_horizontal_velocity_prior",
    }
    coverage = []
    for index, role in enumerate(REQUIRED_WINDOW_STREAMS):
        artifact = role_to_artifact[role]
        coverage.append(
            {
                "stream_role": role,
                "source_alias": "<PROVIDER_ROOT>",
                "relative_path": relpaths[artifact],
                "source_sha256": hashes[artifact],
                "first_valid_timestamp": 10.0 if index == 0 else 9.0,
                "last_valid_timestamp": 20.0 if index == 0 else 21.0,
                "valid_epoch_count": 2,
                "internal_dropout_preserved": True,
            }
        )
    with (protocol_dir / "WINDOW_SOURCE_COVERAGE.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage[0]))
        writer.writeheader()
        writer.writerows(coverage)
    raw_summary = {
        "expected": 22,
        "full_lock_rows": 9980,
        "by2_lock_rows": 22,
        "pre_verified": 22,
        "post_verified": 22,
        "mismatch": 0,
        "missing": 0,
        "symlink_escape": 0,
        "raw_mutation": 0,
        "passed": True,
    }
    mutation = {
        "schema_version": "paper-rebuild-by2-raw-mutation-audit-v1",
        "pre_verified": 22,
        "post_verified": 22,
        "raw_mutation": 0,
        "changed_relative_paths": [],
        "passed": True,
    }
    decision = _build_success_pre_run_decision(
        code_commit="1" * 40,
        raw_pre_verified=22,
        raw_post_verified=22,
        raw_mutation_count=0,
        raw_doppler_backend_lineage_proven=True,
        raw_doppler_valid_epoch_count=100,
        provider_bundle_hash=bundle_hash,
        window_summary={
            field: window[field]
            for field in (
                "t_start",
                "t_end",
                "duration_seconds",
                "source_time_origin_seconds",
                "common_initialization",
            )
        },
        evaluator_ready=False,
        evaluator_terminal_status="BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED",
    )
    assert decision["fresh_provider_generated"] is True
    assert "provider_promoted" not in decision
    backend = {"valid_epoch_count": 100}
    _assert_exact_pre_run_gate_closure(
        stage,
        decision=decision,
        raw_summary=raw_summary,
        mutation=mutation,
        window_contract=window,
        bundle=bundle,
        backend=backend,
    )
    raw_summary["post_verified"] = 21
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        _assert_exact_pre_run_gate_closure(
            stage,
            decision=decision,
            raw_summary=raw_summary,
            mutation=mutation,
            window_contract=window,
            bundle=bundle,
            backend=backend,
        )
    raw_summary["post_verified"] = 22
    marker_path.unlink()
    with pytest.raises(FileNotFoundError):
        _assert_exact_pre_run_gate_closure(
            stage,
            decision=decision,
            raw_summary=raw_summary,
            mutation=mutation,
            window_contract=window,
            bundle=bundle,
            backend=backend,
        )
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    pending = dict(journal)
    pending["state"] = "STAGE_PROMOTED_PROVIDER_PENDING"
    pending["provider_final_promoted"] = False
    (audit_dir / "PROMOTION_JOURNAL.json").write_text(
        json.dumps(pending), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        _assert_exact_pre_run_gate_closure(
            stage,
            decision=decision,
            raw_summary=raw_summary,
            mutation=mutation,
            window_contract=window,
            bundle=bundle,
            backend=backend,
        )


def test_row_aggregate_crosscheck_and_mismatch_gate() -> None:
    rows = []
    for index, value in enumerate((1.0, 2.0, 3.0)):
        rows.append(
            {
                "matched": True,
                "horizontal_position_error_m": value,
                "vertical_error_m": value / 2,
                "position_3d_error_m": value * 1.1,
                "yaw_error_deg": value * 2,
            }
        )
    primary = aggregate_row_level(rows)
    secondary = aggregate_row_level_independent(rows)
    assert crosscheck_aggregates(primary, secondary, absolute_tolerance=1e-12, relative_tolerance=1e-12)["passed"] is True
    secondary["metrics"]["yaw_error_deg"]["max"] += 1.0
    assert crosscheck_aggregates(primary, secondary, absolute_tolerance=1e-12, relative_tolerance=1e-12)["passed"] is False
    secondary = aggregate_row_level_independent(rows)
    secondary["coverage_ratio"] = 0.5
    result = crosscheck_aggregates(primary, secondary, absolute_tolerance=1e-12, relative_tolerance=1e-12)
    assert result["passed"] is False
    assert "coverage_ratio" in result["mismatches"]


def _formal_manifest(method: str) -> dict[str, object]:
    catalog = _catalog()
    counters = {field: 0 for field in (
        "position_update_count", "receiver_velocity_update_count", "dual_yaw_update_count",
        "raw_doppler_update_count", "source_aware_evaluation_count", "source_aware_weight_changed_count",
        "go2_roll_pitch_update_count", "go2_horizontal_velocity_update_count",
        "selected_fgo_feedback_update_count", "nine_factor_fgo_update_count", "qa_fallback_count",
        "multi_state_qm_update_count", "contact_fk_update_count",
    )}
    counters["position_update_count"] = 10
    counters["receiver_velocity_update_count"] = 8
    return {
        "schema_version": "paper-rebuild-formal-run-manifest-v1",
        "stage_id": "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        "protocol_id": "CLEAN1_BY2_CLEAN_NORMAL_V1",
        "case_id": "CLEAN1_BY2_CLEAN_NORMAL",
        "data_mode": "real_by2_raw",
        "run_id": "01_single_antenna_EKF",
        "algorithm_id": method,
        "method_role": catalog.method(method)["role"],
        "code_commit": "1" * 40,
        "code_worktree_dirty_at_run": False,
        "executable_hash": DIGEST,
        "runtime_config_hash": DIGEST,
        "methods_yaml_hash": DIGEST,
        "window_contract_hash": DIGEST,
        "evaluator_contract_hash": DIGEST,
        "raw_source_hashes": {relative: DIGEST for relative in BY2_RAW_RELATIVE_PATHS},
        "provider_hashes": {role: DIGEST for role in REQUIRED_FORMAL_PROVIDER_ROLES},
        "provider_generator_commit": "1" * 40,
        "provider_generation_config_hash": DIGEST,
        "local_path_config_hash": DIGEST,
        "actual_solver_input_paths": {
            "propagation_imu": "runtime_inputs/BY2.imu",
            "gnss_position_receiver_velocity_dual_yaw": "runtime_inputs/BY2.gnss",
        },
        "actual_solver_input_roles": [
            "propagation_imu",
            "gnss_position_receiver_velocity_dual_yaw",
        ],
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0,
        "status_fallback_used": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_yaw_truth_claim": False,
        "go2_contact_truth_claim": False,
        "common_initialization": True,
        "common_initialization_dual_yaw_used": True,
        "solver_returncode": 0,
        "runtime_seconds": 1.0,
        "module_update_counts": counters,
        "output_files": {"nav": "NAV.nav", "std": "STD.csv", "eval_nav": "EVAL_NAV.csv"},
        "output_hashes": {"nav": DIGEST, "std": DIGEST, "eval_nav": DIGEST},
        "terminal_status": "PASS",
        "paper_performance_claim": False,
    }


def test_formal_manifest_positive_and_counter_negative() -> None:
    catalog = _catalog()
    manifest = _formal_manifest("single_antenna_EKF")
    assert validate_formal_run_manifest(manifest, catalog) == []
    assert_formal_run_manifest(manifest, catalog)
    manifest["module_update_counts"]["dual_yaw_update_count"] = 1  # type: ignore[index]
    assert "forbidden_module_activated:dual_yaw_update_count" in validate_formal_run_manifest(manifest, catalog)


@pytest.mark.parametrize(
    "mutation",
    ("bad_hash", "too_few_raw_hashes", "extra_top_field", "extra_counter"),
)
def test_formal_manifest_schema_negative_keywords(mutation: str) -> None:
    catalog = _catalog()
    manifest = _formal_manifest("single_antenna_EKF")
    if mutation == "bad_hash":
        manifest["executable_hash"] = "not-a-hash"
    elif mutation == "too_few_raw_hashes":
        manifest["raw_source_hashes"] = {"only": DIGEST}
    elif mutation == "extra_top_field":
        manifest["unexpected"] = False
    else:
        manifest["module_update_counts"]["unexpected"] = 0  # type: ignore[index]
    with pytest.raises(Exception):
        assert_formal_run_manifest(manifest, catalog)
