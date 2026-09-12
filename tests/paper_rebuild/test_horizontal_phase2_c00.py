from __future__ import annotations

import csv
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import legsa_gins.paper_rebuild.horizontal_literature.phase2_runner as phase2
from legsa_gins.paper_rebuild.horizontal_literature.phase2_runner import (
    BASELINE_LENGTH_M,
    CASE_ID,
    DEFAULT_WORKERS,
    EXPECTED_PAIR_COUNT,
    MAX_WORKERS,
    METHOD_ID,
    NATIVE_FILE_NAMES,
    CompactCacheReader,
    Phase2Paths,
    PreflightResult,
    deterministic_shards,
    load_phase2_contract,
    validate_compact_cache,
    validate_native_freeze,
    validate_part,
    write_compact_cache,
)
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import RawxEpoch


ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "configs/paper_rebuild/horizontal_literature"


def _epoch(index: int) -> RawxEpoch:
    return RawxEpoch(100.0 + 0.2 * index, 2409, 18, 1, 1, ())


def _pairs(count: int):
    return [(_epoch(index), _epoch(index)) for index in range(count)]


def test_phase2_contract_locks_paper_math_units_oracle_and_outputs():
    contract = load_phase2_contract()
    assert contract["method_id"] == METHOD_ID and contract["case_id"] == CASE_ID
    assert contract["formal_reproduction_level"] == "FAITHFUL_ALGORITHM_REPRODUCTION"
    assert contract["paper_source"]["doi"] == "10.1109/TIM.2022.3193412"
    assert contract["algorithm"]["K_policy"] == "ALL_UNIQUE_CANDIDATES"
    assert contract["algorithm"]["candidate_deduplication"] == (
        "MACHINE_PRECISION_GEOMETRIC_DIRECTION_ONLY"
    )
    assert contract["algorithm"]["delta_Delta"] == 0.05
    assert contract["algorithm"]["round_half_down"] == "ceil(x-0.5)"
    assert contract["algorithm"]["wrap_interval_cycles"] == "(-0.5,0.5]"
    oracle = contract["algorithm"]["objective_oracle"]
    assert oracle["original_epoch_indices"] == list(range(0, EXPECTED_PAIR_COUNT, 150))
    assert oracle["grid_direction_count"] == 4096
    assert oracle["forbidden_dependency"] == "ALGORITHM1_CIRCLE_CANDIDATES"
    assert oracle["integer_rounding_implementation"] == "ORACLE_LOCAL_CEIL_X_MINUS_0P5"
    assert oracle["production_import_allowlist"] == ["solve_unit_sphere_quadratic"]
    units = contract["units_and_weights"]
    assert units["backend_DD_order_and_units"] == "[code_m,phase_m]"
    assert units["paper_CWLS_order_and_units"] == "[phase_cycles,code_cycles]"
    assert contract["observation_contract"]["phase_bias_calibration"] == "NONE"
    assert contract["runtime_topology"]["native_files"] == NATIVE_FILE_NAMES
    assert contract["parallel_execution"]["default_workers"] == DEFAULT_WORKERS
    assert contract["parallel_execution"]["maximum_workers"] == MAX_WORKERS
    atomic_backends = contract["parallel_execution"]["atomic_install_backends"]
    assert atomic_backends["primary"] == "LINUX_RENAMEAT2_RENAME_NOREPLACE"
    assert atomic_backends["drvfs_fallback"] == (
        "WINDOWS_DOTNET_FILE_OR_DIRECTORY_MOVE_NO_OVERWRITE"
    )
    assert atomic_backends["hardlink_fallback"] == "UNAVAILABLE_ON_TARGET_DRVFS_EPERM"
    csv_contract = contract["runtime_topology"]["native_csv_field_contract"]
    assert csv_contract["python_csv_decoded_character_limit"] == phase2.CSV_FIELD_SIZE_LIMIT
    assert phase2.CSV_FIELD_SIZE_LIMIT == 8 * 1024 * 1024
    assert csv_contract["measured_candidate_diagnostics_max_utf8_bytes"] == 429258
    assert csv_contract["measured_refinement_iterations_max_utf8_bytes"] == 402621
    trace_csv = contract["post_native_evaluator"]["trace_csv_contract"]
    assert trace_csv == {
        "observed_column_count": 10,
        "first_column": "time",
        "exact_columns": list(phase2.TRACE_CSV_COLUMNS),
        "timestamp_alias_accepted": False,
    }
    evaluator = contract["post_native_evaluator"]
    assert evaluator["gps_to_unix_seconds"] == (
        "315964800+gps_week*604800+gps_tow_seconds-leap_seconds"
    )
    assert evaluator["leap_seconds"] == {
        "expected_value": 18,
        "authority": "COMPACT_CACHE_PAIRED_EPOCHS_R1_R2_LEAP_FIELDS",
        "require_identical_all_receiver_epochs": True,
    }
    assert evaluator["trace_unwrap_domain"] == (
        "FULL_VALIDATED_MONOTONIC_TRACE_BEFORE_NATIVE_WINDOW_GATE"
    )
    assert evaluator["native_epoch_match_gate_seconds"] == [66.0, 340.0]
    assert evaluator["matched_native_time_must_be_bracketed_by_trace"] is True
    post_source = contract["post_native_evaluator"]["source_identity"]
    assert post_source["compact_cache_validation_fingerprint"] == (
        "NATIVE_SOURCE_FINGERPRINT"
    )
    assert post_source["post_only_source_fingerprint_divergence_allowed"] is True
    accounting = contract["post_native_evaluator"]["invocation_accounting"]
    assert accounting["manifest_count_scope"] == (
        "SUCCESSFUL_POST_NATIVE_INVOCATION_ONLY"
    )
    assert accounting["hpposecef_decode_pass_count_unit"] == "GNSS_RECEIVER_STREAM"
    assert accounting["successful_invocation_receiver_stream_decode_pass_count"] == 2
    assert accounting[
        "prior_failed_post_native_attempts_not_in_successful_invocation_counts"
    ] is True
    association = contract["post_native_evaluator"]["proxy_epoch_association"]
    assert association["candidate_grid"] == (
        "SORTED_INTERSECTION_OF_GNSS1_AND_GNSS2_HPPOSECEF_ITOW"
    )
    assert association["nearest_requirement"] == "UNIQUE_NEAREST_COMMON_EPOCH"
    assert association["midpoint_tie"] == "UNAVAILABLE"
    assert association["assignment_requirement"] == "STRICT_MONOTONIC_ONE_TO_ONE"
    assert association["trace_or_accuracy_used"] is False
    assert set(association["required_row_fields"]) <= set(phase2.PROXY_FIELDS)
    recovery = contract["post_native_evaluator"]["recovery_outputs"]
    assert recovery["safe_slug_regex"] == "[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
    assert recovery["collision_policy"] == "REFUSE_IF_ANY_RECOVERY_TARGET_EXISTS"
    assert recovery["primary_post_role"] == "HASHED_IMMUTABLE_INPUT_ONLY"
    shared_codes = {
        "INSUFFICIENT_PR_CP_VALID", "INSUFFICIENT_INTEGER_COMPATIBLE_PHASE",
        "INSUFFICIENT_ELEVATION_ELIGIBLE", "NORMAL_MATRIX_RANK_DEFICIENT",
    }
    assert shared_codes <= set(contract["failure_codes"])
    backend_source = inspect.getsource(phase2.build_gps_l1_double_difference_model)
    assert all(code in backend_source for code in shared_codes)


