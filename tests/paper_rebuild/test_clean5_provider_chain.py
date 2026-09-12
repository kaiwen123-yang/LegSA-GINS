"""C-03 adapter contract tests use synthetic files only, never real raw data."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from legsa_gins.paper_rebuild.clean1r2r1_formal import rebase_auxiliary_time_csv
from legsa_gins.paper_rebuild.clean5_sequence import generation_audit as ga
from legsa_gins.paper_rebuild.clean5_sequence import runtime_config as rc


def test_25200_rebase_preserves_source_fields(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("time,source_time,value\n28354.125,468572.000,1.2500\n28355.125,468573.000,2.5000\n")
    target = tmp_path / "rebased.csv"
    report = rebase_auxiliary_time_csv(source, target, offset_seconds=25200.0)
    assert report["time_column_only_transformed"] is True
    assert report["source_time_column_preserved"] is True
    lines = target.read_text().splitlines()
    assert [float(line.split(",")[0]) for line in lines[1:]] == [3154.125, 3155.125]
    assert [line.split(",")[1:] for line in lines[1:]] == [["468572.000", "1.2500"], ["468573.000", "2.5000"]]


def test_exclusive_manifest_does_not_overwrite(tmp_path):
    path = tmp_path / "manifest.json"
    ga.write_json_exclusive(path, {"old": True})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        ga.write_json_exclusive(path, {"old": False})
    assert path.read_bytes() == before


def test_checkpoint_path_identity_is_sequence_specific():
    rows = {f"by3/file_{i}": {"sha256": f"{i:064x}"} for i in range(22)}
    lock = {"sha256": "a" * 64, "rows": rows}
    report = {"schema_version": "paper_rebuild.final_v23_external_raw_checkpoint.v1",
              "audit_phase": "pre_generation", "raw_hash_lock_sha256": lock["sha256"],
              "expected": 22, "verified": 22, "missing": 0, "mismatch": 0,
              "symlink_escape": 0, "raw_mutation": 0, "passed": True,
              "trace_read_role": "outer_raw_integrity_hash_audit_only", "trace_provider_or_solver_input": False,
              "verified_hashes": {key: row["sha256"] for key, row in rows.items()}}
    assert ga.validate_checkpoint(report, phase="pre_generation", lock=lock) == report["verified_hashes"]
    report["verified_hashes"] = {key.replace("by3", "by1"): row["sha256"] for key, row in rows.items()}
    with pytest.raises(RuntimeError, match="checkpoint"):
        ga.validate_checkpoint(report, phase="pre_generation", lock=lock)


def test_checkpoint_audit_rejects_second_read_and_raw_write(tmp_path):
    root = tmp_path / "raw"
    source = root / "trace_example.csv"
    row = {"path": str(source), "flags": "O_RDONLY|O_CLOEXEC", "return_code": 3}
    assert ga.audit_records([row], root, {source}, checkpoint_phase=True)["pass"]
    assert not ga.audit_records([row, row], root, {source}, checkpoint_phase=True)["pass"]
    assert not ga.audit_records([{**row, "flags": "O_RDWR"}], root, {source}, checkpoint_phase=True)["pass"]


@pytest.mark.parametrize("name", ["trace_example.csv", "example.bag", "example.fpl"])
def test_generation_audit_forbids_hash_only_inputs(tmp_path, name):
    root = tmp_path / "raw"
    source = root / name
    row = {"path": str(source), "flags": "O_RDONLY", "return_code": 3}
    assert not ga.audit_records([row], root, {source}, checkpoint_phase=False)["pass"]


def test_checkpoint_session_separates_pre_and_post_counts(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    audit = tmp_path / "audit"
    log = tmp_path / "trace.log"
    source = raw / "file.csv"
    lines = []
    for phase in ("pre_generation", "post_generation"):
        lines.append(f'42 openat(AT_FDCWD, "{audit / (phase + "_BEGIN")}", O_WRONLY|O_CREAT|O_EXCL, 0666) = 3')
        lines.append(f'42 openat(AT_FDCWD, "{source}", O_RDONLY|O_CLOEXEC) = 3')
    log.write_text("\n".join(lines) + "\n")
    registry = SimpleNamespace(raw_root=raw, code_root=tmp_path)
    monkeypatch.setattr(ga, "selected_lock", lambda *_: {"rows": {"file.csv": {}}})
    report = ga.audit_checkpoint_session(log, registry, object(), audit)
    assert report["pass"] and report["raw_open_count"] == 2
    assert report["pre_generation"]["per_file_open_count"][str(source)] == 1
    assert report["post_generation"]["per_file_open_count"][str(source)] == 1
    # Two pre reads and no post read must fail despite the same overall count.
    log.write_text("\n".join([lines[0], lines[1], lines[1], lines[2]]) + "\n")
    assert not ga.audit_checkpoint_session(log, registry, object(), audit)["pass"]


def test_scientific_hash_uses_same_normalization_as_canonical():
    from legsa_gins.paper_rebuild.canonical541.runner import scientific_runtime_config_hash
    text = "run_id: run\nrun_label: label\ncase_id: C00\nalgorithm_id: AB0000\noutputpath: /output\nimupath: /imu\ngnsspath: /gnss\nstarttime: 66\n"
    assert rc.scientific_runtime_config_hash(text) == scientific_runtime_config_hash(text)


def test_runtime_nonwhitelisted_override_raises():
    with pytest.raises(rc.RuntimeConfigError):
        rc.apply_runtime_overrides({"starttime": 66.0, "antlever": [0.03, 0.03, -0.3]}, {"antlever": [0, 0, 0]})
    assert rc.apply_runtime_overrides({"starttime": 66.0}, {"starttime": 411.0}) == {"starttime": 411.0}


@pytest.mark.parametrize("dataset,first,base,offset", [
    ("BY2", 1772784055, 1772784000.0, 28800.0),
    ("BY2H", 1772784400, 1772784000.0, 28800.0),
    ("BY2O", 1772783543, 1772780400.0, 25200.0),
])
def test_source_base_time_and_rebase_contract_agree(tmp_path, dataset, first, base, offset):
    from legsa_gins.paper_rebuild.clean5_sequence.provider_contract import SequenceProviderError, validate_sequence_time
    status = tmp_path / "gnss1-status.csv"
    status.write_text(f"sys_stamp.secs,sys_stamp.nsecs,pos_valid\n{first-5000},0,false\n{first},200000000,true\n")
    sequence = SimpleNamespace(dataset_id=dataset, fix_root=tmp_path)
    contract = {"time_contract": {"base_time": base, "utc_day_midnight": 1772755200.0,
                                  "auxiliary_rebase_offset_seconds": offset},
                "window_contract": {"t_start": 1.0, "t_end": 10.0}}
    result = validate_sequence_time(sequence, contract)
    assert result["base_time"] - result["utc_day_midnight"] == offset
    contract["time_contract"]["auxiliary_rebase_offset_seconds"] += 3600
    with pytest.raises(SequenceProviderError, match="rebase"):
        validate_sequence_time(sequence, contract)


def test_existing_provider_directory_fails_before_source_reads(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean5_sequence import provider_chain as pc
    destination = tmp_path / "02_PROVIDER_FREEZE"
    destination.mkdir()
    monkeypatch.setattr(pc, "validate_sequence_time", lambda *_: pytest.fail("must not read raw"))
    with pytest.raises(FileExistsError):
        pc.generate_sequence_payloads(None, None, {}, destination)
    assert list(destination.iterdir()) == []


def test_physical_gate_failure_prevents_later_providers(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean5_sequence import provider_chain as pc
    sequence = SimpleNamespace(dataset_id="BY2H", data_mode="real_by2h_raw", fix_root=tmp_path)
    registry = SimpleNamespace(code_root=tmp_path)
    contract = {"identity": {"dataset_id": "BY2H", "data_mode": "real_by2h_raw"}}
    monkeypatch.setattr(pc, "validate_frozen_parameters", lambda *_: {})
    monkeypatch.setattr(pc, "validate_sequence_time", lambda *_: {"base_time": 0})
    monkeypatch.setattr(pc.providers, "build_physical_dual_yaw_provider", lambda *_, **kw: (
        [{"time": 1.0, "baseline_length_m": 4.0, "physical_in_band": False}],
        {"physical_baseline_gate_pass": False, "median_baseline_length_m": 4.0,
         "p05_baseline_length_m": 4.0, "p95_baseline_length_m": 4.0}))
    monkeypatch.setattr(pc, "_exact_runtime_inputs", lambda *_: pytest.fail("generation continued after physical FAIL"))
    destination = tmp_path / "02_PROVIDER_FREEZE"
    with pytest.raises(pc.SequenceProviderError, match="physical dual-yaw gate FAILED"):
        pc.generate_sequence_payloads(registry, sequence, contract, destination)
    assert {p.name for p in destination.iterdir()} == {"DUAL_YAW_PHYSICAL_AUDIT.json", "YAW_PHYSICAL_GATE.json"}
    assert json.loads((destination / "YAW_PHYSICAL_GATE.json").read_text())["four_meter_band_epoch_count"] == 1


def test_auxiliary_changes_to_common_inputs_fail(tmp_path):
    from legsa_gins.paper_rebuild.clean5_sequence import provider_chain as pc
    artifacts = {}
    for role in ("imu_runtime_input", "gnss_runtime_input"):
        p = tmp_path / role
        p.write_text("1 2 3\n")
        artifacts[role] = {"path": str(p), "sha256": ga.sha256_file(p)}
    assert all(row["unchanged"] for row in pc._assert_runtime_input_hashes(artifacts).values())
    Path(artifacts["gnss_runtime_input"]["path"]).write_text("1 2 4\n")
    with pytest.raises(pc.SequenceProviderError, match="modified a sealed"):
        pc._assert_runtime_input_hashes(artifacts)


def test_by2_hash_mismatch_fails_with_first_difference(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean5_sequence import provider_parity as pp
    providers, references = {}, {}
    for role in (*pp.EXPECTED_BYTE_PROVIDER_HASHES, "raw_doppler_provider"):
        p = tmp_path / (role + ".actual")
        ref = tmp_path / (role + ".reference")
        text = "time,value\n1,2\n" if role.startswith("go2_") else "1 2\n"
        p.write_text(text)
        ref.write_text(text.replace("2", "3"))
        providers[role] = {"path": str(p)}
        references[role] = ref
    monkeypatch.setattr(pp, "EXPECTED_BYTE_PROVIDER_HASHES",
                        {role: ga.sha256_file(references[role]) for role in pp.EXPECTED_BYTE_PROVIDER_HASHES})
    monkeypatch.setattr(pp, "compute_raw_doppler_solver_semantic_sha256", lambda _: pp.EXPECTED_SOLVER_SEMANTIC_SHA256)
    monkeypatch.setattr(pp, "audit_cpp_provenance_consumption", lambda _: {"passed": True})
    called = []
    def named_audit(**kwargs):
        called.append(kwargs)
        return {"passed": True}
    monkeypatch.setattr(pp, "audit_raw_doppler_minimum_sufficient_parity", named_audit)
    report = tmp_path / "BY2_PROVIDER_PARITY_GATE.json"
    with pytest.raises(pp.SequenceProviderError, match="parity FAILED"):
        pp.validate_by2_parity({"dataset_id": "BY2", "providers": providers}, references, tmp_path, report)
    payload = json.loads(report.read_text())
    assert payload["passed"] is False and len(called) == 1
    diff = payload["byte_provider_gates"]["imu_runtime_input"]["first_difference"]
    assert (diff["time"], diff["column"], diff["expected"], diff["actual"]) == ("1", 2, "3", "2")


def test_first_difference_rejects_damaged_reference(tmp_path):
    from legsa_gins.paper_rebuild.clean5_sequence.provider_parity import verified_first_difference
    ref = tmp_path / "reference"
    actual = tmp_path / "actual"
    ref.write_text("1 2\n")
    expected = ga.sha256_file(ref)
    ref.write_text("1 9\n")
    actual.write_text("1 3\n")
    result = verified_first_difference(ref, actual, expected_hash=expected)
    assert result["status"] == "FROZEN_REFERENCE_INTEGRITY_FAILED"
    assert "column" not in result
