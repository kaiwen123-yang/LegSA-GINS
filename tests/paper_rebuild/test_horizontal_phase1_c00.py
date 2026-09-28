from pathlib import Path
from types import SimpleNamespace
import csv
import hashlib
import json
import subprocess
import sys

import numpy as np
import pytest
import yaml

import legsa_gins.paper_rebuild.horizontal_literature.phase1_runner as phase1
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import Candidate
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import RawxEpoch, SignalIdentity
from legsa_gins.paper_rebuild.horizontal_literature.phase1_runner import (
    BLOCKED_EXTERNAL,
    BLOCKED_RAW,
    OUTPUT_RELATIVE_PATHS,
    PASS_STATUS,
    REPOSITORY_ROOT,
    load_paths,
    run_phase1,
    runtime_manifest_template,
)
import legsa_gins.paper_rebuild.horizontal_literature.phase1r_runner as phase1r


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _config(tmp_path: Path, create_sources: bool) -> Path:
    project = tmp_path / "project"
    raw = project / "data/raw"
    by2 = raw / "BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal"
    clean = project / "clean_rebuild_202607"
    tools = tmp_path / "external"
    bridge_root = tools / "bridge"
    rtklib_root = tools / "RTKLIB"
    bridge_root.mkdir(parents=True)
    rtklib_root.mkdir()
    (rtklib_root / "LICENSE.txt").write_text("BSD-2-Clause", encoding="utf-8")
    for name in ("convbin", "nav_bridge.so", "lambda.so"):
        (tools / name).write_bytes(name.encode())
    if create_sources:
        by2.mkdir(parents=True)
        raw_values = {"gnss1-raw.csv": b"data\nreceiver1\n",
                      "gnss2-raw.csv": b"data\nreceiver2\n"}
        rows = []
        for name, data in raw_values.items():
            (by2 / name).write_bytes(data)
            relative = str((by2 / name).relative_to(raw)).replace("\\", "/")
            rows.append({"relative_path": relative, "size_bytes": len(data),
                         "sha256": _digest(data)})
        lock = clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv"
        lock.parent.mkdir(parents=True)
        with lock.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["relative_path", "size_bytes", "sha256"])
            writer.writeheader()
            writer.writerows(rows)
    path = tmp_path / "paths.yaml"
    path.write_text(yaml.safe_dump({
        "schema_version": "paper_rebuild.paths.v1",
        "paths": {
            "code_root": str(REPOSITORY_ROOT), "raw_root": str(raw),
            "by2_fix_root": str(by2), "clean_root": str(clean),
            "horizontal_literature_rtklib_root": str(rtklib_root),
            "horizontal_literature_convbin": str(tools / "convbin"),
            "horizontal_literature_rtklib_bridge": str(tools / "nav_bridge.so"),
            "horizontal_literature_lambda_library": str(tools / "lambda.so"),
            "horizontal_literature_bridge_root": str(bridge_root),
        },
    }), encoding="utf-8")
    return path


def test_missing_raw_fails_before_mkdir_with_machine_terminal(tmp_path):
    config = _config(tmp_path, False)
    paths = load_paths(config)
    result = run_phase1(config, "disabled")
    assert result["status"] == BLOCKED_RAW
    assert result["evaluation"] == "NOT_EVALUATED"
    assert result["paired_epoch_count"] is None
    assert result["output_files"] == "NOT_PRODUCED"
    assert not paths.stage_root.exists()


def test_existing_sources_fail_before_mkdir_when_external_provider_is_missing(tmp_path):
    config = _config(tmp_path, True)
    paths = load_paths(config)
    paths.lambda_library.unlink()
    result = run_phase1(config, "disabled")
    assert result["status"] == BLOCKED_EXTERNAL
    assert not paths.stage_root.exists()
    manifest = runtime_manifest_template(paths, "a" * 64, "deadbeef")
    assert manifest["trace_used_online"] is False
    assert manifest["old_runtime_input_count"] == 0
    assert set(manifest["output_paths"]) == set(OUTPUT_RELATIVE_PATHS)
    assert manifest["raw_hashes_validated"] is False
    assert manifest["satellite_state_provider_identity"] == "RTKLIB_BROADCAST_EPHEMERIS"