def test_independent_oracle_owns_round_half_down_and_imports_only_sphere_solver():
    values = phase2._oracle_round_half_down([-0.5, 0.5, 1.5, -1.5, 0.5000001])
    assert values.tolist() == [-1, 0, 1, -2, 1]
    source = inspect.getsource(phase2._oracle_refine)
    assert "from .ext02_cwls import solve_unit_sphere_quadratic" in source
    assert "import round_half_down" not in source


def test_standard_schema_additively_preserves_ext01_and_admits_ext02_labels():
    schema = yaml.safe_load(
        (CONFIG_ROOT / "STANDARD_HEADING_STREAM_SCHEMA_V1.yaml").read_text(encoding="utf-8")
    )
    fields = schema["fields"]
    assert fields["method_id"]["enum"] == ["EXT01_CLAMBDA", "EXT02_CWLS"]
    assert {"fixed", "float", "invalid"} <= set(fields["solution_type"]["enum"])
    assert "accepted_wrapped_solution" in fields["solution_state"]["enum"]
    for required in (
        "baseline_elevation_deg", "method_native_accepted",
        "recovered_integer_vector_present", "recovered_integer_vector",
        "ambiguity_satellite_identities", "wrapped_phase_rms_cycles",
        "pseudorange_residual_rms_m", "candidate_threshold_delta", "K_policy",
    ):
        assert required in fields


def test_compact_cache_is_fingerprinted_mmap_and_roundtrips_original_order(tmp_path):
    cache = tmp_path / "cache"
    write_compact_cache(cache, _pairs(5), source_fingerprint="a" * 64)
    manifest = validate_compact_cache(
        cache, source_fingerprint="a" * 64, expected_pair_count=5,
    )
    assert manifest["raw_csv_access_by_workers"] is False
    reader = CompactCacheReader(cache)
    assert len(reader) == 5
    assert [reader.pair(index)[0].gps_tow_seconds for index in range(5)] == [
        100.0 + 0.2 * index for index in range(5)
    ]
    assert reader.epochs.mode == "r"
    with pytest.raises(phase2.Phase2RunnerError, match="fingerprint"):
        validate_compact_cache(cache, source_fingerprint="b" * 64)


def test_deterministic_shards_conserve_all_1509_and_enforce_max20():
    shards = deterministic_shards(EXPECTED_PAIR_COUNT, DEFAULT_WORKERS)
    assert len(shards) == DEFAULT_WORKERS
    assert shards[0][1] == 0 and shards[-1][2] == EXPECTED_PAIR_COUNT
    indices = [index for _shard, start, stop in shards for index in range(start, stop)]
    assert indices == list(range(EXPECTED_PAIR_COUNT))
    with pytest.raises(phase2.Phase2RunnerError):
        deterministic_shards(1, MAX_WORKERS + 1)


