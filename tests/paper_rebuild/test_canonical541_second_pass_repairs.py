from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

import legsa_gins.paper_rebuild.canonical541.runner as runner
from legsa_gins.paper_rebuild.canonical541.authorization import STAGE_ID
from legsa_gins.paper_rebuild.canonical541.preparation import scientific_method_runtime_hash
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS
from legsa_gins.paper_rebuild.canonical541.provider_reuse import (
    CONFIG_PATHS, GENERATOR_PATHS, EXPECTED_CASE_IDS, EXPECTED_SOURCE_IDS,
    decide_provider_reuse,
)
from legsa_gins.paper_rebuild.canonical541.readiness import (
    ReadinessError, derive_compact_readiness_gate,
)
from legsa_gins.paper_rebuild.canonical541.runner import actual_rendered_runtime_config_sha256
from legsa_gins.paper_rebuild.canonical541.authorization import validate_attempt_root


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _counter_manifest(profile: str) -> dict:
    from legsa_gins.paper_rebuild.canonical541.readiness import _expected_flags
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


def _readiness_fixture(tmp_path: Path):
    from legsa_gins.paper_rebuild.canonical541.readiness import CLEAN18_PROFILES, _expected_flags
    freeze = "a" * 40; executable = "b" * 64
    binding = {"stage_id": STAGE_ID, "code_freeze_commit": freeze, "executable_sha256": executable}
    build = _write_json(tmp_path / "build.json", {**binding, "passed": True, "build_type": "Release"})
    tests = _write_json(tmp_path / "tests.json", {**binding, "passed": True, "failed": 0, "paper_rebuild_passed": 410})
    preflight = _write_json(tmp_path / "preflight.json", {**binding, "passed": True, "expected_identity_count": 5951,
                            "duplicate_identity_count": 0, "missing_identity_count": 0,
                            "invalid_algorithm_role_route_count": 0})
    attempt = tmp_path / STAGE_ID / ".attempt_20260808T000000"; attempt.mkdir(parents=True)
    output = tmp_path / "clean18_outputs"; output.mkdir(); seal = tmp_path / "clean18_seal"; seal.mkdir()
    seal_rows = []
    for index, profile in enumerate(CLEAN18_PROFILES, 1):
        root = output / f"{index:02d}_{profile}"; root.mkdir()
        flags = _expected_flags(profile)
        algorithm = {"AB0000": "strong_dual_yaw_EKF", "AB1111": "LegSA_Paper_V1"}.get(profile, profile)
        manifest = {**_counter_manifest(profile), "stage_id": STAGE_ID,
                    "port_role": "canonical541_formal_controlled_degradation_solver",
                    "case_id": "C00_clean_normal", "algorithm_id": algorithm, "trace_used_online": False}
        manifest_path = _write_json(root / "RUN_MANIFEST.json", manifest)
        for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
            path = root / name; path.write_text("1 2 3\n", encoding="utf-8")
        _write_json(root / "CANONICAL541_EXECUTION_PROOF.json", {
            **binding, "terminal_status": "COMPLETED_EVALUABLE", "effective_profile": profile,
            "effective_flags": flags, "case_id": "C00_clean_normal",
            "solver_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "module_counters": runner.module_counters(manifest),
            "output_hashes_before_proof": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt")
            },
        })
        for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
            path = root / name
            seal_rows.append({"algorithm_id": profile, "relative_path": path.relative_to(output).as_posix(),
                              "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "sealed_before_trace": True})
    seal_manifest = seal / "OUTPUT_HASH_MANIFEST.csv"
    _write_csv(seal_manifest, list(seal_rows[0]), seal_rows)
    _write_json(seal / "OUTPUT_SEAL_JOURNAL.json", {**binding, "passed": True, "unique_formal_runs": 18,
                "method_ids": list(CLEAN18_PROFILES), "trace_open_count_before_seal": 0,
                "all_outputs_sealed_before_trace": True,
                "output_hash_manifest_sha256": hashlib.sha256(seal_manifest.read_bytes()).hexdigest()})
    anchor = tmp_path / "anchor"; anchor.mkdir()
    for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
        (anchor / name).write_text("1.0 2.00 3\n", encoding="utf-8")
    ab = output / "03_AB0000"
    return dict(build_artifact=build, test_artifact=tests, preflight_artifact=preflight,
                ab0000_output_root=ab, ab0000_anchor_root=anchor,
                clean18_output_root=output, clean18_seal_root=seal, attempt_root=attempt,
                code_freeze_commit=freeze, executable_sha256=executable)


def test_compact_readiness_is_derived_from_authoritative_roots(tmp_path):
    kwargs = _readiness_fixture(tmp_path)
    result = derive_compact_readiness_gate(
        **kwargs,
    )
    assert result["passed"] is True and result["clean_18_terminal"] == 18
    manifest = Path(kwargs["clean18_output_root"]) / "04_AB0001/RUN_MANIFEST.json"
    bad = json.loads(manifest.read_text()); bad["raw_doppler_update_count"] = 1
    _write_json(manifest, bad)
    with pytest.raises(ReadinessError):
        derive_compact_readiness_gate(**kwargs)


@pytest.mark.parametrize("mutation", ["stage", "freeze", "executable", "identity", "seal", "parity"])
def test_compact_readiness_rejects_wrong_authoritative_evidence(tmp_path, mutation):
    kwargs = _readiness_fixture(tmp_path)
    if mutation in {"stage", "freeze", "executable"}:
        field = {"stage": "stage_id", "freeze": "code_freeze_commit", "executable": "executable_sha256"}[mutation]
        payload = json.loads(Path(kwargs["preflight_artifact"]).read_text()); payload[field] = "wrong"
        _write_json(Path(kwargs["preflight_artifact"]), payload)
    elif mutation == "identity":
        (Path(kwargs["clean18_output_root"]) / "04_AB0001").rename(Path(kwargs["clean18_output_root"]) / "04_P0")
    elif mutation == "seal":
        (Path(kwargs["clean18_output_root"]) / "04_AB0001/KF_GINS_STD.txt").write_text("9\n")
    else:
        (Path(kwargs["ab0000_anchor_root"]) / "KF_GINS_STD.txt").write_text("9\n")
    with pytest.raises(ReadinessError):
        derive_compact_readiness_gate(**kwargs)


@pytest.mark.parametrize("mutation", ["manifest_hash", "proof_counters", "proof_nav", "proof_std"])
def test_compact_readiness_rejects_proof_file_binding_tamper(tmp_path, mutation):
    kwargs = _readiness_fixture(tmp_path)
    proof_path = Path(kwargs["clean18_output_root"]) / "04_AB0001/CANONICAL541_EXECUTION_PROOF.json"
    proof = json.loads(proof_path.read_text())
    if mutation == "manifest_hash":
        proof["solver_manifest_sha256"] = "0" * 64
    elif mutation == "proof_counters":
        proof["module_counters"]["position_update_count"] = 2
    elif mutation == "proof_nav":
        proof["output_hashes_before_proof"]["KF_GINS_Navresult.nav"] = "0" * 64
    else:
        proof["output_hashes_before_proof"]["KF_GINS_STD.txt"] = "0" * 64
    _write_json(proof_path, proof)
    with pytest.raises(ReadinessError):
        derive_compact_readiness_gate(**kwargs)


@pytest.mark.parametrize("filename", ["RUN_MANIFEST.json", "KF_GINS_Navresult.nav", "KF_GINS_STD.txt"])
def test_compact_readiness_rejects_current_file_tamper_even_with_updated_seal(tmp_path, filename):
    kwargs = _readiness_fixture(tmp_path)
    run_root = Path(kwargs["clean18_output_root"]) / "04_AB0001"
    target = run_root / filename
    if filename == "RUN_MANIFEST.json":
        payload = json.loads(target.read_text()); payload["harmless_tamper"] = True
        _write_json(target, payload)
    else:
        target.write_text("4 5 6\n", encoding="utf-8")
        seal_root = Path(kwargs["clean18_seal_root"])
        seal_manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"
        with seal_manifest.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        relative = target.relative_to(Path(kwargs["clean18_output_root"])).as_posix()
        for row in rows:
            if row["relative_path"] == relative:
                row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                row["size_bytes"] = str(target.stat().st_size)
        _write_csv(seal_manifest, list(rows[0]), rows)
        journal_path = seal_root / "OUTPUT_SEAL_JOURNAL.json"
        journal = json.loads(journal_path.read_text())
        journal["output_hash_manifest_sha256"] = hashlib.sha256(seal_manifest.read_bytes()).hexdigest()
        _write_json(journal_path, journal)
    with pytest.raises(ReadinessError, match="proof|solver-manifest"):
        derive_compact_readiness_gate(**kwargs)


def test_scientific_method_hash_is_profile_and_data_mode_bound_without_paths():
    strong = FULL_METHODS[2]
    clean = scientific_method_runtime_hash(strong, "C00_clean_normal", "c" * 64)
    degraded = scientific_method_runtime_hash(strong, "D01_seed_00", "c" * 64)
    assert clean != degraded
    assert clean == scientific_method_runtime_hash(strong, "C00_clean_normal", "c" * 64)


def test_actual_rendered_runtime_hash_normalizes_only_output_and_self_hash():
    first = "stage_id: S\nrun_id: R\nimupath: /a/input\noutputpath: /attempt/one\n"
    second = "stage_id: S\nrun_id: R\nimupath: /a/input\noutputpath: /attempt/two\nactual_rendered_runtime_config_sha256: ignored\n"
    assert actual_rendered_runtime_config_sha256(first) == actual_rendered_runtime_config_sha256(second)
    changed = second.replace("/a/input", "/b/input")
    assert actual_rendered_runtime_config_sha256(first) != actual_rendered_runtime_config_sha256(changed)


def test_attempt_root_rejects_bare_stage(tmp_path):
    stage = tmp_path / STAGE_ID; stage.mkdir()
    with pytest.raises(Exception, match="runtime_root must be exactly"):
        validate_attempt_root(stage)


def test_c00_requires_anchor_parity_only(monkeypatch, tmp_path):
    profiles = tuple(runner.C00_REFERENCE_BY_PROFILE)
    unique = []
    for index, profile in enumerate(profiles):
        root = tmp_path / f"run_{index}"; root.mkdir()
        (root / "RUN_MANIFEST.json").write_text(json.dumps({"port_role": "canonical541_formal_controlled_degradation_solver"}))
        (root / "KF_GINS_Navresult.nav").write_text("same\n" if profile == "AB0000" else profile)
        (root / "KF_GINS_STD.txt").write_text("same\n" if profile == "AB0000" else profile)
        unique.append({"case_id": "C00_clean_normal", "effective_profile": profile,
                       "method_id": f"M{index}", "run_id": f"R{index}", "output_root": str(root),
                       **{field: False for field in runner.FEATURE_FIELDS}})
    anchor = tmp_path / "anchor" / runner.C00_REFERENCE_BY_PROFILE["AB0000"]
    anchor.mkdir(parents=True)
    (anchor / "KF_GINS_Navresult.nav").write_text("same\n")
    (anchor / "KF_GINS_STD.txt").write_text("same\n")
    logical = [{"case_id": "C00_clean_normal", "matrix": "full_algorithm", "method_id": f"F{i:02d}",
                "run_id": f"RF{i}"} for i in range(1, 5)]
    logical += [{"case_id": "C00_clean_normal", "matrix": "internal_ablation", "method_id": f"A{i:02d}",
                 "run_id": ("RF4" if i == 1 else "RF3" if i == 2 else f"RA{i}"),
                 "execution_alias": i in (1, 2)} for i in range(1, 10)]
    monkeypatch.setattr(runner, "validate_terminal_output", lambda row: {
        "terminal_status": "COMPLETED_EVALUABLE", "solver_read_ledger": {"trace_open_count": 0}})
    monkeypatch.setattr(runner, "validate_output_structure", lambda root, require_exact: {
        "nav": {"rows": 1, "finite": True}, "std": {"rows": 1, "finite": True},
        "exact_clean_structure": True})
    monkeypatch.setattr(runner, "validate_method_counters", lambda profile, manifest: {"position_update_count": 1})
    stage = tmp_path / STAGE_ID / ".attempt_20260808T000000"; stage.mkdir(parents=True)
    report = runner.validate_c00_structural_gate(
        unique_runs=unique, logical_rows=logical, clean_ablation_runtime_root=tmp_path / "anchor",
        stage_root=stage, output_path=stage / "gate.json")
    assert report["passed"] is True and report["report_only_profile_count"] == 10
    assert sum(row["parity_required"] for row in report["rows"]) == 1


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def test_provider_reuse_supports_actual_legacy_freeze_schema(monkeypatch, tmp_path):
    repo = tmp_path / "repo"; origin = tmp_path / "origin"; ready = origin / "06_PROVIDER_READY"
    ready.mkdir(parents=True)
    for relative in (*GENERATOR_PATHS, *CONFIG_PATHS):
        path = repo / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(relative)
    generators = {p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in GENERATOR_PATHS}
    configs = {p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in CONFIG_PATHS}
    old_commit = "057c0e24b1550034f95d5b24ea47d04e3ea515d1"
    # Faithful old CANONICAL541_CODE_FREEZE schema: code_freeze_commit is present,
    # embedded generator/config maps are absent.
    freeze = _write_json(tmp_path / "freeze.json", {"code_freeze_commit": old_commit,
                         "stage_id": "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX", "passed": True})
    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.canonical541.provider_reuse.git_object_provider_hashes",
        lambda repo_root, commit: (generators, configs),
    )
    _write_csv(ready / "CANONICAL541_PROVIDER_READY_MANIFEST.csv", ["case_id", "provider_ready"],
               [{"case_id": case_id, "provider_ready": "true"} for case_id in EXPECTED_CASE_IDS])
    _write_csv(ready / "CANONICAL541_EFFECT_VALIDATION_RESULTS.csv", ["case_id", "passed"],
               [{"case_id": case_id, "passed": "true"} for case_id in EXPECTED_CASE_IDS])
    payload = tmp_path / "provider.bin"; payload.write_bytes(b"provider")
    payload_sha = hashlib.sha256(payload.read_bytes()).hexdigest()
    _write_csv(ready / "PROVIDER_SHA256_MANIFEST.csv",
               ["case_id", "source", "sha256", "size_bytes", "resolved_path"],
               [{"case_id": case_id, "source": source, "sha256": payload_sha,
                 "size_bytes": payload.stat().st_size, "resolved_path": str(payload)}
                for case_id in EXPECTED_CASE_IDS for source in EXPECTED_SOURCE_IDS])
    provider_root = origin / "05_PROVIDER_GENERATION"; (provider_root / "FINALIZED").mkdir(parents=True)
    _write_json(ready / "PROVIDER_GATE.json", {"passed": True, "provider_generation": 541,
                "effect_validation": 541, "provider_ready": 541, "raw_mutation": 0, "trace_open_count": 0,
                "finalized_provider_root": str(provider_root / "FINALIZED")})
    for name in ("EFFECT_VALIDATION_DETAIL_TABLE.csv", "EFFECT_VALIDATION_FAILURES.csv",
                 "COMPONENT_VALIDATION_TABLE.csv"):
        (ready / name).write_text("status\npass\n", encoding="utf-8")
    decision = decide_provider_reuse(repo_root=repo, origin_stage=origin,
                                     origin_freeze_path=freeze, new_solver_code_freeze="new",
                                     provider_root=provider_root)
    assert decision["reuse_541_providers"] is True and len(decision["provider_payload_row_hashes"]) == 4328
    sha_manifest = ready / "PROVIDER_SHA256_MANIFEST.csv"
    with sha_manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[-1]["case_id"] = rows[0]["case_id"]; rows[-1]["source"] = rows[0]["source"]
    _write_csv(sha_manifest, list(rows[0]), rows)
    identity_mismatch = decide_provider_reuse(
        repo_root=repo, origin_stage=origin, origin_freeze_path=freeze,
        new_solver_code_freeze="new", provider_root=provider_root,
    )
    assert identity_mismatch["canonical_case_source_identity_closure"] is False
    assert identity_mismatch["regeneration_required"] is True
    rows[-1]["case_id"] = EXPECTED_CASE_IDS[-1]; rows[-1]["source"] = EXPECTED_SOURCE_IDS[-1]
    _write_csv(sha_manifest, list(rows[0]), rows)
    (repo / GENERATOR_PATHS[0]).write_text("changed")
    mismatch = decide_provider_reuse(repo_root=repo, origin_stage=origin,
                                     origin_freeze_path=freeze, new_solver_code_freeze="new",
                                     provider_root=provider_root)
    assert mismatch["reuse_541_providers"] is False and mismatch["regeneration_required"] is True


def test_provider_semantic_path_set_includes_case_and_matrix_contracts():
    assert set(GENERATOR_PATHS) == {
        "src/legsa_gins/paper_rebuild/canonical541/matrix_spec.py",
        "src/legsa_gins/paper_rebuild/canonical541/case_manifest.py",
        "src/legsa_gins/paper_rebuild/canonical541/provider_generator.py",
        "src/legsa_gins/paper_rebuild/canonical541/effect_validation.py",
        "src/legsa_gins/paper_rebuild/canonical541/seed_anchor.py",
        "scripts/paper_rebuild/generate_canonical541_providers.py",
    }


def test_solver_manifest_requires_exact_canonical_role():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert '"port_role": "canonical541_formal_controlled_degradation_solver"' in source