def test_real_pipeline_contract_writes_every_pair_and_all_named_outputs(tmp_path, monkeypatch):
    config = _config(tmp_path, True)
    paths = load_paths(config)
    epoch1 = RawxEpoch(100.0, 2409, 18, 1, 1, ())
    epoch2 = RawxEpoch(100.0, 2409, 18, 1, 1, ())

    def reconstruct(_source, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"UBX")
        epoch = epoch1 if "gnss1" in output.name else epoch2
        return SimpleNamespace(
            rawx_epochs=(epoch,), sfrbx_messages=(SimpleNamespace(reserved1=0, reserved2=0),
                                                  SimpleNamespace(reserved1=0, reserved2=0)),
            nav_sat_epochs=(),
            message_counts={"02-15": 1, "02-13": 2}, checksum_failure_count=0,
            input_cell_count=2, stream=b"UBX", discarded_byte_count=0,
        )

    def convbin(_executable, _ubx, observation, navigation):
        observation.write_text("OBS", encoding="utf-8")
        navigation.write_text("NAV", encoding="utf-8")
        return [str(_executable), "-n", str(navigation), str(_ubx)]

    class Provider:
        ephemeris_counts = {"gps_gal_bds_qzs": 12, "glonass": 0, "sbas": 0}

        def __init__(self, bridge, navigation):
            assert bridge == paths.rtklib_bridge
            assert len(navigation) == 2

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ephemeris_audit(self, *_args):
            return SimpleNamespace(signed_age_seconds=-120.0, health=0)

    monkeypatch.setattr(phase1, "_external_dependency_audit", lambda _paths: {
        "name": "RTKLIB", "commit": "180043ee24b6d2b168f98b64be15f69d50046b1a",
        "license": "BSD-2-Clause", "upstream_source_patch": "none",
        "local_thin_adapter": {"source_hashes": {}},
    })
    monkeypatch.setattr(phase1, "_nav_sat_elevation_audit", lambda *_args: {
        "sanity_pass": True, "matched_satellite_count": 1,
    })
    monkeypatch.setattr(phase1, "reconstruct_ubx_stream", reconstruct)
    monkeypatch.setattr(phase1, "_run_convbin", convbin)
    monkeypatch.setattr(phase1, "RtklibBroadcastProvider", Provider)
    monkeypatch.setattr(
        phase1, "gps_l1_code_spp",
        lambda *_args, **_kwargs: SimpleNamespace(position_ecef_m=np.array([6_378_137.0, 0.0, 0.0])),
    )
    identity = SignalIdentity(0, 3, 0, 0)
    model = SimpleNamespace(
        pivot=identity, satellites=(SignalIdentity(0, 4, 0, 0),),
        observation_m=np.zeros(2), ambiguity_design_m=np.array([[0.0], [1.0]]),
        baseline_design=np.zeros((2, 3)), covariance_m2=np.eye(2),
        elevations_rad={identity: 0.8},
    )
    monkeypatch.setattr(phase1, "build_gps_l1_double_difference_model",
                        lambda *_args, **_kwargs: model)
    calls = []

    def strict_solver(*_args, **kwargs):
        calls.append(kwargs)
        best = Candidate(np.array([0]), np.array([0.0, 0.350, 0.0]),
                         1.0, 0.5, 0.5, 0.0)
        second = Candidate(np.array([1]), np.array([0.0, 0.350, 0.0]),
                           2.0, 1.5, 0.5, 0.0)
        return SimpleNamespace(
            best=best, second=second, ratio=2.0, ratio_valid=True,
            search_complete=True, nodes_visited=10, candidates_evaluated=4,
            failure_code=None, float_solution=SimpleNamespace(covariance=np.eye(4)),
        )

    monkeypatch.setattr(phase1, "solve_clambda", strict_solver)
    result = run_phase1(config, "disabled")
    assert result["status"] == PASS_STATUS
    assert result["paired_epoch_count"] == 1
    assert result["success_row_count"] == 1
    assert result["failure_row_count"] == 0
    assert (result["fixed_row_count"], result["float_row_count"],
            result["invalid_row_count"]) == (1, 0, 0)
    assert result["conservation"] == "PASS"
    assert calls and calls[0]["strict"] is True
    assert calls[0]["lambda_bridge_path"] == paths.lambda_library
    assert calls[0]["length_m"] == 0.350
    assert calls[0]["initial_candidate_count"] == 512
    assert calls[0]["timeout_seconds"] == 2.0
    assert all(path.is_file() for path in paths.output_files.values())
    assert len(paths.output_files) == 18
    with paths.output_files["ext01_heading_results"].open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["status"] == "SUCCESS"
    assert float(rows[0]["baseline_length_m"]) == 0.350
    assert result["trace_used_online"] is False
    assert json.loads(paths.output_files["raw_observation_audit"].read_text())["trace_open_count"] == 0


