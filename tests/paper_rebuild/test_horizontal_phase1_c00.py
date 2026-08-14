from pathlib import Path
from types import SimpleNamespace
import csv
import hashlib
import json
import subprocess
import sys

import numpy as np
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