def test_atomic_part_resume_validates_fingerprint_hash_order_and_conservation(tmp_path):
    records = [{"epoch_index": index, "value": index * 2} for index in range(3)]
    data = tmp_path / "part.jsonl"
    manifest = tmp_path / "part.manifest.json"
    phase2._write_part_atomic(
        data, manifest, records, source_fingerprint="f" * 64,
        shard_id=0, start=0, stop=3,
    )
    assert validate_part(
        data, manifest, source_fingerprint="f" * 64,
        shard_id=0, start=0, stop=3,
    ) == records
    original_data = data.read_bytes()
    original_manifest = manifest.read_bytes()
    with pytest.raises(phase2.Phase2RunnerError, match="target collision"):
        phase2._write_part_atomic(
            data, manifest, records, source_fingerprint="f" * 64,
            shard_id=0, start=0, stop=3,
        )
    assert data.read_bytes() == original_data
    assert manifest.read_bytes() == original_manifest
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["source_fingerprint"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(phase2.Phase2RunnerError, match="manifest mismatch"):
        validate_part(
            data, manifest, source_fingerprint="f" * 64,
            shard_id=0, start=0, stop=3,
        )


def test_atomic_writers_never_replace_existing_targets(tmp_path):
    byte_target = tmp_path / "evidence.bin"
    csv_target = tmp_path / "evidence.csv"
    npy_target = tmp_path / "evidence.npy"
    byte_target.write_bytes(b"frozen")
    csv_target.write_text("frozen\n", encoding="utf-8")
    npy_target.write_bytes(b"frozen-npy")
    with pytest.raises(phase2.Phase2RunnerError, match="target collision"):
        phase2._atomic_write_bytes(byte_target, b"replacement")
    with pytest.raises(phase2.Phase2RunnerError, match="target collision"):
        phase2._atomic_write_csv(csv_target, [{"x": 1}], ("x",))
    with pytest.raises(phase2.Phase2RunnerError, match="target collision"):
        phase2._atomic_save_npy(npy_target, phase2.np.asarray([1.0]))
    assert byte_target.read_bytes() == b"frozen"
    assert csv_target.read_text(encoding="utf-8") == "frozen\n"
    assert npy_target.read_bytes() == b"frozen-npy"


def test_csv_reader_roundtrips_large_field_and_restores_prior_global_limit(tmp_path):
    path = tmp_path / "large.csv"
    payload = "x" * (256 * 1024)
    phase2._atomic_write_csv(path, [{"epoch_index": 7, "payload": payload}], (
        "epoch_index", "payload",
    ))
    process_limit = csv.field_size_limit()
    custom_prior = 131_071
    csv.field_size_limit(custom_prior)
    try:
        rows = phase2._read_csv_rows(path)
        assert rows == [{"epoch_index": "7", "payload": payload}]
        assert csv.field_size_limit() == custom_prior
    finally:
        csv.field_size_limit(process_limit)


def test_csv_reader_rejects_field_above_frozen_limit_restores_and_chains_error(tmp_path):
    path = tmp_path / "oversized.csv"
    payload = "z" * (phase2.CSV_FIELD_SIZE_LIMIT + 1)
    phase2._atomic_write_csv(path, [{"payload": payload}], ("payload",))
    process_limit = csv.field_size_limit()
    custom_prior = 262_143
    csv.field_size_limit(custom_prior)
    try:
        with pytest.raises(phase2.Phase2RunnerError, match="CSV_PARSE_ERROR") as caught:
            phase2._read_csv_rows(path)
        assert isinstance(caught.value.__cause__, csv.Error)
        assert "field larger than field limit" in str(caught.value.__cause__)
        assert f"frozen_field_size_limit={phase2.CSV_FIELD_SIZE_LIMIT}" in str(caught.value)
        assert csv.field_size_limit() == custom_prior
    finally:
        csv.field_size_limit(process_limit)


def test_drvfs_windows_move_uses_encoded_quoted_paths_and_exact_transition(
        tmp_path, monkeypatch):
    source = tmp_path / "source.file"
    target = tmp_path / "target.file"
    source.write_bytes(b"payload")
    captured = {}
    monkeypatch.setattr(phase2, "_same_drvfs_mount", lambda *_args: {"filesystem_type": "9p"})
    monkeypatch.setattr(
        phase2, "_wsl_windows_path",
        lambda path: "G:\\O'Brien\\source.file" if path == source else "G:\\target.file",
    )
    monkeypatch.setattr(phase2.shutil, "which", lambda name: f"/fake/{name}")

    def windows_move(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        source.rename(target)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(phase2.subprocess, "run", windows_move)
    mode = phase2._windows_dotnet_move_noreplace(
        source, target, kind="file", label="test file",
    )
    assert mode == "WINDOWS_DOTNET_FILE_MOVE_NOREPLACE"
    encoded = captured["command"][captured["command"].index("-EncodedCommand") + 1]
    script = phase2.base64.b64decode(encoded).decode("utf-16le")
    assert "$source = 'G:\\O''Brien\\source.file'" in script
    assert "$target = 'G:\\target.file'" in script
    assert "[System.IO.File]::Move($source, $target)" in script
    assert "env" not in captured["kwargs"]
    assert not source.exists() and target.read_bytes() == b"payload"


def test_atomic_install_falls_back_only_after_unsupported_renameat2(
        tmp_path, monkeypatch):
    source = tmp_path / "source.file"
    target = tmp_path / "target.file"
    source.write_bytes(b"payload")

    class UnsupportedRename:
        argtypes = None
        restype = None

        def __call__(self, *_args):
            phase2.ctypes.set_errno(phase2.errno.EINVAL)
            return -1

    monkeypatch.setattr(
        phase2.ctypes, "CDLL",
        lambda *_args, **_kwargs: SimpleNamespace(renameat2=UnsupportedRename()),
    )

    def fallback(src, dst, *, kind, label):
        assert kind == "file" and label == "test file"
        src.rename(dst)
        return "WINDOWS_DOTNET_FILE_MOVE_NOREPLACE"

    monkeypatch.setattr(phase2, "_windows_dotnet_move_noreplace", fallback)
    assert phase2._atomic_install_noreplace(
        source, target, label="test file",
    ) == "WINDOWS_DOTNET_FILE_MOVE_NOREPLACE"
    assert not source.exists() and target.read_bytes() == b"payload"


def test_scientific_comparison_removes_only_runtime_process_fields():
    left = {
        "heading": {"epoch_index": 7, "body_yaw_deg": 12.5},
        "runtime": {
            "runtime_seconds": 0.1, "worker_pid": 101,
            "worker_max_rss_bytes": 1000, "shard_id": 0,
        },
    }
    right = json.loads(json.dumps(left))
    right["runtime"] = {
        "runtime_seconds": 1.2, "worker_pid": 202,
        "worker_max_rss_bytes": 2000, "shard_id": 9,
    }
    assert phase2._scientific_part(left) == phase2._scientific_part(right)
    right["heading"]["body_yaw_deg"] = 12.6
    assert phase2._scientific_part(left) != phase2._scientific_part(right)


def test_search_complete_requires_every_unique_candidate_converged_and_finite():
    good = SimpleNamespace(converged=True, failure_code=None, objective=1.0)
    failed = SimpleNamespace(converged=False, failure_code="SPHERE_SOLVER_FAILURE", objective=None)
    assert phase2._candidate_search_complete(
        SimpleNamespace(candidate_count=1, diagnostics=(good,))
    )
    assert not phase2._candidate_search_complete(
        SimpleNamespace(candidate_count=2, diagnostics=(good, failed))
    )
    assert not phase2._candidate_search_complete(
        SimpleNamespace(candidate_count=2, diagnostics=(good,))
    )


def test_rejected_search_preserves_candidate_pool_and_refinement_evidence():
    diagnostic = SimpleNamespace(
        coarse_index=0, coarse_direction=phase2.np.asarray([1.0, 0.0, 0.0]),
        coarse_objective=2.0, refined_direction=phase2.np.asarray([1.0, 0.0, 0.0]),
        objective=None, converged=False, integer_ambiguities=(1, -2),
        wrapped_phase_rms_cycles=None, wrapped_phase_max_abs_cycles=None,
        refined_unwrapped_objective=None, iteration_count=0,
        integer_vector_stable=False, unit_norm_error=None,
        convergence_state="SPHERE_SOLVER_FAILURE", failure_code="SPHERE_SOLVER_FAILURE",
        iterations=(),
    )
    pool = SimpleNamespace(
        phase_row_count=2, integer_option_count_per_row=(3, 4), circles=(1, 2, 3),
        pair_count=3, intersecting_pair_count=2, near_tangent_candidate_count=1,
        degenerate_pair_count=0, raw_candidate_count=5,
        directions=(phase2.np.asarray([1.0, 0.0, 0.0]),),
    )
    exc = RuntimeError("rejected pool")
    exc.candidate_diagnostics = (diagnostic,)
    exc.candidate_pool = pool
    candidates, refinements, counts = phase2._rejected_candidate_evidence(
        7, _epoch(7), exc,
    )
    assert refinements == []
    assert counts == {
        "raw_candidate_count": 5, "unique_candidate_count": 1,
        "refined_candidate_count": 0,
    }
    assert candidates[0]["phase_row_count"] == 2
    assert candidates[0]["integer_option_count_per_row"] == [3, 4]
    assert candidates[0]["failure_code"] == "SPHERE_SOLVER_FAILURE"
    invalid = phase2._invalid_record(
        7, _epoch(7), "SPHERE_SOLVER_FAILURE", "rejected pool", 0.1,
        candidate_rows=candidates, refinement_rows=refinements, candidate_counts=counts,
    )
    assert invalid["heading"]["search_complete"] is False
    assert invalid["heading"]["unique_candidate_count"] == 1
    assert len(invalid["candidates"]) == 1


def _fake_paths(tmp_path: Path) -> Phase2Paths:
    stage = tmp_path / "stage"
    report = stage / "11_REPORT"
    return Phase2Paths(
        config_path=tmp_path / "paths.yaml", code_root=ROOT,
        raw_root=tmp_path / "raw", by2_fix_root=tmp_path / "raw/by2",
        clean_root=tmp_path, raw_hash_lock=tmp_path / "lock.csv",
        gnss1_raw=tmp_path / "g1.csv", gnss2_raw=tmp_path / "g2.csv",
        trace=tmp_path / "trace.csv", rtklib_root=tmp_path / "rtklib",
        convbin=tmp_path / "convbin", rtklib_bridge=tmp_path / "bridge.so",
        bridge_root=tmp_path / "bridge", stage_root=stage,
        native_root=stage / "03_EXT02_CWLS/C00", report_root=report,
        final_report=report / phase2.REPORT_FILE_NAME,
        final_status=report / phase2.STATUS_FILE_NAME,
    )


def test_native_files_have_exact_1509_summary_rows_labels_and_freeze_gate(tmp_path):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    cache = attempt / "COMPACT_CACHE"
    cache_manifest = write_compact_cache(
        cache, _pairs(EXPECTED_PAIR_COUNT), source_fingerprint="c" * 64,
    )
    records = []
    for index in range(EXPECTED_PAIR_COUNT):
        epoch = _epoch(index)
        record = phase2._invalid_record(
            index, epoch, "NUMERICAL_FAILURE", "synthetic test failure", 0.01,
        )
        record["runtime"]["shard_id"] = index % DEFAULT_WORKERS
        records.append(record)
    paths = _fake_paths(tmp_path)
    preflight = PreflightResult(
        paths=paths, contract=load_phase2_contract(), config_hash="1" * 64,
        contract_hash="2" * 64, schema_hash="3" * 64,
        code_commit="4" * 40, raw_source_hashes={"raw": "5" * 64},
        provider_hashes={"provider": "6" * 64}, source_fingerprint="c" * 64,
    )
    summary = phase2.write_native_outputs(
        attempt, cache, records, preflight=preflight,
        cache_manifest=cache_manifest, provider_hashes=preflight.provider_hashes,
        determinism_probe={
            "status": "PASS", "workers_compared": DEFAULT_WORKERS,
            "actual_process_count": DEFAULT_WORKERS, "probe_worker_failure_count": 0,
        },
        workers=DEFAULT_WORKERS,
    )
    assert summary["paired_epoch_count"] == EXPECTED_PAIR_COUNT
    assert summary["success_row_count"] == 0
    assert summary["objective_oracle_evaluated_count"] == 0
    assert summary["objective_oracle_not_evaluated_count"] == len(phase2.ORACLE_INDICES)
    assert summary["objective_oracle_all_comparisons_pass"] is None
    assert summary["code_commit_role"] == "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY"
    assert summary["native_descriptive_statistics"]["candidate_search_completion"] == {
        "accepted_count": 0,
        "accepted_search_complete_count": 0,
        "all_accepted_search_complete": None,
        "rejected_incomplete_search_epoch_count": 0,
    }
    assert validate_native_freeze(attempt)["freeze_validated"] is True
    for logical in (
        "heading_results", "runtime", "dd_diagnostics", "candidate_diagnostics",
        "refinement_diagnostics", "objective_oracle_diagnostics", "tracking_diagnostics",
    ):
        with (attempt / NATIVE_FILE_NAMES[logical]).open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == EXPECTED_PAIR_COUNT
        assert [int(row["epoch_index"]) for row in rows] == list(range(EXPECTED_PAIR_COUNT))
    with (attempt / NATIVE_FILE_NAMES["candidate_diagnostics"]).open(
        newline="", encoding="utf-8",
    ) as stream:
        first = next(csv.DictReader(stream))
    assert first["phase_row_count"] == "0"
    assert json.loads(first["integer_option_count_per_row"]) == []
    assert first["unique_candidate_count"] == "0"
    for field in (
        "circle_count", "circle_pair_count", "intersecting_pair_count",
        "near_tangent_candidate_count", "raw_candidate_count",
        "degenerate_pair_count",
    ):
        assert first[field] == "0"
    assert first["search_complete"] == "false"
    native_hashes = {
        path.name: phase2._sha256_file(path)
        for path in attempt.iterdir() if path.name in NATIVE_FILE_NAMES.values()
    }
    with pytest.raises(phase2.Phase2RunnerError, match="native output target collision"):
        phase2.write_native_outputs(
            attempt, cache, records, preflight=preflight,
            cache_manifest=cache_manifest, provider_hashes=preflight.provider_hashes,
            determinism_probe={"status": "PASS"}, workers=DEFAULT_WORKERS,
        )
    assert native_hashes == {
        path.name: phase2._sha256_file(path)
        for path in attempt.iterdir() if path.name in NATIVE_FILE_NAMES.values()
    }
    final = tmp_path / "final"
    phase2._atomic_finalize_attempt(attempt, final)
    assert not attempt.exists()
    assert validate_native_freeze(final)["paired_epoch_count"] == EXPECTED_PAIR_COUNT


def test_cli_lists_all_lifecycle_modes_and_defaults_to_16():
    script = ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase2.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"], text=True,
        capture_output=True, check=False,
    )
    assert completed.returncode == 0 and completed.stderr == ""
    for mode in phase2.ALLOWED_MODES:
        assert mode in completed.stdout
    assert "--workers" in completed.stdout
    assert "--post-recovery-id" in completed.stdout


def test_resource_snapshot_and_cache_io_evidence_have_required_fields(tmp_path):
    cache = tmp_path / "cache"
    write_compact_cache(cache, _pairs(2), source_fingerprint="9" * 64)
    snapshot = phase2._system_resource_snapshot(tmp_path)
    assert {
        "ram_total_bytes", "ram_available_bytes", "swap_total_bytes",
        "swap_used_bytes", "swap_in_pages", "swap_out_pages", "cpu_count",
        "load_average_1m_5m_15m", "thermal", "configured_clean_storage",
    } <= snapshot.keys()
    assert snapshot["thermal"]["status"] in {"AVAILABLE", "UNAVAILABLE"}
    io_probe = phase2._measure_cache_read(cache)
    assert io_probe["bytes_read"] > 0
    assert io_probe["throughput_bytes_per_second"] > 0
    assert io_probe["worker_raw_csv_read_count"] == 0


def _resource_snapshot(*, ram=100_000, disk=10_000_000_000, swap_in=0, swap_out=0,
                       temperature=40.0):
    thermal = (
        {"status": "UNAVAILABLE", "zones": []}
        if temperature is None else {
            "status": "AVAILABLE",
            "zones": [{"zone": "thermal_zone0", "temperature_c": temperature}],
        }
    )
    return {
        "ram_available_bytes": ram,
        "swap_in_pages": swap_in, "swap_out_pages": swap_out,
        "configured_clean_storage": {"available_bytes": disk},
        "thermal": thermal,
    }


def _positive_io():
    return {"bytes_read": 100, "elapsed_seconds": 0.5, "throughput_bytes_per_second": 200.0}


def test_resource_admission_is_explicit_and_fail_closed_at_frozen_limits():
    before = _resource_snapshot(ram=100_000_000_000)
    after = _resource_snapshot(ram=90_000_000_000, temperature=42.0)
    admitted = phase2._resource_admission_evidence(
        workers=DEFAULT_WORKERS, before=before, after=after, cache_read=_positive_io(),
        peak_per_worker_rss_bytes=1_000_000_000,
        worker_failure_count=0, actual_process_count=DEFAULT_WORKERS,
    )
    assert admitted["admitted"] is True
    assert admitted["deterministic_output_size_projection"] == {
        "paired_epoch_count": EXPECTED_PAIR_COUNT,
        "bytes_per_epoch": 1048576,
        "fixed_bytes": 67108864,
        "projected_output_bytes": EXPECTED_PAIR_COUNT * 1048576 + 67108864,
        "disk_safety_reserve_bytes": 1073741824,
        "required_available_bytes": EXPECTED_PAIR_COUNT * 1048576 + 67108864 + 1073741824,
        "formula": "1509*bytes_per_epoch+fixed_bytes+disk_safety_reserve_bytes",
    }

    worker_failure = phase2._resource_admission_evidence(
        workers=DEFAULT_WORKERS, before=before, after=after, cache_read=_positive_io(),
        peak_per_worker_rss_bytes=1, worker_failure_count=1,
        actual_process_count=DEFAULT_WORKERS,
    )
    assert "zero_worker_failures" in worker_failure["rejection_reasons"]

    rss_boundary = phase2._resource_admission_evidence(
        workers=DEFAULT_WORKERS,
        before=_resource_snapshot(ram=1600), after=_resource_snapshot(ram=1600),
        cache_read=_positive_io(), peak_per_worker_rss_bytes=70,
        worker_failure_count=0, actual_process_count=DEFAULT_WORKERS,
    )
    assert "projected_rss_below_70_percent_available_ram" in rss_boundary["rejection_reasons"]

    bad_io = phase2._resource_admission_evidence(
        workers=DEFAULT_WORKERS, before=before, after=after,
        cache_read={"bytes_read": 1, "elapsed_seconds": 0.0, "throughput_bytes_per_second": 0.0},
        peak_per_worker_rss_bytes=1, worker_failure_count=0,
        actual_process_count=DEFAULT_WORKERS,
    )
    assert "positive_cache_read_io" in bad_io["rejection_reasons"]

    no_disk = phase2._resource_admission_evidence(
        workers=DEFAULT_WORKERS,
        before=_resource_snapshot(ram=100_000_000_000, disk=1),
        after=_resource_snapshot(ram=100_000_000_000, disk=1),
        cache_read=_positive_io(), peak_per_worker_rss_bytes=1,
        worker_failure_count=0, actual_process_count=DEFAULT_WORKERS,
    )
    assert "adequate_disk_for_deterministic_output_projection" in no_disk["rejection_reasons"]


def test_maximum20_requires_zero_swap_and_available_stable_temperature():
    rejected = phase2._resource_admission_evidence(
        workers=MAX_WORKERS,
        before=_resource_snapshot(ram=100_000_000_000, swap_in=1, temperature=None),
        after=_resource_snapshot(ram=100_000_000_000, swap_in=2, temperature=None),
        cache_read=_positive_io(), peak_per_worker_rss_bytes=1,
        worker_failure_count=0, actual_process_count=MAX_WORKERS,
    )
    assert "maximum20_zero_swap_activity" in rejected["rejection_reasons"]
    assert "maximum20_temperature_available_and_stable" in rejected["rejection_reasons"]
    admitted = phase2._resource_admission_evidence(
        workers=MAX_WORKERS,
        before=_resource_snapshot(ram=100_000_000_000, temperature=40.0),
        after=_resource_snapshot(ram=100_000_000_000, temperature=42.0),
        cache_read=_positive_io(), peak_per_worker_rss_bytes=1,
        worker_failure_count=0, actual_process_count=MAX_WORKERS,
    )
    assert admitted["admitted"] is True


def test_rejected_resource_probe_evidence_is_persisted_before_raise(tmp_path, monkeypatch):
    paths = _fake_paths(tmp_path)
    preflight = PreflightResult(
        paths=paths, contract=load_phase2_contract(), config_hash="1" * 64,
        contract_hash="2" * 64, schema_hash="3" * 64, code_commit="4" * 40,
        raw_source_hashes={}, provider_hashes={}, source_fingerprint="7" * 64,
    )
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    evidence = {
        "status": "REJECTED", "workers_compared": DEFAULT_WORKERS,
        "resource_admission": {"admitted": False},
        "rejection_reasons": ["RESOURCE::positive_cache_read_io"],
    }

    def reject(*_args, **_kwargs):
        raise phase2.ResourceAdmissionError(evidence)

    monkeypatch.setattr(phase2, "resource_determinism_probe", reject)
    with pytest.raises(phase2.ResourceAdmissionError, match="resource admission rejected"):
        phase2._load_or_run_probe(
            attempt, tmp_path / "cache", preflight, (),
            workers=DEFAULT_WORKERS, resume=False,
        )
    persisted = json.loads(
        (attempt / "RESOURCE_DETERMINISM_PROBE.json").read_text(encoding="utf-8")
    )
    assert persisted["status"] == "REJECTED"
    assert persisted["source_fingerprint"] == preflight.source_fingerprint


def test_zero_availability_is_explicit_poor_applicability_not_vacuous_evaluation():
    headings = [{"epoch_index": index, "method_native_accepted": "false"} for index in range(3)]
    proxies = [{
        "epoch_index": index, "production_objective": None, "proxy_objective": None,
        "oracle_gated_epoch": index in phase2.ORACLE_INDICES,
    } for index in range(3)]
    counts = phase2._post_evaluation_counts(headings, proxies)
    assert counts == {
        "accepted_count": 0,
        "proxy_objective_eligible_accepted_count": 0,
        "proxy_objective_evaluated_count": 0,
        "proxy_objective_not_evaluated_accepted_count": 0,
        "oracle_gated_accepted_count": 0,
        "oracle_gated_proxy_objective_evaluated_count": 0,
    }
    assert phase2.PASS_VALIDATED != phase2.UNSUPPORTED


def test_fixed_trace_parser_requires_real_time_yaw_schema_and_preserves_evaluator():
    base = 1772784000
    header = ",".join(phase2.TRACE_CSV_COLUMNS) + "\n"
    payload = (
        header
        + f"{base + 66},0,0,0,0,0,0,10,0,0\n"
        + f"{base + 67},0,0,0,0,0,0,20,0,0\n"
    ).encode("utf-8")
    headings = [
        {
            "epoch_index": "0", "gps_week": "2408", "gps_tow_seconds": "460884",
            "method_native_accepted": "true", "body_yaw_deg": "85",
        },
        {
            "epoch_index": "1", "gps_week": "2408", "gps_tow_seconds": "460885",
            "method_native_accepted": "true", "body_yaw_deg": "75",
        },
    ]
    rows = phase2._trace_reference(payload, headings, leap_seconds=18)
    assert [row["absolute_time_unix_seconds"] for row in rows] == pytest.approx(
        [base + 66, base + 67]
    )
    assert [row["trace_body_yaw_ned_deg"] for row in rows] == pytest.approx([80.0, 70.0])
    assert [row["native_minus_trace_wrapsafe_deg"] for row in rows] == pytest.approx(
        [5.0, 5.0]
    )
    assert all(row["time_offset_seconds"] == 0.0 for row in rows)
    assert all(row["alignment_search_used"] is False for row in rows)

    timestamp_payload = payload.replace(b"time,lat", b"timestamp,lat", 1)
    with pytest.raises(phase2.Phase2RunnerError, match="timestamp is not accepted"):
        phase2._trace_reference(timestamp_payload, headings, leap_seconds=18)
    missing_payload = payload.replace(b",roll\n", b"\n", 1)
    with pytest.raises(phase2.Phase2RunnerError, match="requires exact columns"):
        phase2._trace_reference(missing_payload, headings, leap_seconds=18)

    # The real-scale first native TOW maps to base+55.998, not base+28873.998.
    early = [{**headings[0], "gps_tow_seconds": "460873.998"}]
    early_row = phase2._trace_reference(payload, early, leap_seconds=18)[0]
    assert early_row["absolute_time_unix_seconds"] == pytest.approx(base + 55.998)
    assert early_row["fixed_window_matched"] is False


def test_trace_unwraps_full_stream_before_native_window_and_brackets_boundaries():
    base = 1772784000
    payload = (
        ",".join(phase2.TRACE_CSV_COLUMNS) + "\n"
        + f"{base + 65},0,0,0,0,0,0,179,0,0\n"
        + f"{base + 341},0,0,0,0,0,0,-179,0,0\n"
    ).encode("utf-8")
    headings = [
        {
            "epoch_index": "0", "gps_week": "2408", "gps_tow_seconds": "460884",
            "method_native_accepted": "true", "body_yaw_deg": "271",
        },
        {
            "epoch_index": "1", "gps_week": "2408", "gps_tow_seconds": "461158",
            "method_native_accepted": "true", "body_yaw_deg": "269",
        },
    ]
    rows = phase2._trace_reference(payload, headings, leap_seconds=18)
    assert [row["fixed_window_matched"] for row in rows] == [True, True]
    assert [row["absolute_time_unix_seconds"] for row in rows] == pytest.approx(
        [base + 66, base + 340]
    )
    assert [row["trace_body_yaw_ned_deg"] for row in rows] == pytest.approx([
        phase2._wrap360(90.0 - (179.0 + 2.0 / 276.0)),
        phase2._wrap360(90.0 - (179.0 + 2.0 * 275.0 / 276.0)),
    ])


def test_post_native_cache_uses_frozen_native_not_current_post_fingerprint(
        tmp_path, monkeypatch):
    paths = _fake_paths(tmp_path)
    native_fingerprint = "a" * 64
    post_fingerprint = "b" * 64
    preflight = PreflightResult(
        paths=paths, contract=load_phase2_contract(), config_hash="1" * 64,
        contract_hash="2" * 64, schema_hash="3" * 64, code_commit="4" * 40,
        raw_source_hashes={}, provider_hashes={}, source_fingerprint=post_fingerprint,
        runtime_source_hashes={"phase2_runner.py": "5" * 64},
        git_source_state={"authorized_dirty_runtime_delta_present": True},
    )
    freeze = {"source_fingerprint": native_fingerprint, "code_commit": "4" * 40}
    summary = {
        "source_fingerprint": native_fingerprint, "code_commit": "4" * 40,
        "runtime_source_hashes": {"phase2_runner.py": "6" * 64},
    }
    identity = phase2._post_native_source_identity(preflight, freeze, summary)
    assert identity["native_source_fingerprint"] == native_fingerprint
    assert identity["post_native_source_fingerprint"] == post_fingerprint
    assert identity["post_only_source_fingerprint_diverged_from_native"] is True

    observed = {}

    def validate(cache_root, *, source_fingerprint, expected_pair_count):
        observed.update({
            "cache_root": cache_root,
            "source_fingerprint": source_fingerprint,
            "expected_pair_count": expected_pair_count,
        })
        return {"source_fingerprint": source_fingerprint}

    monkeypatch.setattr(phase2, "validate_compact_cache", validate)
    phase2._validate_post_native_compact_cache(paths, identity)
    assert observed == {
        "cache_root": paths.native_root / "COMPACT_CACHE",
        "source_fingerprint": native_fingerprint,
        "expected_pair_count": EXPECTED_PAIR_COUNT,
    }

    with pytest.raises(phase2.Phase2RunnerError, match="do not match"):
        phase2._post_native_source_identity(
            preflight,
            freeze,
            {**summary, "source_fingerprint": "c" * 64},
        )


def test_compact_cache_supplies_uniform_audited_trace_leap_seconds(tmp_path):
    cache = tmp_path / "cache"
    write_compact_cache(
        cache, _pairs(EXPECTED_PAIR_COUNT), source_fingerprint="d" * 64,
    )
    leap_seconds, evidence = phase2._validated_compact_cache_leap_seconds(cache)
    assert leap_seconds == 18
    assert evidence == {
        "source": "COMPACT_CACHE_PAIRED_EPOCHS_R1_R2_LEAP_FIELDS",
        "expected_and_observed_leap_seconds": 18,
        "paired_epoch_count_verified": EXPECTED_PAIR_COUNT,
        "receiver_epoch_field_count_verified": 2 * EXPECTED_PAIR_COUNT,
        "all_receiver_epoch_values_identical": True,
    }


def test_post_native_invocation_counts_are_explicitly_success_only():
    accounting = phase2._successful_post_native_invocation_accounting(3020)
    assert accounting == {
        "successful_post_native_invocation_attempt_count": 1,
        "successful_post_native_invocation_hpposecef_decode_pass_count": 2,
        "successful_post_native_invocation_hpposecef_decode_pass_count_unit": (
            "GNSS_RECEIVER_STREAM"
        ),
        "successful_post_native_invocation_hpposecef_semantic_decode_count": 3020,
        "successful_post_native_invocation_trace_open_count": 1,
        "prior_failed_post_native_attempts_not_in_successful_invocation_counts": True,
    }
    with pytest.raises(phase2.Phase2RunnerError, match="decode count"):
        phase2._successful_post_native_invocation_accounting(-1)


def test_proxy_common_grid_nearest_association_records_signed_offsets_and_cadence():
    rows = phase2._proxy_common_grid_associations(
        [998, 1202, 1398],
        [1000, 1200, 1400],
        [1000, 1200, 1400],
    )
    assert [row["proxy_itow_ms"] for row in rows] == [1000, 1200, 1400]
    assert [row["proxy_itow_minus_rawx_ms"] for row in rows] == [2, -2, 2]
    assert [row["proxy_local_common_grid_cadence_ms"] for row in rows] == [
        200, 200, 200,
    ]
    assert [row["proxy_local_half_cadence_bound_ms"] for row in rows] == [
        100.0, 100.0, 100.0,
    ]
    assert all(
        row["proxy_association_status"]
        == "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
        for row in rows
    )
    assert all(
        row["proxy_association_policy"] == phase2.PROXY_ASSOCIATION_POLICY
        for row in rows
    )


def test_proxy_common_grid_rejects_ties_half_cadence_and_missing_cadence():
    tie = phase2._proxy_common_grid_associations(
        [1100], [1000, 1200], [1000, 1200],
    )[0]
    assert tie["proxy_association_status"] == "UNAVAILABLE_MIDPOINT_TIE"
    assert tie["proxy_itow_ms"] is None

    boundary, inside = phase2._proxy_common_grid_associations(
        [900, 901], [1000, 1200], [1000, 1200],
    )
    assert boundary["proxy_itow_minus_rawx_ms"] == 100
    assert boundary["proxy_local_half_cadence_bound_ms"] == 100.0
    assert boundary["proxy_association_status"] == "UNAVAILABLE_HALF_CADENCE_BOUND"
    assert inside["proxy_itow_minus_rawx_ms"] == 99
    assert inside["proxy_association_status"] == (
        "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
    )

    no_cadence = phase2._proxy_common_grid_associations(
        [1000], [1000], [1000],
    )[0]
    assert no_cadence["proxy_association_status"] == (
        "UNAVAILABLE_NO_LOCAL_COMMON_GRID_CADENCE"
    )


def test_proxy_common_grid_fails_duplicates_and_rejects_non_one_to_one_sequences():
    with pytest.raises(phase2.Phase2RunnerError, match="GNSS1.*duplicates"):
        phase2._proxy_common_grid_associations(
            [1000], [1000, 1000], [1000, 1200],
        )
    duplicated_assignment = phase2._proxy_common_grid_associations(
        [998, 999], [1000, 1200], [1000, 1200],
    )
    assert {
        row["proxy_association_status"] for row in duplicated_assignment
    } == {"UNAVAILABLE_NONUNIQUE_ASSIGNMENT"}

    nonmonotonic = phase2._proxy_common_grid_associations(
        [1198, 998], [1000, 1200], [1000, 1200],
    )
    assert {
        row["proxy_association_status"] for row in nonmonotonic
    } == {"UNAVAILABLE_NONMONOTONIC_ASSIGNMENT"}


def test_hpposecef_proxy_rows_use_associated_common_itow_not_rawx_exact_key(
        tmp_path, monkeypatch):
    paths = _fake_paths(tmp_path)

    def hp_epoch(itow, vector):
        return SimpleNamespace(
            itow_ms=itow,
            position_ecef_m=phase2.np.asarray(vector, dtype=float),
        )

    common = [101000, 101200, 101400]
    receiver1 = SimpleNamespace(nav_hpposecef_epochs=[
        hp_epoch(itow, [6378137.0, 0.0, 0.0]) for itow in common
    ])
    receiver2 = SimpleNamespace(nav_hpposecef_epochs=[
        hp_epoch(itow, [6378137.0, 1.0, 0.0]) for itow in common
    ])

    def reconstruct(path, *, decode_nav_hpposecef_semantics):
        assert decode_nav_hpposecef_semantics is True
        return receiver1 if path == paths.gnss1_raw else receiver2

    monkeypatch.setattr(phase2, "reconstruct_ubx_stream", reconstruct)
    headings = [{
        "epoch_index": str(index), "gps_week": "2408",
        "gps_tow_seconds": str(100.998 + 0.2 * index),
        "method_native_accepted": "false", "body_yaw_deg": "",
    } for index in range(3)]
    rows, semantic_count = phase2._hpposecef_proxy_rows(
        paths, headings, [{"baseline_ecef_m": ""} for _ in headings],
    )
    assert semantic_count == 6
    assert [row["rawx_itow_ms"] for row in rows] == [100998, 101198, 101398]
    assert [row["proxy_itow_ms"] for row in rows] == common
    assert [row["proxy_itow_minus_rawx_ms"] for row in rows] == [2, 2, 2]
    assert all(row["proxy_status"] == "AVAILABLE_DESCRIPTIVE_ONLY" for row in rows)


def _write_primary_post_evidence(paths: Phase2Paths) -> dict[Path, bytes]:
    paths.native_root.mkdir(parents=True, exist_ok=True)
    paths.report_root.mkdir(parents=True, exist_ok=True)
    payloads = {
        path: f"primary::{logical}".encode("utf-8")
        for logical, path in paths.post_native_files.items()
    }
    payloads[paths.final_report] = b"primary-report"
    payloads[paths.final_status] = b"primary-status"
    for path, payload in payloads.items():
        path.write_bytes(payload)
    return payloads


def test_post_recovery_paths_inventory_hashes_and_no_overwrite(tmp_path):
    paths = _fake_paths(tmp_path)
    primary_payloads = _write_primary_post_evidence(paths)
    inventory = phase2._primary_post_inventory(paths)
    assert inventory["role"] == "IMMUTABLE_PRIMARY_POST_EVIDENCE_INPUT_ONLY"
    assert len(inventory["files"]) == len(phase2.POST_NATIVE_FILE_NAMES) + 2
    assert len(inventory["inventory_sha256"]) == 64

    destinations = phase2._post_native_destinations(paths, "proxyfix1")
    assert destinations.output_root == paths.native_root / "POST_NATIVE_RECOVERY_proxyfix1"
    assert destinations.report == paths.report_root / "PHASE2_EXT02_C00_REPORT_proxyfix1.md"
    assert destinations.status == paths.report_root / "PHASE2_STATUS_proxyfix1.json"
    assert all(
        path.parent == destinations.output_root
        for path in destinations.post_native_files.values()
    )
    assert not set(destinations.post_native_files.values()).intersection(
        paths.post_native_files.values()
    )
    phase2._validate_recovery_targets_absent(destinations)
    phase2._prepare_recovery_output_root(destinations)
    with pytest.raises(phase2.Phase2RunnerError, match="target collision"):
        phase2._validate_recovery_targets_absent(destinations)
    assert all(path.read_bytes() == payload for path, payload in primary_payloads.items())
    phase2._revalidate_primary_post_inventory(paths, inventory)


def test_post_recovery_rejects_unsafe_slug_any_target_and_prior_hash_drift(tmp_path):
    paths = _fake_paths(tmp_path)
    _write_primary_post_evidence(paths)
    inventory = phase2._primary_post_inventory(paths)
    for value in ("../escape", "has.dot", "", "a" * 65):
        with pytest.raises(phase2.Phase2RunnerError, match="post recovery id"):
            phase2._post_native_destinations(paths, value)

    destinations = phase2._post_native_destinations(paths, "collision")
    destinations.report.write_bytes(b"existing recovery report")
    with pytest.raises(phase2.Phase2RunnerError, match="target collision"):
        phase2._validate_recovery_targets_absent(destinations)

    paths.final_status.write_bytes(b"mutated-primary-status")
    with pytest.raises(phase2.Phase2RunnerError, match="inventory changed"):
        phase2._revalidate_primary_post_inventory(paths, inventory)


def test_post_recovery_id_is_rejected_outside_post_native_mode(tmp_path):
    with pytest.raises(phase2.Phase2RunnerError, match="only in post-native"):
        phase2.preflight_phase2(
            tmp_path / "unused.yaml", mode="preflight", post_recovery_id="proxyfix1",
        )


def test_wrapsafe_metrics_use_fixed_denominator_continuity_and_circular_bias():
    metrics = phase2._wrapsafe_error_metrics(
        [179.0, -179.0], [3, 4], [100.6, 100.8], valid_denominator=4,
    )
    assert metrics["matched_count"] == 2 and metrics["valid_coverage"] == 0.5
    assert metrics["segment_count"] == 1 and metrics["maximum_gap_seconds"] == pytest.approx(0.2)
    assert abs(abs(metrics["circular_wrapsafe_bias_deg"]) - 180.0) < 1.0e-9
    assert metrics["p95_absolute_deg"] == pytest.approx(179.0)


def test_fractional_groups_join_identity_tracking_and_low_dimension_strata():
    rows = [{
        "epoch_index": 7, "status": "AVAILABLE",
        "fractional_dd_cycles": [0.25],
        "proxy_implied_fractional_dd_cycles": [0.20],
        "sub_half_cycle_combination": "GNSS1_ONLY",
        "lock_reset_present": True, "cycle_slip_present": False,
        "pivot_changed": True, "low_dd_dimension": True,
        "identity_fractional_pairs": [{
            "pivot_identity": "0:3:0:0", "satellite_identity": "0:4:0:0",
            "production_fractional_cycles": 0.25,
            "proxy_implied_fractional_cycles": 0.20,
            "r1_subHalfCyc": True, "r2_subHalfCyc": False,
        }],
    }]
    summary = phase2._fractional_group_statistics(rows)
    groups = summary["stable_satellite_pivot_subHalfCyc_groups"]
    assert len(groups) == 1 and groups[0]["observation_count"] == 1
    strata = summary["stratified_tracking_and_dimension_statistics"]
    assert strata["subHalfCyc=GNSS1_ONLY"]["epoch_count"] == 1
    assert strata["lock_reset=true"]["production_observation_count"] == 1
    assert strata["low_dd_dimension=true"]["proxy_observation_count"] == 1


def test_native_only_never_enters_post_native_sources_and_full_orders_after_finalize(
        tmp_path, monkeypatch):
    paths = _fake_paths(tmp_path)
    preflight = PreflightResult(
        paths=paths, contract=load_phase2_contract(), config_hash="1" * 64,
        contract_hash="2" * 64, schema_hash="3" * 64, code_commit="4" * 40,
        raw_source_hashes={}, provider_hashes={}, source_fingerprint="7" * 64,
    )
    attempt = paths.native_root.parent / ".attempt"
    attempt.mkdir(parents=True)
    cache = attempt / "COMPACT_CACHE"
    cache.mkdir()
    order = []
    monkeypatch.setattr(phase2, "preflight_phase2", lambda *_args, **_kwargs: preflight)
    monkeypatch.setattr(phase2, "_open_attempt", lambda *_args, **_kwargs: attempt)
    monkeypatch.setattr(
        phase2, "_prepare_or_resume_cache",
        lambda *_args, **_kwargs: (
            cache, (tmp_path / "a.nav", tmp_path / "b.nav"),
            {"pair_count": EXPECTED_PAIR_COUNT}, {},
        ),
    )
    monkeypatch.setattr(phase2, "_load_or_run_probe", lambda *_args, **_kwargs: {"status": "PASS"})
    monkeypatch.setattr(phase2, "execute_shards", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        phase2, "write_native_outputs",
        lambda *_args, **_kwargs: {
            "paired_epoch_count": EXPECTED_PAIR_COUNT,
            "success_row_count": 1, "failure_row_count": EXPECTED_PAIR_COUNT - 1,
        },
    )
    monkeypatch.setattr(
        phase2, "_atomic_finalize_attempt",
        lambda *_args, **_kwargs: order.append("finalize"),
    )
    monkeypatch.setattr(
        phase2, "run_post_native_diagnostics",
        lambda *_args, **_kwargs: order.append("post") or {"terminal_status": phase2.PASS_VALIDATED},
    )
    native = phase2.run_phase2(tmp_path / "paths.yaml", mode="native-only")
    assert native["terminal_status"] == phase2.PASS_READY
    assert order == ["finalize"]
    order.clear()
    full = phase2.run_phase2(tmp_path / "paths.yaml", mode="full")
    assert full["terminal_status"] == phase2.PASS_VALIDATED
    assert order == ["finalize", "post"]


def test_temp_only_attempt_failure_is_reported_as_preserved_evidence(tmp_path, monkeypatch):
    paths = _fake_paths(tmp_path)
    preflight = PreflightResult(
        paths=paths, contract=load_phase2_contract(), config_hash="1" * 64,
        contract_hash="2" * 64, schema_hash="3" * 64, code_commit="4" * 40,
        raw_source_hashes={}, provider_hashes={}, source_fingerprint="8" * 64,
    )
    predicted = phase2._attempt_root(preflight)
    temporary_name = ".ATTEMPT_IDENTITY.json.tmp.12345"
    temporary_payload = b"partial-identity-evidence"
    monkeypatch.setattr(phase2, "preflight_phase2", lambda *_args, **_kwargs: preflight)

    def fail_after_temp(*_args, **_kwargs):
        predicted.mkdir(parents=True)
        (predicted / temporary_name).write_bytes(temporary_payload)
        raise phase2.Phase2RunnerError("simulated identity install failure")

    monkeypatch.setattr(phase2, "_open_attempt", fail_after_temp)
    result = phase2.run_phase2(tmp_path / "paths.yaml", mode="native-only")
    assert result["partial_attempt_preserved"] is True
    assert temporary_name in result["partial_attempt_evidence_entries"]
    assert (predicted / temporary_name).read_bytes() == temporary_payload
    assert (predicted / "ATTEMPT_TERMINAL.json").is_file()


def test_wrapped_csv_error_terminalizes_attempt_with_original_error_text(tmp_path, monkeypatch):
    paths = _fake_paths(tmp_path)
    preflight = PreflightResult(
        paths=paths, contract=load_phase2_contract(), config_hash="1" * 64,
        contract_hash="2" * 64, schema_hash="3" * 64, code_commit="4" * 40,
        raw_source_hashes={}, provider_hashes={}, source_fingerprint="9" * 64,
    )
    attempt = phase2._attempt_root(preflight)
    attempt.mkdir(parents=True)
    oversized = tmp_path / "terminal-oversized.csv"
    phase2._atomic_write_csv(oversized, [{"payload": "q" * 2048}], ("payload",))
    monkeypatch.setattr(phase2, "CSV_FIELD_SIZE_LIMIT", 1024)
    monkeypatch.setattr(phase2, "preflight_phase2", lambda *_args, **_kwargs: preflight)
    monkeypatch.setattr(phase2, "_open_attempt", lambda *_args, **_kwargs: attempt)

    def fail_during_native_validation(*_args, **_kwargs):
        phase2._read_csv_rows(oversized)
        raise AssertionError("oversized CSV must fail")

    monkeypatch.setattr(phase2, "_prepare_or_resume_cache", fail_during_native_validation)
    result = phase2.run_phase2(tmp_path / "paths.yaml", mode="native-only")
    assert result["partial_attempt_preserved"] is True
    assert result["error_type"] == "Phase2RunnerError"
    assert "csv.Error: field larger than field limit" in result["error"]
    terminal = json.loads((attempt / "ATTEMPT_TERMINAL.json").read_text(encoding="utf-8"))
    assert "csv.Error: field larger than field limit" in terminal["error"]