def test_direct_cli_bootstraps_src_and_emits_machine_blocked_json(tmp_path):
    config = _config(tmp_path, False)
    script = REPOSITORY_ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase1.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--paths-config", str(config),
         "--method-id", "EXT01_CLAMBDA", "--case-id", "C00", "--trace-mode", "disabled"],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 2
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload["status"] == BLOCKED_RAW
    assert payload["evaluation"] == "NOT_EVALUATED"
    assert not load_paths(config).stage_root.exists()


def test_post_mkdir_failure_writes_machine_terminal_and_preserves_partial_root(
        tmp_path, monkeypatch):
    config = _config(tmp_path, True)
    paths = load_paths(config)
    monkeypatch.setattr(phase1, "_external_dependency_audit", lambda _paths: {
        "name": "RTKLIB", "local_thin_adapter": {"source_hashes": {}},
    })
    monkeypatch.setattr(
        phase1, "_execute_after_stage_created",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("deliberate post-mkdir failure")),
    )
    result = run_phase1(config, "disabled")
    assert result["status"] == "BLOCKED_PHASE1_EXT01_C00_RUNTIME_FAILURE"
    assert result["partial_stage_preserved"] is True
    assert paths.stage_root.is_dir()
    status = json.loads(paths.output_files["phase1_status"].read_text(encoding="utf-8"))
    assert status["error_type"] == "RuntimeError"
    assert status["trace_used_online"] is False


def test_workers_1_and_16_identical():
    left = {
        "result": {"epoch_index": 7, "ambiguity_vector": [2, -1],
                   "body_yaw_deg": 12.5, "global_optimum_certified": True},
        "dd": {"common_raw_satellite_count": 8},
        "search": {"termination_reason": "GLOBAL_BOUND_CERTIFIED",
                   "branch_and_bound_nodes_expanded": 19},
        "runtime": {"runtime_seconds": 0.1, "worker_pid": 101},
    }
    right = json.loads(json.dumps(left))
    right["runtime"].update(runtime_seconds=0.7, worker_pid=202)
    assert phase1r._scientific_part(left) == phase1r._scientific_part(right)
    right["result"]["ambiguity_vector"] = [2, 0]
    assert phase1r._scientific_part(left) != phase1r._scientific_part(right)


def test_all_1509_epochs_conserved():
    rows = [
        {"gps_week": 2408, "gps_tow_seconds": 460873.998 + 0.2 * index,
         "integer_solution_returned": index % 3 != 0}
        for index in range(phase1r.EXPECTED_PAIR_COUNT)
    ]
    continuity = phase1r._continuity(rows)
    assert len(rows) == phase1r.EXPECTED_PAIR_COUNT == 1509
    assert continuity["integer_solution_epoch_count"] == sum(
        row["integer_solution_returned"] for row in rows
    )


def test_trace_not_opened_before_native_freeze(tmp_path):
    trace = tmp_path / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
    trace.write_text("time,yaw\n1,2\n", encoding="utf-8")
    fake = SimpleNamespace(
        native_freeze=tmp_path / "missing_native_freeze.json",
        target_root=tmp_path,
        output_files={},
        base=SimpleNamespace(by2_fix_root=tmp_path),
    )
    with pytest.raises(FileNotFoundError):
        phase1r._trace_metrics_after_freeze(fake, (), ())
    assert trace.read_text(encoding="utf-8") == "time,yaw\n1,2\n"


def test_phase1r_output_contract_has_no_ambiguity_acceptance_claim():
    assert phase1r.RESULT_FIELDS.index("ambiguity_satellite_identities") \
        < phase1r.RESULT_FIELDS.index("ambiguity_vector")
    assert "ambiguity_acceptance_test_defined" in phase1r.RESULT_FIELDS
    assert "ambiguity_accepted" in phase1r.RESULT_FIELDS
    assert "global_optimum_certified" in phase1r.SEARCH_FIELDS
    assert "candidate_cap_applied" in phase1r.SEARCH_FIELDS


def test_phase1r_terminal_cannot_pass_empty_validity_evidence():
    status, _ = phase1r._terminal_from_evidence(
        {"row_level_scientific_equality": True},
        {"search_objective_crosscheck_passed": True,
         "objective_identity_crosscheck_passed": True,
         "code_phase_cross_covariance_crosscheck_passed": True},
        [], {"quality_statistics": {}, "output_row_count": 0},
        {"native_rows": 1509, "dd_rows": 1509, "search_rows": 1509,
         "proxy_rows": 1509, "integer_solution_rows": 0,
         "fractional_dd_rows": 0, "rtklib_diagnostic_rows": 0,
         "rtklib_matched_proxy_rows": 0},
    )
    assert status == "BLOCKED_PHASE1R_VALIDITY_EVIDENCE_EMPTY"


