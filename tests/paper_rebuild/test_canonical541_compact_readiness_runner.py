from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import legsa_gins.paper_rebuild.canonical541.compact_readiness_runner as compact
from legsa_gins.paper_rebuild.canonical541.authorization import RUNTIME_ROLE, STAGE_ID
from legsa_gins.paper_rebuild.canonical541.readiness import CLEAN18_PROFILES, _expected_flags
from legsa_gins.paper_rebuild.canonical541.runner import module_counters, runtime_profile_id


def _counters(profile: str) -> dict:
    flags = _expected_flags(profile); dual = int(flags["dual_yaw"])
    return {
        "position_update_count": 1,
        "receiver_velocity_update_count": int(flags["receiver_velocity"]),
        "dual_yaw_attempt_count": dual, "dual_yaw_accepted_count": dual,
        "yaw_NORMAL": dual, "yaw_DOWNWEIGHT": 0, "yaw_REJECT": 0,
        "raw_doppler_update_count": int(flags["raw_doppler"]),
        "source_aware_evaluation_count": int(flags["source_aware"]),
        "source_aware_weight_changed_count": 0,
        "go2_roll_pitch_update_count": int(flags["go2_rp"]),
        "go2_horizontal_velocity_update_count": int(flags["go2_hv"]),
        "selected_fgo_feedback_update_count": 0, "nine_factor_fgo_update_count": 0,
        "multi_state_qm_update_count": 0, "qa_fallback_count": 0,
        "contact_fk_update_count": 0,
    }


def test_exact_clean18_profiles_flags_and_aliases():
    profiles = compact.clean18_profiles()
    assert tuple(row.effective_profile for row in profiles) == CLEAN18_PROFILES
    assert len(profiles) == len({row.signature for row in profiles}) == 18
    assert profiles[2].method_id == "F03" and profiles[2].name == "strong_dual_yaw_EKF"
    assert profiles[-1].method_id == "F04" and profiles[-1].name == "LegSA_Paper_V1"
    for profile in profiles:
        assert dict(profile.flags) == _expected_flags(profile.effective_profile)


