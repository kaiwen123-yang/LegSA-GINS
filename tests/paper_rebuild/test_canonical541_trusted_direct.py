import json
from pathlib import Path

import pytest
import yaml

import legsa_gins.paper_rebuild.canonical541.runner as runner
import legsa_gins.paper_rebuild.canonical541.trusted_direct as direct
import legsa_gins.paper_rebuild.canonical541.evaluator as evaluator
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FEATURE_FIELDS, FULL_METHODS


SHA = "a" * 64


def test_trusted_attempt_and_scientific_freeze_are_exact(tmp_path: Path) -> None:
    stage = tmp_path / "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX" / direct.TRUSTED_ATTEMPT_NAME
    stage.mkdir(parents=True)
    assert direct.validate_trusted_identity(stage, direct.SCIENTIFIC_FREEZE) == stage.resolve()
    with pytest.raises(direct.TrustedDirectError, match="scientific freeze"):
        direct.validate_trusted_identity(stage, "0" * 40)
    wrong = stage.parent / ".attempt_other"; wrong.mkdir()
    with pytest.raises(direct.TrustedDirectError, match="authorized attempt"):
        direct.validate_trusted_identity(wrong, direct.SCIENTIFIC_FREEZE)


def test_trusted_expected_inputs_require_paths_without_hashing(tmp_path: Path, monkeypatch) -> None:
    imu = tmp_path / "input.imu"; gnss = tmp_path / "input.gnss"
    imu.write_text("imu\n"); gnss.write_text("gnss\n")
    manifest = {
        "actual_solver_inputs": {"imu": str(imu), "gnss": str(gnss)},
        "actual_solver_input_hashes": {"imu": SHA, "gnss": SHA},
        "effective_flags": {"raw_doppler": False, "go2_rp": False, "go2_hv": False},
    }
    monkeypatch.setattr(runner, "sha256_file", lambda _: (_ for _ in ()).throw(AssertionError("payload hashed")))
    expected = runner._expected_solver_inputs(manifest, trusted_manifest_hashes=True)
    assert expected == {
        "propagation_imu": imu.resolve(),
        "gnss_position_receiver_velocity_dual_yaw": gnss.resolve(),
    }
    with pytest.raises(AssertionError, match="payload hashed"):
        runner._expected_solver_inputs(manifest)


def test_trusted_template_bypasses_parent_bundle_loaders(tmp_path: Path, monkeypatch) -> None:
    imu = tmp_path / "input.imu"; gnss = tmp_path / "input.gnss"
    imu.write_text("x"); gnss.write_text("y")
    profile = FULL_METHODS[0]
    manifest = {"actual_solver_inputs": {"imu": str(imu), "gnss": str(gnss)}}
    monkeypatch.setattr(runner, "build_clean_runtime_config",
                        lambda **_: (_ for _ in ()).throw(AssertionError("parent loader called")))
    text = runner.build_runtime_config(
        profile=profile, clean_input_manifest="not-read", auxiliary_manifest="not-read",
        provider_protocol="not-read", method_bound_manifest=manifest,
        output_dir=tmp_path / "out", case_id="C00_clean_normal", run_id="RUN_00001",
        trusted_base_template="imupath: old\ngnsspath: old\noutputpath: old\n",
    )
    payload = yaml.safe_load(text)
    assert payload["imupath"] == str(imu)
    assert payload["gnsspath"] == str(gnss)
    assert payload["run_id"] == "RUN_00001"
    assert payload["trace_used_online"] is False


def test_manifest_loader_uses_recorded_hashes_and_strict_boolean_strings(
    tmp_path: Path, monkeypatch,
) -> None:
    stage = tmp_path
    source = tmp_path / "payload"; source.write_text("do not hash me")
    path = (stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND"
            / "C00_clean_normal" / "single_antenna_EKF" / "METHOD_BOUND_INPUT_MANIFEST.json")
    path.parent.mkdir(parents=True)
    flags = {field: str(FULL_METHODS[0].flags[field]).lower() for field in FEATURE_FIELDS}
    path.write_text(json.dumps({
        "case_id": "C00_clean_normal", "method_id": "F01",
        "method_name": "single_antenna_EKF", "effective_profile": "single_antenna_EKF",
        "effective_flags": flags, "stage_id": direct.STAGE_ID,
        "attempt_root": str(stage), "solver_code_freeze_commit": direct.SCIENTIFIC_FREEZE,
        "executable_sha256": SHA,
        "actual_solver_inputs": {"imu": str(source)},
        "actual_solver_input_hashes": {"imu": SHA},
        "method_bound_bundle_sha256": SHA,
    }))
    monkeypatch.setattr(direct, "METHOD_BOUND_COUNT", 1)
    bindings = direct._load_method_manifests(stage, expected_executable_hash=SHA)
    assert ("C00_clean_normal", FULL_METHODS[0].signature) in bindings


def test_pipeline_exposes_hard_locked_trusted_direct_command() -> None:
    source = (Path(__file__).parents[2] / "scripts/paper_rebuild/run_canonical541_repaired_pipeline.py").read_text()
    assert '"--trusted-direct-resume"' in source
    assert "run_canonical541_trusted_direct.py" in source
    assert "package_canonical541_trusted_direct.py" in source
    assert '"--trusted-direct"' in source


def test_trusted_runner_executable_rehash_is_guarded_by_opt_in() -> None:
    source = (Path(__file__).parents[2] / "src/legsa_gins/paper_rebuild/canonical541/runner.py").read_text()
    assert "if not trusted_manifest_hashes and sha256_file(binary)" in source
    assert "not trusted_manifest_hashes and sha256_file(binary) != expected_executable_hash" in source
    assert "output_hashes = {} if trusted_manifest_hashes else" in source
    assert '"output_hashes_deferred_to_seal": trusted_manifest_hashes' in source


def test_trusted_evaluator_seal_gate_does_not_hash_runtime_outputs(
    tmp_path: Path, monkeypatch,
) -> None:
    runtime = tmp_path / "runtime"; runtime.mkdir()
    nav = runtime / "KF_GINS_Navresult.nav"; std = runtime / "KF_GINS_STD.txt"
    nav.write_text("nav"); std.write_text("std")
    seal = tmp_path / "seal"; seal.mkdir()
    rows = [
        {"run_id": "RUN_00001", "run_root": str(runtime), "relative_path": path.name,
         "size_bytes": path.stat().st_size, "sha256": SHA, "terminal_status": "COMPLETED_EVALUABLE"}
        for path in (nav, std)
    ]
    with (seal / "OUTPUT_HASH_MANIFEST.csv").open("w", newline="") as handle:
        writer = __import__("csv").DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (seal / "OUTPUT_SEAL_JOURNAL.json").write_text(json.dumps({
        "sealed_before_offline_trace": True, "trace_open_count_before_seal": 0,
        "manifest_sha256": SHA,
    }))
    original = evaluator.sha256_file
    def guarded(path):
        if Path(path) in {nav, std, seal / "OUTPUT_HASH_MANIFEST.csv"}:
            raise AssertionError("trusted evaluator hashed sealed runtime evidence")
        return original(path)
    monkeypatch.setattr(evaluator, "sha256_file", guarded)
    gate = evaluator._seal_gate(seal, trusted_direct=True)
    evaluator._revalidate_run_inputs(runtime, "RUN_00001", gate, trusted_direct=True)