def test_phase1r_terminal_requires_rtklib_rows_to_match_proxy_epochs():
    status, _ = phase1r._terminal_from_evidence(
        {"row_level_scientific_equality": True},
        {"search_objective_crosscheck_passed": True,
         "objective_identity_crosscheck_passed": True,
         "code_phase_cross_covariance_crosscheck_passed": True},
        [], {"quality_statistics": {}, "output_row_count": 4,
             "matched_proxy_count": 0},
        {"native_rows": 1509, "dd_rows": 1509, "search_rows": 1509,
         "proxy_rows": 1509, "integer_solution_rows": 1,
         "fractional_dd_rows": 1, "rtklib_diagnostic_rows": 4,
         "rtklib_matched_proxy_rows": 0},
    )
    assert status == "BLOCKED_PHASE1R_RTKLIB_DIAGNOSTIC_JOIN_FAILED"


def test_phase1r_epoch_fingerprint_binds_generated_navigation_hashes():
    audit = {
        "ubx_hashes": {"gnss1.ubx": "1" * 64},
        "observation_hashes": {"gnss1.obs": "2" * 64},
        "navigation_hashes": {"gnss1.nav": "3" * 64},
        "cache_manifest_sha256": "4" * 64,
    }
    first = phase1r._epoch_fingerprint("0" * 64, audit)
    changed = json.loads(json.dumps(audit))
    changed["navigation_hashes"]["gnss1.nav"] = "5" * 64
    assert first != phase1r._epoch_fingerprint("0" * 64, changed)


def test_phase1r_original_c00_hash_tree_rejects_symlinks(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("immutable", encoding="utf-8")
    (tmp_path / "alias.txt").symlink_to(source)
    with pytest.raises(phase1r.Phase1RRunnerError, match="symlink"):
        phase1r._hash_tree(tmp_path)


def test_phase1r_containment_rejects_symlinked_runtime_ancestor(tmp_path):
    target = tmp_path / "target"
    outside = tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (target / ".cache").symlink_to(outside, target_is_directory=True)
    with pytest.raises(phase1r.Phase1RRunnerError, match="symlink"):
        phase1r._assert_contained(target / ".cache/fingerprint/NAV", target)


def test_phase1r_native_freeze_rejects_stale_run_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(phase1r, "EXPECTED_PAIR_COUNT", 1)
    target = tmp_path / "validated"
    target.mkdir()
    outputs = {}
    for name in phase1r.NATIVE_FREEZE_NAMES:
        path = target / f"{name}.csv"
        if name == "failures":
            path.write_text("epoch_index\n", encoding="utf-8")
        else:
            path.write_text("epoch_index\n0\n", encoding="utf-8")
        outputs[name] = path
    freeze_path = target / "PHASE1R_NATIVE_FREEZE.json"
    raw_hashes = {"gnss1-raw.csv": "1" * 64, "gnss2-raw.csv": "2" * 64}
    original_hashes = {"native.csv": "3" * 64}
    freeze_path.write_text(json.dumps({
        "native_hashes": {name: phase1r.sha256_file(path) for name, path in outputs.items()},
        "native_frozen_before_trace_open": True,
        "trace_open_count_at_freeze": 0,
        "paired_epoch_count": 1,
        "native_row_count": 1,
        "failure_row_count": 0,
        "worker_determinism": {"row_level_scientific_equality": True},
        "run_fingerprint": "a" * 64,
        "raw_source_hashes": raw_hashes,
        "original_c00_hashes": original_hashes,
        "original_c00_tree_digest": phase1r._tree_digest(original_hashes),
    }), encoding="utf-8")
    paths = SimpleNamespace(
        target_root=target, native_freeze=freeze_path, output_files=outputs,
    )
    phase1r._validate_native_freeze(
        paths, fingerprint="a" * 64, raw_hashes=raw_hashes,
        original_hashes=original_hashes,
    )
    with pytest.raises(phase1r.Phase1RRunnerError, match="fingerprint"):
        phase1r._validate_native_freeze(
            paths, fingerprint="b" * 64, raw_hashes=raw_hashes,
            original_hashes=original_hashes,
        )