def _fixture(monkeypatch, tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    protocol = repo / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"
    protocol.parent.mkdir(parents=True); protocol.write_text("schema_version: test\n")
    stage = tmp_path / STAGE_ID; attempt = stage / ".attempt_20260808T000000"; attempt.mkdir(parents=True)
    clean = tmp_path / "clean"; anchor = clean / compact.STRONG_ANCHOR_RELATIVE; anchor.mkdir(parents=True)
    for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
        (anchor / name).write_text("1 2 3\n")
    base_root = tmp_path / "base"
    clean_manifest = base_root / "FINAL_V23_CLEAN_CLEAN2R2A/FINAL_V23_CLEAN_INPUT_MANIFEST.json"
    auxiliary = base_root / "FRESH_AUXILIARIES_CLEAN2R2A/CLEAN1R2R1_AUXILIARY_MANIFEST.json"
    clean_manifest.parent.mkdir(parents=True); auxiliary.parent.mkdir(parents=True)
    clean_manifest.write_text("{}\n"); auxiliary.write_text("{}\n")
    local = tmp_path / "paths.local.yaml"; local.write_text("paths: {}\n")
    executable = tmp_path / "solver"; executable.write_bytes(b"solver")
    raw = tmp_path / "raw"; raw.mkdir()
    paths = {"runtime_root": attempt, "code_root": repo, "clean_root": clean,
             "raw_root": raw, "base_provider_root": base_root}
    base = SimpleNamespace(original_provider_paths={name: str(tmp_path / name)
                           for name in ("raw_doppler", "go2_rp", "go2_hv")})
    freeze = "a" * 40
    monkeypatch.setattr(compact, "git_code_state", lambda root: (freeze, False))
    monkeypatch.setattr(compact, "load_execution_authorization", lambda root: {
        "stage_id": STAGE_ID, "protocol_id": compact.PROTOCOL_ID,
        "runtime_role": RUNTIME_ROLE,
    })
    freeze_root = attempt / "01_GIT_FREEZE"; freeze_root.mkdir()
    (freeze_root / "CANONICAL541_CODE_FREEZE.json").write_text(json.dumps({
        "stage_id": STAGE_ID, "code_freeze_commit": freeze,
        "executable_path": str(executable.resolve()),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "provider_generation_count_at_freeze": 0, "formal_solver_run_count_at_freeze": 0,
        "trace_open_count_at_freeze": 0, "passed": True,
    }) + "\n")

    def fake_materialize(*, profile, output_root, **kwargs):
        output_root.mkdir(parents=True)
        payload = {"method_id": profile.method_id, "method_name": profile.name,
                   "effective_profile": profile.effective_profile,
                   "effective_flags": dict(profile.flags)}
        (output_root / "METHOD_BOUND_INPUT_MANIFEST.json").write_text(json.dumps(payload) + "\n")
        return payload

    monkeypatch.setattr(compact, "materialize_method_bound_inputs", fake_materialize)
    monkeypatch.setattr(compact, "build_runtime_config", lambda **kwargs: "stage_id: test\noutputpath: out\n")

    calls = []
    def fake_executor(*, output_root, profile, **kwargs):
        calls.append(profile.effective_profile)
        root = Path(output_root)
        manifest = {**_counters(profile.effective_profile), "stage_id": STAGE_ID,
                    "port_role": RUNTIME_ROLE, "case_id": compact.CASE_ID,
                    "algorithm_id": runtime_profile_id(profile), "trace_used_online": False}
        manifest_path = root / "RUN_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest) + "\n")
        for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
            (root / name).write_text("1 2 3\n")
        return {
            "terminal_status": "COMPLETED_EVALUABLE",
            "effective_profile": profile.effective_profile,
            "effective_flags": dict(profile.flags), "case_id": compact.CASE_ID,
            "solver_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "module_counters": module_counters(manifest),
            "output_hashes_before_proof": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt")
            },
            "solver_read_ledger": {"trace_open_count": 0},
        }
    return repo, local, paths, attempt, executable, freeze, base, fake_executor, calls


def _complete(monkeypatch, tmp_path):
    fixture = _fixture(monkeypatch, tmp_path)
    repo, local, paths, attempt, executable, freeze, base, executor, _ = fixture
    report = compact.execute_compact_readiness(
        repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
        executable=executable, code_freeze_commit=freeze, base=base, executor=executor,
    )
    return fixture, report


def test_one_shot_run_emits_readiness_compatible_proofs_and_seal(monkeypatch, tmp_path):
    repo, local, paths, attempt, executable, freeze, base, executor, calls = _fixture(monkeypatch, tmp_path)
    report = compact.execute_compact_readiness(
        repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
        executable=executable, code_freeze_commit=freeze, base=base, executor=executor,
    )
    assert report["passed"] is True and report["clean18_terminal"] == 18
    assert calls[0] == "AB0000" and set(calls) == set(CLEAN18_PROFILES)
    assert report["trace_reads_before_seal"] == 0 and report["technical_retries"] == 0
    assert report["clean18_flags"] == {
        profile.effective_profile: dict(profile.flags) for profile in compact.clean18_profiles()
    }
    assert report["logical_aliases"] == {"AB1111": ["F04", "A01"], "AB0000": ["F03", "A02"]}
    seal = Path(report["seal_root"]) / "OUTPUT_SEAL_JOURNAL.json"
    assert json.loads(seal.read_text())["runtime_role"] == RUNTIME_ROLE
    resumed = compact.execute_compact_readiness(
        repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
        executable=executable, code_freeze_commit=freeze, base=base,
        executor=lambda **kwargs: pytest.fail("sealed resume must not launch"), resume=True,
    )
    assert resumed == report
    journal = json.loads(seal.read_text()); journal["schema_version"] = "paper_rebuild.clean2r2a1_output_seal.v1"
    seal.write_text(json.dumps(journal) + "\n")
    with pytest.raises(compact.CompactReadinessRunError, match="seal journal binding drift"):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
            executable=executable, code_freeze_commit=freeze, base=base,
            executor=lambda **kwargs: pytest.fail("old schema must not launch"), resume=True,
        )


def test_authorization_and_code_freeze_gate_fail_before_output_or_lock(monkeypatch, tmp_path):
    repo, local, paths, attempt, executable, freeze, base, executor, _ = _fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(compact, "load_execution_authorization", lambda root: {
        "stage_id": STAGE_ID, "protocol_id": compact.PROTOCOL_ID,
        "runtime_role": "wrong_role",
    })
    with pytest.raises(compact.CompactReadinessRunError, match="authorization identity drift"):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
            executable=executable, code_freeze_commit=freeze, base=base, executor=executor,
        )
    assert not (attempt / compact.READINESS_DIRECTORY).exists()
    assert not (attempt / "compact_readiness_runner.lock").exists()

    monkeypatch.setattr(compact, "load_execution_authorization", lambda root: {
        "stage_id": STAGE_ID, "protocol_id": compact.PROTOCOL_ID,
        "runtime_role": RUNTIME_ROLE,
    })
    gate = attempt / "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json"
    payload = json.loads(gate.read_text()); payload["provider_generation_count_at_freeze"] = 1
    gate.write_text(json.dumps(payload) + "\n")
    with pytest.raises(Exception, match="code-freeze evidence gate failed"):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
            executable=executable, code_freeze_commit=freeze, base=base, executor=executor,
        )
    assert not (attempt / compact.READINESS_DIRECTORY).exists()
    assert not (attempt / "compact_readiness_runner.lock").exists()


def test_code_freeze_requires_exact_executable_absolute_path(monkeypatch, tmp_path):
    repo, local, paths, attempt, executable, freeze, base, executor, _ = _fixture(monkeypatch, tmp_path)
    gate = attempt / "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json"
    payload = json.loads(gate.read_text()); payload["executable_path"] = str(tmp_path / "other_solver")
    gate.write_text(json.dumps(payload) + "\n")
    with pytest.raises(compact.CompactReadinessRunError, match="executable path binding"):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
            executable=executable, code_freeze_commit=freeze, base=base, executor=executor,
        )
    assert not (attempt / compact.READINESS_DIRECTORY).exists()


@pytest.mark.parametrize(
    ("tamper", "match"),
    [
        ("local_config", "seal journal binding drift"),
        ("schema", "report binding drift"),
        ("role", "report binding drift"),
        ("output_root", "report binding drift"),
        ("seal_root", "report binding drift"),
        ("seal_record", "report binding drift"),
        ("seal_manifest_hash", "report binding drift"),
        ("seal_journal_hash", "report binding drift"),
        ("aliases", "report binding drift"),
        ("flags", "report binding drift"),
        ("no_rerun", "report binding drift"),
        ("tuning", "report binding drift"),
    ],
)
def test_sealed_resume_rejects_binding_tamper(monkeypatch, tmp_path, tamper, match):
    fixture, report = _complete(monkeypatch, tmp_path)
    repo, local, paths, attempt, executable, freeze, base, _, _ = fixture
    report_path = attempt / compact.READINESS_DIRECTORY / "COMPACT_READINESS_RUN_REPORT.json"
    payload = json.loads(report_path.read_text())
    if tamper == "local_config":
        local.write_text("paths: {tampered: true}\n")
    elif tamper == "schema":
        payload["schema_version"] = "paper_rebuild.canonical541.compact_readiness_run.v0"
    elif tamper == "role":
        payload["runtime_role"] = "clean1_formal_four_method_solver"
    elif tamper == "output_root":
        payload["output_root"] = str(tmp_path / "wrong_output")
    elif tamper == "seal_root":
        payload["seal_root"] = str(tmp_path / "wrong_seal")
    elif tamper == "seal_record":
        payload["seal"]["sealed_file_count"] = 71
    elif tamper == "seal_manifest_hash":
        payload["seal_manifest_sha256"] = "0" * 64
    elif tamper == "seal_journal_hash":
        payload["seal_journal_sha256"] = "0" * 64
    elif tamper == "aliases":
        payload["logical_aliases"]["AB0000"] = ["F03"]
    elif tamper == "flags":
        payload["clean18_flags"]["AB0000"]["raw_doppler"] = True
    elif tamper == "no_rerun":
        payload["metric_driven_rerun"] = True
    elif tamper == "tuning":
        payload["per_case_tuning"] = True
    if tamper != "local_config":
        report_path.write_text(json.dumps(payload) + "\n")
    with pytest.raises(compact.CompactReadinessRunError, match=match):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
            executable=executable, code_freeze_commit=freeze, base=base,
            executor=lambda **kwargs: pytest.fail("invalid resume must not launch"), resume=True,
        )


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_exact_seal_rejects_non_exact_path_closure(monkeypatch, tmp_path, mutation):
    fixture, report = _complete(monkeypatch, tmp_path)
    _, local, _, _, executable, freeze, _, _, _ = fixture
    seal_root = Path(report["seal_root"])
    manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"
    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle)); fields = list(rows[0])
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append({**rows[-1], "relative_path": "unexpected/EXTRA.json"})
    else:
        rows[-1] = dict(rows[0])
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    with pytest.raises(compact.CompactReadinessRunError, match="exact 72-file closure"):
        compact.validate_compact_readiness_seal(
            output_root=report["output_root"], seal_root=seal_root, code_freeze=freeze,
            executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            local_config_sha256=hashlib.sha256(local.read_bytes()).hexdigest(),
        )


@pytest.mark.parametrize(
    "name",
    ["KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "RUN_MANIFEST.json",
     "CANONICAL541_EXECUTION_PROOF.json"],
)
def test_exact_seal_rejects_each_sealed_file_class_tamper(monkeypatch, tmp_path, name):
    fixture, report = _complete(monkeypatch, tmp_path)
    _, local, _, _, executable, freeze, _, _, _ = fixture
    target = Path(report["output_root"]) / "03_AB0000" / name
    target.write_bytes(target.read_bytes() + b"tamper\n")
    with pytest.raises(compact.CompactReadinessRunError, match="sealed file drift"):
        compact.validate_compact_readiness_seal(
            output_root=report["output_root"], seal_root=report["seal_root"],
            code_freeze=freeze,
            executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            local_config_sha256=hashlib.sha256(local.read_bytes()).hexdigest(),
        )


def test_rejects_clean2_root_freeze_drift_and_duplicate_lock(monkeypatch, tmp_path):
    repo, local, paths, attempt, executable, freeze, base, executor, _ = _fixture(monkeypatch, tmp_path)
    clean2 = tmp_path / "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME"
    clean2.mkdir()
    with pytest.raises(Exception, match="runtime_root must be exactly"):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=clean2,
            executable=executable, code_freeze_commit=freeze, base=base, executor=executor,
        )
    with pytest.raises(compact.CompactReadinessRunError, match="exact clean code freeze"):
        compact.execute_compact_readiness(
            repo_root=repo, local_config=local, paths=paths, attempt_root=attempt,
            executable=executable, code_freeze_commit="b" * 40, base=base, executor=executor,
        )
    first = compact._acquire_lock(attempt, freeze, hashlib.sha256(executable.read_bytes()).hexdigest())
    try:
        with pytest.raises(compact.CompactReadinessRunError, match="lock already exists"):
            compact._acquire_lock(attempt, freeze, hashlib.sha256(executable.read_bytes()).hexdigest())
    finally:
        compact._release_lock(first)


def test_cli_does_not_reference_legacy_reporting_runner():
    source = (Path(__file__).resolve().parents[2] /
              "scripts/paper_rebuild/run_canonical541_compact_readiness.py").read_text()
    assert "by2_algorithm_runner" not in source
    assert "--local-config" in source and "--attempt-root" in source
    assert "--code-freeze-commit" in source and "--executable" in source
