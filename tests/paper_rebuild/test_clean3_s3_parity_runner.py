import csv
import json
import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean3_math_repair as s3
from legsa_gins.paper_rebuild.final_v23_clean_parity import active_runtime_config
from legsa_gins.paper_rebuild.manifest import sha256_file


ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _replace(text: str, values: dict[str, str]) -> str:
    rows = []
    found = set()
    for row in text.splitlines():
        key = row.split(":", 1)[0].strip() if ":" in row else ""
        if key in values:
            rows.append(f"{key}: {values[key]}")
            found.add(key)
        else:
            rows.append(row)
    rows.extend(f"{key}: {value}" for key, value in values.items() if key not in found)
    return "\n".join(rows) + "\n"


@pytest.fixture(scope="module")
def loader_harness(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("clean3_loader")
    source = tmp / "main.cpp"
    source.write_text(
        '#include <exception>\n#include <iostream>\n'
        '#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc, char** argv) { try { auto o = '
        'legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]); '
        'std::cout << o.algorithm_id << " " << o.port_role; return 0; '
        '} catch (const std::exception& e) { std::cerr << e.what(); return 2; }}\n',
        encoding="utf-8",
    )
    binary = tmp / "loader_harness"
    subprocess.run([
        "g++", "-std=c++17", "-I", str(ROOT / "cpp/legsa_v23_port_core/include"),
        str(ROOT / "cpp/legsa_v23_port_core/src/common/types.cpp"),
        str(ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp"),
        str(ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp"),
        str(source), "-o", str(binary),
    ], check=True)
    return binary


def _run_loader(binary: Path, tmp_path: Path, text: str) -> subprocess.CompletedProcess[str]:
    config = tmp_path / "config.yaml"
    config.write_text(text, encoding="utf-8")
    return subprocess.run([str(binary), str(config)], capture_output=True, text=True, check=False)


def _clean2_config(tmp_path: Path) -> str:
    common = active_runtime_config(
        tmp_path / "imu", tmp_path / "gnss", tmp_path / "out",
        method_id="strong_dual_yaw_EKF", run_id="AB0000",
    )
    return _replace(common, {
        "stage_id": s3.PARENT_PROVIDER_STAGE_ID,
        "protocol_id": s3.PARENT_PROVIDER_PROTOCOL_ID,
        "data_mode": "real_clean",
        "algorithm_id": "AB0000",
        "ablation_variant": "AB0000",
    })


def test_loader_extension_is_exact_and_fail_closed(loader_harness: Path, tmp_path: Path) -> None:
    old = _clean2_config(tmp_path)
    accepted_old = _run_loader(loader_harness, tmp_path, old)
    assert accepted_old.returncode == 0, accepted_old.stderr
    assert accepted_old.stdout == "AB0000 clean2r2a_formal_clean_ablation_solver"

    clean3 = s3.build_s3_ab0000_config(tmp_path / "imu", tmp_path / "gnss", tmp_path / "out")
    accepted = _run_loader(loader_harness, tmp_path, clean3)
    assert accepted.returncode == 0, accepted.stderr
    assert accepted.stdout == "AB0000 clean3_s3_ab0000_parity_solver"

    invalid = [
        _replace(clean3, {"algorithm_id": "AB0001"}),
        _replace(old, {"clean3_s3_ab0000_parity_mode": "true"}),
        "\n".join(row for row in clean3.splitlines()
                    if not row.startswith("clean3_s3_ab0000_parity_mode:")) + "\n",
        _replace(clean3, {"clean1_formal_mode": "false"}),
    ]
    for text in invalid:
        rejected = _run_loader(loader_harness, tmp_path, text)
        assert rejected.returncode == 2
        assert "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH" in rejected.stderr


@pytest.fixture
def fake_s3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "clean3@example.invalid")
    _git(repo, "config", "user.name", "CLEAN3 Test")
    for relative in (s3.RUNTIME_COUNTER_PATH, s3.LOADER_EXTENSION_PATH):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"repair bytes for {relative}\n", encoding="utf-8")
    counter_test = repo / "tests/paper_rebuild/test_clean3r2_counter_contract_routing.py"
    counter_test.parent.mkdir(parents=True, exist_ok=True)
    counter_test.write_bytes((ROOT / counter_test.relative_to(repo)).read_bytes())
    (repo / "docs").mkdir()
    (repo / "docs/context.md").write_text("context\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "s2 repair")
    repair = _git(repo, "rev-parse", "HEAD")
    prior_tree = _git(repo, "rev-parse", "HEAD:cpp")
    (repo / "docs/context.md").write_text("CLEAN3 failed attempt terminal\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "B0 closeout")
    b0 = _git(repo, "rev-parse", "HEAD")
    for relative in s3.A0_CHANGED_PATHS:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"A0 authorization for {relative}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "A0 amendment")
    amendment_parent = _git(repo, "rev-parse", "HEAD")
    for relative in s3.S0_CODE_FREEZE_CHANGED_PATHS:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "CLEAN3R3 C1 code freeze")
    code_freeze = _git(repo, "rev-parse", "HEAD")
    for relative in s3.RUNNER_FREEZE_CHANGED_PATHS:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_git(ROOT, "show", f"{s3.REJECTED_RUNNER_FREEZE_COMMIT}:{relative}"),
                          encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "preserved CLEAN3R3 C2 runner freeze")
    rejected_runner_freeze = _git(repo, "rev-parse", "HEAD")
    for relative in s3.C2R1_CHANGED_PATHS:
        (repo / relative).write_text(_git(ROOT, "show", f"{s3.C2R1_COMMIT}:{relative}"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "preserved CLEAN3R3 C2R1 runner freeze")
    c2r1 = _git(repo, "rev-parse", "HEAD")
    for relative in s3.C2R2_CHANGED_PATHS:
        (repo / relative).write_text(_git(ROOT, "show", f"{s3.C2R2_COMMIT}:{relative}"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "preserved CLEAN3R3 C2R2 runner freeze")
    c2r2 = _git(repo, "rev-parse", "HEAD")
    for relative in s3.C2R3_CHANGED_PATHS:
        (repo / relative).write_text(_git(ROOT, "show", f"{s3.C2R3_COMMIT}:{relative}"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "preserved CLEAN3R3 C2R3 runner freeze")
    c2r3 = _git(repo, "rev-parse", "HEAD")
    for relative in s3.C2R4_CHANGED_PATHS:
        (repo / relative).write_text(_git(ROOT, "show", f"{s3.C2R4_COMMIT}:{relative}"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "preserved CLEAN3R3 C2R4 runner freeze")
    c2r4 = _git(repo, "rev-parse", "HEAD")
    for relative in s3.C2R5_CHANGED_PATHS:
        (repo / relative).write_text(_git(ROOT, "show", f"{s3.C2R5_COMMIT}:{relative}"), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "preserved CLEAN3R3 C2R5 runner freeze")
    c2r5 = _git(repo, "rev-parse", "HEAD")
    for relative in s3.C2R6_CHANGED_PATHS:
        (repo / relative).write_bytes((ROOT / relative).read_bytes())
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "CLEAN3R3 C2R6 runner freeze")
    runner_freeze = _git(repo, "rev-parse", "HEAD")

    monkeypatch.setattr(s3, "REPAIR_IMPLEMENTATION_COMMIT", repair)
    monkeypatch.setattr(s3, "B0_COMMIT", b0)
    monkeypatch.setattr(s3, "AMENDMENT_PARENT_HEAD", amendment_parent)
    monkeypatch.setattr(s3, "CODE_FREEZE_COMMIT", code_freeze)
    monkeypatch.setattr(s3, "REJECTED_RUNNER_FREEZE_COMMIT", rejected_runner_freeze)
    monkeypatch.setattr(s3, "C2R1_COMMIT", c2r1)
    monkeypatch.setattr(s3, "C2R2_COMMIT", c2r2)
    monkeypatch.setattr(s3, "C2R3_COMMIT", c2r3)
    monkeypatch.setattr(s3, "C2R4_COMMIT", c2r4)
    monkeypatch.setattr(s3, "C2R5_COMMIT", c2r5)
    monkeypatch.setattr(s3, "PRIOR_REVIEWED_CPP_TREE", prior_tree)
    authorization_path = repo / s3.AUTHORIZATION_PATH
    authorization_path.parent.mkdir(parents=True, exist_ok=True)
    authorization_path.write_text("CLEAN3R3 authorization\n", encoding="utf-8")
    authorization_paths = (s3.FREEZE_PATH, s3.AUTHORIZATION_PATH)
    for relative in ():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"authorization governance for {relative}\n", encoding="utf-8")
    freeze_path = repo / s3.FREEZE_PATH
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    freeze = {
        "schema_version": "paper_rebuild.clean3r3_s3_execution_freeze.v1",
        "stage_id": s3.STAGE_ID, "protocol_id": s3.PROTOCOL_ID,
        "case_id": s3.CASE_ID, "algorithm_id": s3.METHOD_ID, "run_id": s3.RUN_ID,
        "code_freeze_commit": code_freeze,
        "runner_freeze_commit": runner_freeze,
        "repair_implementation_commit": repair,
        "b0_commit": b0,
        "amendment_parent_head": amendment_parent,
        "failed_attempt_stage_id": s3.FAILED_ATTEMPT_STAGE_ID,
        "failed_attempt_terminal": s3.FAILED_ATTEMPT_TERMINAL,
        "failed_attempt_parity": s3.FAILED_ATTEMPT_PARITY,
        "failed_attempt_execution_commit": s3.FAILED_ATTEMPT_EXECUTION_COMMIT,
        "failed_attempt_runner_freeze_commit": s3.FAILED_ATTEMPT_RUNNER_FREEZE_COMMIT,
        "final_cpp_tree": _git(repo, "rev-parse", "HEAD:cpp"),
        "tracked_file_sha256": {relative: sha256_file(repo / relative) for relative in s3.FROZEN_CODE_PATHS},
        "authorization_document": s3.AUTHORIZATION_PATH,
        "authorization_sha256": sha256_file(authorization_path),
        "authorization_hash_algorithm": "sha256",
        "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
        "g_c2": "REPORTING_ONLY",
        "g_c3": "HARD_UNCHANGED",
        "sealed_governance_preflight_required": True,
        "authorization_commit_paths": list(authorization_paths),
        "execution_authorization": {
            "s3_solver_allowed_now": True,
            "maximum_solver_executions": 1,
            "evaluator_allowed_now": False,
            "reference_trace_allowed_now": False,
            "canonical_541_allowed_now": False,
            "provider_regeneration_allowed_now": False,
            "retry_allowed_now": False,
        },
        "old_attempt_overwritten": False,
        "ready_for_s4": False,
        "ready_for_paper_claims": False,
    }
    freeze_path.write_text(json.dumps(freeze, sort_keys=True), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "authorize CLEAN3R3 S3")
    proof = {"root": "synthetic-preflight", "attempt_id": "ATTEMPT_000001", "attempt_ordinal": 1,
             "claim_sha256": "c" * 64, "terminal_sha256": "d" * 64,
             "report_sha256": "a" * 64, "seal_sha256": "b" * 64, "trace_sha256": "e" * 64,
             "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER"}
    monkeypatch.setattr(s3, "_governance_preflight_guard", lambda clean_root, identity: dict(proof))
    monkeypatch.setattr(s3, "_select_governance_preflight_locked", lambda namespace, identity: dict(proof))

    clean = tmp_path / "clean"
    raw = tmp_path / "raw"
    raw.mkdir()
    raw_rows = []
    relatives = [s3.BY2_TRACE_RELATIVE_PATH] + [f"BY2/raw_{index:02d}.dat" for index in range(21)]
    for index, relative in enumerate(relatives):
        path = raw / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"raw-{index}\n".encode())
        raw_rows.append({
            "dataset": "BY2", "relative_path": relative,
            "size_bytes": str(path.stat().st_size), "sha256": sha256_file(path),
        })
    extra = raw / "OTHER/extra.dat"
    extra.parent.mkdir()
    extra.write_bytes(b"extra\n")
    full_rows = raw_rows + [{
        "dataset": "OTHER", "relative_path": "OTHER/extra.dat",
        "size_bytes": str(extra.stat().st_size), "sha256": sha256_file(extra),
    }]
    lock_root = clean / "01_RAW_HASH_LOCK"
    lock_root.mkdir(parents=True)
    full_lock = lock_root / "RAW_FILE_HASH_LOCK.csv"
    by2_lock = lock_root / "BY2_HASH_LOCK.csv"
    for target, rows in ((full_lock, full_rows), (by2_lock, raw_rows)):
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("dataset", "relative_path", "size_bytes", "sha256"))
            writer.writeheader()
            writer.writerows(rows)

    base = clean / "stages" / s3.PARENT_PROVIDER_STAGE_ID / "04_BASE_PROVIDER"
    main = base / "FINAL_V23_CLEAN_CLEAN2R2A"
    aux = base / "FRESH_AUXILIARIES_CLEAN2R2A"
    main.mkdir(parents=True)
    aux.mkdir()
    providers = {
        "imu": main / "imu.txt", "gnss": main / "gnss.txt",
        "raw_doppler": aux / "raw.csv", "go2_roll_pitch": aux / "rp.csv",
        "go2_horizontal_velocity": aux / "hv.csv",
    }
    for role, path in providers.items():
        path.write_text(f"{role}\n", encoding="utf-8")
    provider_hashes = {role: sha256_file(path) for role, path in providers.items()}
    raw_hashes = {row["relative_path"]: row["sha256"] for row in raw_rows}
    clean_manifest = main / "FINAL_V23_CLEAN_INPUT_MANIFEST.json"
    clean_payload = {
        "stage_id": s3.CLEAN_INPUT_STAGE_ID, "protocol_id": s3.CLEAN_INPUT_PROTOCOL_ID,
        "artifacts": {
            "imu": {"relative_path": "imu.txt", "sha256": provider_hashes["imu"]},
            "gnss": {"relative_path": "gnss.txt", "sha256": provider_hashes["gnss"]},
        },
        "raw_source_hashes": raw_hashes,
    }
    clean_manifest.write_text(json.dumps(clean_payload, sort_keys=True), encoding="utf-8")
    auxiliary_manifest = aux / "CLEAN1R2R1_AUXILIARY_MANIFEST.json"
    auxiliary_payload = {
        "stage_id": s3.PARENT_PROVIDER_STAGE_ID, "protocol_id": s3.PARENT_PROVIDER_PROTOCOL_ID,
        "clean_input_manifest_path": str(clean_manifest),
        "clean_input_manifest_sha256": sha256_file(clean_manifest),
        "raw_source_hashes": raw_hashes,
        "auxiliary_artifacts": {
            "raw_doppler_provider": {"path": str(providers["raw_doppler"]), "sha256": provider_hashes["raw_doppler"]},
            "go2_attitude_prior": {"path": str(providers["go2_roll_pitch"]), "sha256": provider_hashes["go2_roll_pitch"]},
            "go2_horizontal_velocity_prior": {"path": str(providers["go2_horizontal_velocity"]), "sha256": provider_hashes["go2_horizontal_velocity"]},
        },
    }
    auxiliary_manifest.write_text(json.dumps(auxiliary_payload, sort_keys=True), encoding="utf-8")
    parity_dir = clean / "stages" / s3.PARENT_PARITY_STAGE_ID / "04_BASE_PROVIDER"
    parity_dir.mkdir(parents=True)
    parity_report = parity_dir / "CLEAN2R2A1_BASE_PROVIDER_PARITY.json"
    parity_payload = {
        "stage_id": s3.PARENT_PARITY_STAGE_ID, "protocol_id": s3.PARENT_PARITY_PROTOCOL_ID,
        "passed": True, "provider_payload_modified_after_generation": False,
        "trace_open_count": 0, "actual_hashes": provider_hashes,
        "raw_source_hashes": raw_hashes,
        "clean_input_manifest_path": str(clean_manifest),
        "clean_input_manifest_sha256": sha256_file(clean_manifest),
        "auxiliary_manifest_path": str(auxiliary_manifest),
        "auxiliary_manifest_sha256": sha256_file(auxiliary_manifest),
    }
    parity_report.write_text(json.dumps(parity_payload, sort_keys=True), encoding="utf-8")

    anchor = clean / "17_LOGS/CLEAN1R2R1_FINAL/04_FOUR_METHOD_RUNTIME/03_strong_dual_yaw_EKF"
    anchor.mkdir(parents=True)
    (anchor / "KF_GINS_Navresult.nav").write_bytes(b"anchor nav\n")
    (anchor / "KF_GINS_STD.txt").write_bytes(b"anchor std\n")

    monkeypatch.setattr(s3, "EXPECTED_MANIFEST_HASHES", {
        "clean_input_manifest": sha256_file(clean_manifest),
        "auxiliary_manifest": sha256_file(auxiliary_manifest),
        "provider_parity_report": sha256_file(parity_report),
    })
    monkeypatch.setattr(s3, "EXPECTED_PROVIDER_HASHES", provider_hashes)
    monkeypatch.setattr(s3, "EXPECTED_FULL_RAW_LOCK_SHA256", sha256_file(full_lock))
    monkeypatch.setattr(s3, "EXPECTED_BY2_RAW_LOCK_SHA256", sha256_file(by2_lock))
    monkeypatch.setattr(s3, "EXPECTED_FULL_RAW_ROWS", 23)
    monkeypatch.setattr(s3, "EXPECTED_ANCHOR_HASHES", {
        "KF_GINS_Navresult.nav": sha256_file(anchor / "KF_GINS_Navresult.nav"),
        "KF_GINS_STD.txt": sha256_file(anchor / "KF_GINS_STD.txt"),
    })
    inputs = s3.S3Inputs(repo, clean, raw, full_lock, by2_lock, clean_manifest, auxiliary_manifest, parity_report)
    return {"inputs": inputs, "providers": providers, "raw": raw, "repo": repo, "clean": clean,
            "freeze": freeze, "freeze_path": freeze_path, "clean_manifest": clean_manifest,
            "auxiliary_manifest": auxiliary_manifest, "parity_report": parity_report,
            "authorization_path": authorization_path, "runner_freeze": runner_freeze,
            "code_freeze": code_freeze, "amendment_parent": amendment_parent}


def _solver_manifest(providers: dict[str, Path]) -> dict[str, object]:
    return {
        "clean1_formal_mode": True, "clean_final_v23_parity_mode": True,
        "stage_id": s3.STAGE_ID, "protocol_id": s3.PROTOCOL_ID, "case_id": s3.CASE_ID,
        "data_mode": s3.DATA_MODE, "run_id": s3.RUN_ID, "algorithm_id": s3.METHOD_ID,
        "enable_dual_yaw_update": True, "enable_receiver_velocity_update": True,
        "enable_raw_doppler": False, "source_aware_weighting_enabled": False,
        "go2_attitude_weak_prior_enabled": False, "go2_horizontal_velocity_prior_enabled": False,
        "trace_used_online": False, "synthetic_data_used": False, "semisynthetic_data_used": False,
        "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False, "per_case_tuning": False,
        "output_only_correction": False, "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0, "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0, "legacy_aggregate_input_count": 0,
        "cov_health_status": "PASS", "cov_health_fail_count": 0, "math_port_completed": True,
        "port_role": "clean3_s3_ab0000_parity_solver", "phase": s3.STAGE_ID,
        "ablation_variant": "AB0000", "yaw_scheme_C_enabled": True,
        "performance_claim": False, "paper_performance_claim": False, "proposed_factor_claim": False,
        "actual_solver_input_paths": {
            "propagation_imu": str(providers["imu"]),
            "gnss_position_receiver_velocity_dual_yaw": str(providers["gnss"]),
        },
        "actual_solver_input_roles": {
            "propagation_imu": "propagation_imu",
            "gnss_position_receiver_velocity_dual_yaw": "gnss_position_receiver_velocity_dual_yaw",
        },
        "position_update_count": 1, "receiver_velocity_update_count": 1,
        "dual_yaw_attempt_count": 1, "dual_yaw_accepted_count": 1,
        "yaw_NORMAL": 1, "yaw_DOWNWEIGHT": 0, "yaw_REJECT": 0,
        "raw_doppler_update_count": 0, "source_aware_evaluation_count": 0,
        "source_aware_weight_changed_count": 0, "go2_roll_pitch_update_count": 0,
        "go2_horizontal_velocity_update_count": 0, "selected_fgo_feedback_update_count": 0,
        "nine_factor_fgo_update_count": 0, "multi_state_qm_update_count": 0,
        "qa_fallback_count": 0, "contact_fk_update_count": 0,
    }


def _amend_freeze(ctx: dict[str, object], freeze: dict[str, object], message: str) -> None:
    path = ctx["freeze_path"]
    assert isinstance(path, Path)
    path.write_text(json.dumps(freeze, sort_keys=True), encoding="utf-8")
    repo = ctx["repo"]
    assert isinstance(repo, Path)
    _git(repo, "add", s3.FREEZE_PATH)
    _git(repo, "commit", "--amend", "-qm", message)


def _runner(ctx, *, mismatch=False, mutate=None, syscall_extra="", solver_returncode=0,
            expected_read_result="3"):
    commands = []
    def run(command, cwd, timeout):
        command = list(command)
        commands.append(command)
        if command[:2] == ["cmake", "-S"]:
            Path(command[command.index("-B") + 1]).mkdir()
        elif command[:2] == ["cmake", "--build"]:
            binary = Path(command[2]) / "legsa_v23_port_core_demo"
            binary.write_text("fake\n", encoding="utf-8")
        else:
            trace = Path(command[command.index("-o") + 1])
            output = Path(command[command.index("--output-dir") + 1])
            trace.write_text(
                f'execve("{command[command.index("-o") + 2]}", ["solver"], 0x0) = 0\n'
                f'openat(AT_FDCWD, "{ctx["providers"]["imu"]}", O_RDONLY) = {expected_read_result}\n'
                f'openat(AT_FDCWD, "{ctx["providers"]["gnss"]}", O_RDONLY) = {expected_read_result}\n'
                f'{syscall_extra}',
                encoding="utf-8",
            )
            (output / "KF_GINS_Navresult.nav").write_bytes(b"mismatch\n" if mismatch else b"anchor nav\n")
            (output / "KF_GINS_STD.txt").write_bytes(b"anchor std\n")
            (output / "RUN_MANIFEST.json").write_text(
                json.dumps(_solver_manifest(ctx["providers"]), sort_keys=True), encoding="utf-8",
            )
            if mutate == "provider":
                ctx["providers"]["imu"].write_text("mutated\n", encoding="utf-8")
            elif mutate == "raw":
                (ctx["raw"] / s3.BY2_TRACE_RELATIVE_PATH).write_text("mutated\n", encoding="utf-8")
            elif mutate == "provider_raw_manifest":
                ctx["providers"]["imu"].write_text("mutated\n", encoding="utf-8")
                (ctx["raw"] / s3.BY2_TRACE_RELATIVE_PATH).write_text("mutated\n", encoding="utf-8")
                ctx["auxiliary_manifest"].write_text("{}\n", encoding="utf-8")
            elif mutate == "copy_provider":
                (output / "copied_provider.bin").write_bytes(ctx["providers"]["imu"].read_bytes())
            return subprocess.CompletedProcess(command, solver_returncode, stdout="solver out\n", stderr="solver err\n")
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")
    return run, commands


def test_one_shot_pass_seals_then_compares_and_stops(fake_s3) -> None:
    runner, commands = _runner(fake_s3)
    report = s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert report["terminal_status"] == s3.PASS_TERMINAL
    assert report["profile_count"] == 1 and report["profiles"] == ["AB0000"]
    assert report["auto_s4_started"] is False and report["evaluator_invoked"] is False
    assert len(commands) == 3
    assert all("evaluator" not in " ".join(command).lower() for command in commands)
    stage = fake_s3["clean"] / "stages" / s3.STAGE_ID
    attempt_claim = json.loads((stage / "ATTEMPT_CLAIM.json").read_text())
    launch_claim = json.loads((stage / "02_AB0000_RUNTIME/SOLVER_LAUNCH_CLAIM.json").read_text())
    assert attempt_claim["claimed_before_configure"] is True
    assert attempt_claim["maximum_solver_executions"] == 1 and attempt_claim["retry_allowed"] is False
    assert attempt_claim["selected_preflight"]["attempt_id"] == "ATTEMPT_000001"
    assert attempt_claim["selected_preflight"]["trace_sha256"] == "e" * 64
    assert launch_claim["solver_execution_ordinal"] == 1 and launch_claim["retry_allowed"] is False
    assert not (stage / "S4").exists()
    config = (stage / "02_AB0000_RUNTIME/CLEAN3_S3_AB0000_RUNTIME_CONFIG.yaml").read_text()
    assert "clean3_s3_ab0000_parity_mode: true" in config
    assert "algorithm_id: AB0000" in config
    assert "enable_raw_doppler: false" in config
    seal = json.loads((stage / "03_SEAL/CLEAN3_S3_OUTPUT_SEAL.json").read_text())
    assert seal["sealed_before_parity_comparison"] is True
    outer = json.loads((stage / "02_AB0000_RUNTIME/CLEAN3_S3_RUN_MANIFEST.json").read_text())
    assert outer["stage_id"] == s3.STAGE_ID
    assert outer["parent_contract"]["stage_id"] == s3.PARENT_PROVIDER_STAGE_ID
    assert outer["trace_used_online"] is False
    assert outer["governance_preflight"] == attempt_claim["selected_preflight"]


@pytest.mark.parametrize("stage_id,protocol_id", [
    (s3.PARENT_PROVIDER_STAGE_ID, s3.PARENT_PROVIDER_PROTOCOL_ID),
    ("WRONG_CLEAN_INPUT_STAGE", s3.CLEAN_INPUT_PROTOCOL_ID),
    (s3.CLEAN_INPUT_STAGE_ID, "WRONG_CLEAN_INPUT_PROTOCOL"),
])
def test_clean_input_manifest_identity_is_exact_and_not_clean2(
    fake_s3, monkeypatch: pytest.MonkeyPatch, stage_id: str, protocol_id: str,
) -> None:
    clean_path = fake_s3["clean_manifest"]
    auxiliary_path = fake_s3["auxiliary_manifest"]
    parity_path = fake_s3["parity_report"]
    clean = json.loads(clean_path.read_text())
    clean.update({"stage_id": stage_id, "protocol_id": protocol_id})
    clean_path.write_text(json.dumps(clean, sort_keys=True), encoding="utf-8")
    auxiliary = json.loads(auxiliary_path.read_text())
    auxiliary["clean_input_manifest_sha256"] = sha256_file(clean_path)
    auxiliary_path.write_text(json.dumps(auxiliary, sort_keys=True), encoding="utf-8")
    parity = json.loads(parity_path.read_text())
    parity["clean_input_manifest_sha256"] = sha256_file(clean_path)
    parity["auxiliary_manifest_sha256"] = sha256_file(auxiliary_path)
    parity_path.write_text(json.dumps(parity, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(s3, "EXPECTED_MANIFEST_HASHES", {
        "clean_input_manifest": sha256_file(clean_path),
        "auxiliary_manifest": sha256_file(auxiliary_path),
        "provider_parity_report": sha256_file(parity_path),
    })
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_INHERITED_MANIFEST_CONTRACT"
    assert commands == []


def test_mismatch_is_blocking_and_keeps_sealed_outputs(fake_s3) -> None:
    runner, _ = _runner(fake_s3, mismatch=True)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == s3.MISMATCH_TERMINAL
    report = json.loads(caught.value.report_path.read_text())
    assert report["terminal_status"] == s3.MISMATCH_TERMINAL
    assert report["passed"] is False
    assert (caught.value.report_path.parents[1] / "03_SEAL/CLEAN3_S3_OUTPUT_SEAL.json").is_file()


@pytest.mark.parametrize("mutate,terminal", [
    ("provider", "FAILED_TECHNICAL_IMMUTABLE_MUTATION_DETECTED"),
    ("raw", "FAILED_TECHNICAL_IMMUTABLE_MUTATION_DETECTED"),
])
def test_post_run_mutation_fails_closed(fake_s3, mutate: str, terminal: str) -> None:
    runner, _ = _runner(fake_s3, mutate=mutate)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == terminal
    assert json.loads(caught.value.report_path.read_text())["passed"] is False


def test_solver_nonzero_mutation_override_and_immediate_logs(fake_s3) -> None:
    runner, _ = _runner(fake_s3, mutate="provider_raw_manifest", solver_returncode=9)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_IMMUTABLE_MUTATION_DETECTED"
    report = json.loads(caught.value.report_path.read_text())
    assert any(role.startswith("provider:") for role in report["immutable_changed_roles"])
    assert any(role.startswith("raw:") for role in report["immutable_changed_roles"])
    assert any(role.startswith("manifest:") for role in report["immutable_changed_roles"])
    logs = caught.value.report_path.parents[1] / "02_AB0000_RUNTIME/logs"
    assert (logs / "solver_stdout.txt").read_text() == "solver out\n"
    assert (logs / "solver_stderr.txt").read_text() == "solver err\n"


def test_solver_nonzero_still_audits_forbidden_syscall(fake_s3) -> None:
    runner, _ = _runner(
        fake_s3, solver_returncode=9,
        syscall_extra='execve("/tmp/evaluator", ["evaluator"], 0x0) = 0\n',
    )
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_SOLVER_FILE_OPEN_AUDIT"
    report = json.loads(caught.value.report_path.read_text())
    assert report["immutable_changed_roles"] == []


@pytest.mark.parametrize("extra", [
    "openat(AT_FDCWD, \"{provider}\", O_WRONLY|O_TRUNC) = 9\n",
    "creat(\"/tmp/clean3_escape\", 0666) = 9\n",
    "openat2(AT_FDCWD, \"{trace}\", {{flags=O_RDONLY}}, 24) = 9\n",
    "openat(AT_FDCWD, \"/tmp/reports/stages/legacy.nav\", O_RDONLY) = 9\n",
    "execve(\"/tmp/evaluator\", [\"evaluator\"], 0x0) = 0\n",
])
def test_syscall_audit_rejects_forbidden_activity(fake_s3, extra: str) -> None:
    rendered = extra.format(
        provider=fake_s3["providers"]["imu"],
        trace=fake_s3["raw"] / s3.BY2_TRACE_RELATIVE_PATH,
    )
    runner, _ = _runner(fake_s3, syscall_extra=rendered)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_SOLVER_FILE_OPEN_AUDIT"


def test_runtime_provider_copy_is_rejected(fake_s3) -> None:
    runner, _ = _runner(fake_s3, mutate="copy_provider")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_PROVIDER_COPY_DETECTED"


def test_syscall_parser_resolves_decorated_dirfd_and_structured_flags(tmp_path: Path) -> None:
    trace = tmp_path / "trace"
    trace.write_text(
        f'openat(7<{tmp_path}>, "relative/O_RDWR_name", O_RDONLY|O_CLOEXEC) = 8\n'
        f'openat2(AT_FDCWD<{tmp_path}>, "second", {{flags=O_RDONLY|O_CLOEXEC, mode=0}}, 24) = 9\n',
        encoding="utf-8",
    )
    events = s3._syscall_events(trace, ROOT)
    assert events[0]["paths"] == [(tmp_path / "relative/O_RDWR_name").resolve()]
    assert events[0]["flags"] == "O_RDONLY|O_CLOEXEC"
    assert events[1]["paths"] == [(tmp_path / "second").resolve()]
    assert events[1]["flags"] == "O_RDONLY|O_CLOEXEC"


@pytest.mark.parametrize("row,terminal", [
    ('openat(7, "relative", O_RDONLY) = 8\n', "FAILED_TECHNICAL_SYSCALL_UNRESOLVED_DIRFD"),
    ('openat(AT_FDCWD, "x", O_RDONLY <unfinished ...>\n', "FAILED_TECHNICAL_SYSCALL_TRACE_INCOMPLETE"),
])
def test_syscall_parser_rejects_unresolved_or_incomplete(tmp_path: Path, row: str, terminal: str) -> None:
    trace = tmp_path / "trace"
    trace.write_text(row, encoding="utf-8")
    with pytest.raises(s3._TechnicalFailure) as caught:
        s3._syscall_events(trace, ROOT)
    assert "FAILED_TECHNICAL_" + caught.value.reason == terminal


@pytest.mark.parametrize("extra", [
    'renameat(4</tmp>, "old", 4</tmp>, "new") = -1 EPERM (Operation not permitted)\n',
    'unlinkat(4</tmp>, "victim", 0) = -1 EPERM (Operation not permitted)\n',
])
def test_failed_mutation_attempt_still_fails(fake_s3, extra: str) -> None:
    runner, _ = _runner(fake_s3, syscall_extra=extra)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_SOLVER_FILE_OPEN_AUDIT"


def test_failed_expected_reads_do_not_satisfy_audit(fake_s3) -> None:
    runner, _ = _runner(fake_s3, expected_read_result="-1 ENOENT (No such file or directory)")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_SOLVER_FILE_OPEN_AUDIT"


def test_same_root_symlink_is_rejected_lexically(fake_s3) -> None:
    link = fake_s3["inputs"].by2_raw_lock
    real = link.with_name("BY2_REAL.csv")
    link.rename(real)
    link.symlink_to(real.name)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_PATH_SYMLINK"


def test_cross_root_symlink_is_rejected_lexically(fake_s3, tmp_path: Path) -> None:
    link = fake_s3["inputs"].clean_input_manifest
    outside = tmp_path / "outside.json"
    outside.write_bytes(link.read_bytes())
    link.unlink()
    link.symlink_to(outside)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_PATH_SYMLINK"


def test_preexisting_stage_rejected_before_commands(fake_s3) -> None:
    stage = fake_s3["clean"] / "stages" / s3.STAGE_ID
    stage.mkdir()
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_STAGE_ROOT_PREEXISTS"
    assert commands == []


def test_dirty_worktree_rejected_before_commands(fake_s3) -> None:
    (fake_s3["repo"] / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_DIRTY_WORKTREE"
    assert commands == []


def test_clean3r2_freeze_contract_valid_pass(fake_s3) -> None:
    identity = s3._guard_git(fake_s3["repo"])
    assert identity["code_freeze_commit"] == fake_s3["code_freeze"]
    assert identity["runner_freeze_commit"] == fake_s3["runner_freeze"]
    assert identity["authorization_document"] == s3.AUTHORIZATION_PATH
    assert identity["maximum_solver_executions"] == 1


@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", "paper_rebuild.clean3_s3_execution_freeze.v1"),
    ("stage_id", "WRONG_STAGE"),
    ("protocol_id", "WRONG_PROTOCOL"),
    ("case_id", "WRONG_CASE"),
    ("algorithm_id", "AB0001"),
    ("run_id", "WRONG_RUN"),
])
def test_clean3r2_freeze_schema_and_identity_drift_fail_closed(
    fake_s3, field: str, value: str,
) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze[field] = value
    _amend_freeze(fake_s3, freeze, f"bad {field}")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_CONTRACT"


def test_repair_lineage_drift_rejected(fake_s3, monkeypatch: pytest.MonkeyPatch) -> None:
    repair = fake_s3["runner_freeze"]
    monkeypatch.setattr(s3, "REPAIR_IMPLEMENTATION_COMMIT", repair)
    freeze = dict(fake_s3["freeze"])
    freeze["repair_implementation_commit"] = repair
    _amend_freeze(fake_s3, freeze, "bad repair lineage")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_WRONG_CODE_LINEAGE"


def test_code_freeze_parent_drift_rejected(fake_s3, monkeypatch: pytest.MonkeyPatch) -> None:
    wrong_parent = s3.REPAIR_IMPLEMENTATION_COMMIT
    monkeypatch.setattr(s3, "AMENDMENT_PARENT_HEAD", wrong_parent)
    freeze = dict(fake_s3["freeze"])
    freeze["amendment_parent_head"] = wrong_parent
    _amend_freeze(fake_s3, freeze, "bad runner parent")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_LINEAGE"


def test_successor_runner_freeze_parent_drift_rejected(fake_s3) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze["runner_freeze_commit"] = _git(fake_s3["repo"], "rev-parse", "HEAD")
    _amend_freeze(fake_s3, freeze, "bad successor runner parent")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_LINEAGE"


@pytest.mark.parametrize(
    "scope_name", ["S0_CODE_FREEZE_CHANGED_PATHS", "RUNNER_FREEZE_CHANGED_PATHS"],
)
def test_predecessor_and_successor_scope_drift_rejected(
    fake_s3, monkeypatch: pytest.MonkeyPatch, scope_name: str,
) -> None:
    approved = getattr(s3, scope_name)
    monkeypatch.setattr(s3, scope_name, approved[:-1])
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT"


def test_authorization_commit_scope_drift_rejected(fake_s3) -> None:
    extra = fake_s3["repo"] / "docs/paper_rebuild/EXTRA.md"
    extra.write_text("scope drift\n", encoding="utf-8")
    _git(fake_s3["repo"], "add", extra.relative_to(fake_s3["repo"]).as_posix())
    _git(fake_s3["repo"], "commit", "--amend", "-qm", "bad authorization scope")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT"


def test_authorization_hash_drift_rejected(fake_s3) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze["authorization_sha256"] = "0" * 64
    _amend_freeze(fake_s3, freeze, "bad authorization hash")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_AUTHORIZATION_HASH_MISMATCH"


@pytest.mark.parametrize(("field", "value"), [
    ("failed_attempt_stage_id", "WRONG_FAILED_STAGE"),
    ("failed_attempt_terminal", "WRONG_TERMINAL"),
    ("failed_attempt_parity", "PASS"),
])
def test_old_failed_attempt_contract_drift_rejected(fake_s3, field: str, value: str) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze[field] = value
    _amend_freeze(fake_s3, freeze, f"bad old attempt {field}")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_CONTRACT"


def test_execution_count_authorization_drift_rejected(fake_s3) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze["execution_authorization"] = dict(freeze["execution_authorization"])
    freeze["execution_authorization"]["maximum_solver_executions"] = 2
    _amend_freeze(fake_s3, freeze, "bad execution count")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._guard_git(fake_s3["repo"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_AUTHORIZATION_CONTRACT"


@pytest.mark.parametrize("relative", [
    s3.LOADER_EXTENSION_PATH,
    "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
])
def test_same_path_frozen_byte_drift_rejected(fake_s3, relative: str) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze["tracked_file_sha256"] = dict(freeze["tracked_file_sha256"])
    freeze["tracked_file_sha256"][relative] = "0" * 64
    _amend_freeze(fake_s3, freeze, "authorize bad bytes")
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_RUNNER_BYTE_DRIFT"
    assert commands == []


def test_cli_surface_has_separate_preflight_and_no_profile_selector() -> None:
    import importlib.util
    script = ROOT / "scripts/paper_rebuild/run_clean3_math_repair.py"
    spec = importlib.util.spec_from_file_location("clean3_cli", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    help_text = module.parser().format_help()
    assert "s3-ab0000-parity" in help_text
    assert "governance-preflight" in help_text
    with pytest.raises(SystemExit):
        module.parser().parse_args(["s4"])
    with pytest.raises(SystemExit):
        module.parser().parse_args(["s3-ab0000-parity", "--profile", "AB0001"])


def test_module_docstring_states_exact_two_operation_boundary() -> None:
    assert s3.__doc__ is not None
    assert "exactly two operations" in s3.__doc__
    assert "zero-data governance preflight" in s3.__doc__
    assert "one-shot S3 parity attempt" in s3.__doc__
    assert "preflight never runs\nthe formal solver" in s3.__doc__


def _write_namespace_lock(namespace: Path) -> None:
    lock = namespace / ".namespace.lock"
    lock.touch(mode=0o600)
    info = lock.stat()
    lock.write_text(json.dumps({"schema_version": s3.PREFLIGHT_LOCK_SCHEMA,
        "st_dev": info.st_dev, "st_ino": info.st_ino}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8")


def _sealed_preflight_fixture(tmp_path: Path, execution_head: str = "a" * 40):
    namespace = tmp_path / s3.PREFLIGHT_RELATIVE
    namespace.mkdir(parents=True)
    _write_namespace_lock(namespace)
    root = namespace / "ATTEMPT_000001"
    root.mkdir()
    report_path = root / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json"
    ledger_path = root / "03_SEAL/ZERO_DATA_LOADER_READ_LEDGER.json"
    trace_path = root / "02_HARNESS/logs/SOLVER_FILE_OPEN_TRACE.raw"
    artifact_paths = {
        "harness_binary": root / "01_BUILD/zero_data_loader",
        "harness_source": root / "01_BUILD/zero_data_loader.cpp",
        "accepting_config": root / "02_HARNESS/configs/CLEAN3R3_ZERO_DATA.yaml",
        "negative_config": root / "02_HARNESS/configs/CANONICAL_T8_REJECT.yaml",
    }
    for parent in (report_path.parent, ledger_path.parent, trace_path.parent,
                   *(path.parent for path in artifact_paths.values())):
        parent.mkdir(parents=True, exist_ok=True)
    for role, path in artifact_paths.items():
        path.write_text(role + "\n", encoding="utf-8")
    claim_path = root / "ATTEMPT_CLAIM.json"
    claim_path.write_text(json.dumps({"schema_version": s3.PREFLIGHT_CLAIM_SCHEMA,
        "attempt_id": root.name, "attempt_ordinal": 1, "execution_head": execution_head,
        "stage_id": s3.STAGE_ID, "predecessor_attempt_id": None,
        "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER", "formal_solver_executed": False,
        "claimed_before_work": True}, sort_keys=True), encoding="utf-8")
    artifacts = {role: sha256_file(path) for role, path in artifact_paths.items()}
    report = {
        "schema_version": s3.PREFLIGHT_REPORT_SCHEMA,
        "terminal_status": "PREFLIGHT_OK", "stage_id": s3.STAGE_ID,
        "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
        "trace_subject": "ZERO_DATA_LOADER_HARNESS", "formal_solver_executed": False,
        "raw_open_count": 0, "provider_open_count": 0, "reference_trace_open_count": 0,
        "legacy_open_count": 0, "unexpected_write_count": 0, "unexpected_read_count": 0,
        "g_c2": "REPORTING_ONLY", "g_c3": "HARD_UNCHANGED",
        "execution_head": execution_head, "trace_cwd": str(tmp_path),
        "bound_artifact_sha256": artifacts,
    }
    binary = str(artifact_paths["harness_binary"].resolve())
    ledger = {
        "schema_version": s3.PREFLIGHT_LEDGER_SCHEMA, "trace_subject": "ZERO_DATA_LOADER_HARNESS",
        "exec_paths": [binary], "expected_exec_path": binary, "exact_exec_subject": True,
        "read_attempt_paths": [str(artifact_paths["accepting_config"].resolve())],
        "write_attempt_paths": [], "accepting_config_open_count": 1, "negative_config_open_count": 0,
        "raw_paths": [], "provider_paths": [], "reference_trace_paths": [], "legacy_paths": [],
        "unexpected_write_paths": [], "unexpected_read_paths": [],
        "path_classifications": {str(artifact_paths["accepting_config"].resolve()): "accepting_config"},
        "classification_roots": {key: str(root / "NONEXISTENT_DO_NOT_OPEN" / key)
                                 for key in ("raw", "provider", "reference", "legacy")},
        "raw_open_count": 0, "provider_open_count": 0,
        "reference_trace_open_count": 0, "legacy_open_count": 0, "unexpected_write_count": 0,
        "unexpected_read_count": 0,
        "bound_artifact_sha256": artifacts, "formal_solver_executed": False, "passed": True,
    }
    ledger_path.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")
    report.update({key: value for key, value in ledger.items() if key not in ("schema_version", "passed")})
    report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    trace_path.write_text(
        f'execve("{artifact_paths["harness_binary"]}", ["loader"], 0x0) = 0\n'
        f'openat(AT_FDCWD, "{artifact_paths["accepting_config"]}", O_RDONLY) = 3\n',
        encoding="utf-8")
    seal_path = root / "03_SEAL/CLEAN3R3_GOVERNANCE_PREFLIGHT_SEAL.json"
    seal = {"schema_version": s3.PREFLIGHT_SEAL_SCHEMA, "sealed": True,
            "bound_artifact_sha256": artifacts, "sha256": {
        "report": sha256_file(report_path), "ledger": sha256_file(ledger_path),
        "raw_trace": sha256_file(trace_path),
    }}
    seal_path.write_text(json.dumps(seal, sort_keys=True), encoding="utf-8")
    (root / "TERMINAL.json").write_text(json.dumps({
        "schema_version": s3.PREFLIGHT_TERMINAL_SCHEMA, "attempt_id": root.name,
        "attempt_ordinal": 1, "terminal_status": "PREFLIGHT_OK",
        "report_sha256": sha256_file(report_path), "claim_sha256": sha256_file(claim_path),
    }, sort_keys=True), encoding="utf-8")
    return root, report_path, ledger_path, trace_path, seal_path, report, ledger, seal, artifact_paths


def test_sealed_governance_preflight_guard_is_hard_and_hash_bound(tmp_path: Path) -> None:
    execution_head = "a" * 40
    root, _, _, trace_path, _, _, _, _, _ = _sealed_preflight_fixture(tmp_path, execution_head)
    accepted = s3._governance_preflight_guard(tmp_path, {"execution_head": execution_head})
    assert accepted["proof_kind"] == "STATIC_PLUS_ZERO_DATA_LOADER"
    trace_path.write_text("drift\n", encoding="utf-8")
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3._governance_preflight_guard(tmp_path, {"execution_head": execution_head})
    assert caught.value.terminal_status == "FAILED_TECHNICAL_PREFLIGHT_TRACE_REPLAY"


def test_preflight_rejects_external_symlinked_report_parent(tmp_path: Path) -> None:
    root, *_ = _sealed_preflight_fixture(tmp_path)
    report_parent = root / "04_REPORT"
    external = tmp_path / "external-report"; report_parent.rename(external)
    report_parent.symlink_to(external, target_is_directory=True)
    with pytest.raises(s3.Clean3S3Error):
        s3._governance_preflight_guard(tmp_path, {"execution_head": "a" * 40})


@pytest.mark.parametrize("mutation", [
    "incomplete_ledger", "count_mismatch", "wrong_exec", "forbidden_read", "unexpected_write",
    "omitted_artifact", "bad_artifact_hash", "raw_trace_contradiction", "nonsyscall_trace",
    "report_divergence",
])
def test_governance_preflight_guard_rejects_inconsistent_evidence(tmp_path: Path, mutation: str) -> None:
    _, report_path, ledger_path, trace_path, seal_path, report, ledger, seal, artifacts = \
        _sealed_preflight_fixture(tmp_path)
    if mutation == "incomplete_ledger":
        ledger.pop("schema_version")
    elif mutation == "count_mismatch":
        ledger["raw_open_count"] = 1
    elif mutation == "wrong_exec":
        ledger["exec_paths"] = ["/tmp/not-the-loader"]
        ledger["expected_exec_path"] = "/tmp/not-the-loader"
    elif mutation == "forbidden_read":
        ledger["provider_paths"] = ["/tmp/forbidden-provider"]
        ledger["provider_open_count"] = 1
    elif mutation == "unexpected_write":
        ledger["unexpected_write_paths"] = ["/tmp/write"]
        ledger["unexpected_write_count"] = 1
    elif mutation == "omitted_artifact":
        ledger["bound_artifact_sha256"].pop("negative_config")
    elif mutation == "bad_artifact_hash":
        artifacts["harness_source"].write_text("drift\n", encoding="utf-8")
    elif mutation == "raw_trace_contradiction":
        trace_path.write_text('execve("/tmp/not-the-loader", ["bad"], 0x0) = 0\n', encoding="utf-8")
    elif mutation == "nonsyscall_trace":
        trace_path.write_text("not a syscall trace\n", encoding="utf-8")
    else:
        report["path_classifications"] = {"/tmp/fabricated": "system_dependency"}
        report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")
    seal["sha256"]["ledger"] = sha256_file(ledger_path)
    seal["sha256"]["report"] = sha256_file(report_path)
    seal["sha256"]["raw_trace"] = sha256_file(trace_path)
    seal_path.write_text(json.dumps(seal, sort_keys=True), encoding="utf-8")
    with pytest.raises(s3.Clean3S3Error):
        s3._governance_preflight_guard(tmp_path, {"execution_head": "a" * 40})


@pytest.mark.parametrize("extra", [
    'execve("/tmp/not-loader", ["bad"], 0x0) = 0\n',
    'openat(AT_FDCWD, "{sentinel}/provider/imu", O_RDONLY) = -1 ENOENT\n',
    'openat(AT_FDCWD, "/tmp/unexpected-write", O_WRONLY|O_CREAT) = 3\n',
])
def test_preflight_trace_parser_rejects_wrong_subject_forbidden_read_and_write(
    tmp_path: Path, extra: str,
) -> None:
    binary, accepting, negative = tmp_path / "loader", tmp_path / "accept.yaml", tmp_path / "negative.yaml"
    for path in (binary, accepting, negative):
        path.write_text(path.name, encoding="utf-8")
    sentinel = tmp_path / "NONEXISTENT_DO_NOT_OPEN"
    trace = tmp_path / "trace.raw"
    trace.write_text(
        f'execve("{binary}", ["loader"], 0x0) = 0\n'
        f'openat(AT_FDCWD, "{accepting}", O_RDONLY) = 3\n'
        + extra.format(sentinel=sentinel), encoding="utf-8")
    with pytest.raises(s3._TechnicalFailure):
        s3._audit_preflight_trace(
            trace, cwd=tmp_path, harness_binary=binary, accepting_config=accepting,
            negative_config=negative, sentinel_root=sentinel,
            artifact_hashes={role: "a" * 64 for role in
                             ("harness_binary", "harness_source", "accepting_config", "negative_config")},
        )


def test_governance_preflight_generator_emits_bound_zero_data_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean = tmp_path / "clean"
    clean.mkdir()
    execution_head = "b" * 40
    monkeypatch.setattr(s3, "_guard_git", lambda repo: {"execution_head": execution_head})

    def runner(command, cwd, timeout):
        command = list(command)
        if command[0] == "g++":
            binary = Path(command[-1])
            binary.write_text("loader binary\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[0] == "/fake/strace":
            trace = Path(command[command.index("-o") + 1])
            binary = Path(command[-2])
            config = Path(command[-1])
            trace.write_text(
                f'execve("{binary}", ["loader"], 0x0) = 0\n'
                f'openat(AT_FDCWD, "{config}", O_RDONLY) = 3\n', encoding="utf-8")
            stdout = "\n".join((s3.STAGE_ID, "clean3_s3_ab0000_parity_solver", s3.STAGE_ID, s3.RUN_ID))
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(
            command, 2, stdout="", stderr="FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")

    report = s3.run_governance_preflight(
        ROOT, clean, command_runner=runner, which=lambda _: "/fake/strace")
    assert report["terminal_status"] == "PREFLIGHT_OK"
    assert report["formal_solver_executed"] is False
    assert report["raw_open_count"] == report["provider_open_count"] == 0
    accepted = s3._governance_preflight_guard(clean, {"execution_head": execution_head})
    assert accepted["proof_kind"] == "STATIC_PLUS_ZERO_DATA_LOADER"
    second = s3.run_governance_preflight(
        ROOT, clean, command_runner=runner, which=lambda _: "/fake/strace")
    assert second["attempt_ordinal"] == 2
    selected = s3._governance_preflight_guard(clean, {"execution_head": execution_head})
    assert selected["attempt_id"] == "ATTEMPT_000002"


@pytest.mark.parametrize("entry", ["ATTEMPT_2", "ATTEMPT_000002", "unexpected", "ATTEMPT_000001"])
def test_preflight_namespace_rejects_noncanonical_gap_and_unexpected_entries(
    tmp_path: Path, entry: str,
) -> None:
    namespace = tmp_path / s3.PREFLIGHT_RELATIVE
    namespace.mkdir(parents=True)
    _write_namespace_lock(namespace)
    target = namespace / entry
    if entry == "ATTEMPT_000001":
        target.symlink_to(tmp_path, target_is_directory=True)
    else:
        target.mkdir()
    with pytest.raises(s3.Clean3S3Error):
        s3._scan_preflight_attempts(namespace)


def test_preflight_namespace_rejects_parent_and_dangling_lock_symlinks(tmp_path: Path) -> None:
    clean = tmp_path / "clean"; clean.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    (clean / "00_GOVERNANCE_PREFLIGHT").symlink_to(outside, target_is_directory=True)
    with pytest.raises(s3.Clean3S3Error):
        with s3._preflight_namespace_lock(clean):
            pass
    (clean / "00_GOVERNANCE_PREFLIGHT").unlink()
    namespace = clean / s3.PREFLIGHT_RELATIVE
    namespace.mkdir(parents=True)
    (namespace / ".namespace.lock").symlink_to(tmp_path / "missing")
    with pytest.raises(s3.Clean3S3Error):
        with s3._preflight_namespace_lock(clean):
            pass


def test_preflight_is_forbidden_after_formal_stage_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clean = tmp_path / "clean"
    (clean / "stages" / s3.STAGE_ID).mkdir(parents=True)
    monkeypatch.setattr(s3, "_guard_git", lambda repo: {"execution_head": "b" * 40})
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_governance_preflight(ROOT, clean, which=lambda _: "/fake/strace")
    assert caught.value.terminal_status == "FAILED_TECHNICAL_PREFLIGHT_AFTER_FORMAL_CLAIM"


def test_latest_failed_or_incomplete_preflight_blocks_pass_selection(tmp_path: Path) -> None:
    _sealed_preflight_fixture(tmp_path)
    namespace = tmp_path / s3.PREFLIGHT_RELATIVE
    second = namespace / "ATTEMPT_000002"
    second.mkdir()
    with pytest.raises(s3.Clean3S3Error) as incomplete:
        s3._governance_preflight_guard(tmp_path, {"execution_head": "a" * 40})
    assert incomplete.value.terminal_status == "FAILED_TECHNICAL_PREFLIGHT_INCOMPLETE"
    claim = second / "ATTEMPT_CLAIM.json"
    claim_payload = {"schema_version": s3.PREFLIGHT_CLAIM_SCHEMA, "attempt_id": second.name,
        "attempt_ordinal": 2, "execution_head": "a" * 40, "stage_id": s3.STAGE_ID,
        "predecessor_attempt_id": "ATTEMPT_000001", "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
        "formal_solver_executed": False, "claimed_before_work": True}
    claim.write_text(json.dumps(claim_payload), encoding="utf-8")
    report = second / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_FAILURE.json"
    report.parent.mkdir(parents=True)
    failure = {"schema_version": s3.PREFLIGHT_FAILURE_SCHEMA, "stage_id": s3.STAGE_ID,
        "attempt_id": second.name, "attempt_ordinal": 2, "execution_head": "a" * 40,
        "predecessor_attempt_id": "ATTEMPT_000001", "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
        "formal_solver_executed": False, "terminal_status": "PREFLIGHT_FAILED", "passed": False,
        "failure_reason": "forced failure", "claim_sha256": sha256_file(claim)}
    report.write_text(json.dumps(failure), encoding="utf-8")
    (second / "TERMINAL.json").write_text(json.dumps({
        "schema_version": s3.PREFLIGHT_TERMINAL_SCHEMA, "attempt_id": second.name,
        "attempt_ordinal": 2, "terminal_status": "PREFLIGHT_FAILED",
        "claim_sha256": sha256_file(claim), "report_sha256": sha256_file(report),
    }), encoding="utf-8")
    with pytest.raises(s3.Clean3S3Error) as failed:
        s3._governance_preflight_guard(tmp_path, {"execution_head": "a" * 40})
    assert failed.value.terminal_status == "FAILED_TECHNICAL_PREFLIGHT_LATEST_FAILED"


def test_concurrent_preflight_claims_receive_distinct_contiguous_ordinals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    import threading

    clean = tmp_path / "clean"
    clean.mkdir()
    monkeypatch.setattr(s3, "_guard_git", lambda repo: {"execution_head": "b" * 40})
    entered, before_second_flock, release = threading.Event(), threading.Event(), threading.Event()
    hook_count = {"value": 0}
    hook_lock = threading.Lock()
    def before_flock():
        with hook_lock:
            hook_count["value"] += 1
            if hook_count["value"] == 2:
                before_second_flock.set()
    monkeypatch.setattr(s3, "_LOCK_BEFORE_FLOCK_HOOK", before_flock)

    @s3._locked_preflight
    def claim_only(repo, clean_root, *, _attempt_root=None, _git_identity=None):
        if _attempt_root.name == "ATTEMPT_000001":
            entered.set()
            assert release.wait(5)
        report = {"attempt_id": _attempt_root.name, "attempt_ordinal": int(_attempt_root.name[-6:])}
        (Path(_attempt_root) / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json").write_text(
            json.dumps(report), encoding="utf-8")
        return report

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(claim_only, ROOT, clean)
        assert entered.wait(5)
        second = pool.submit(claim_only, ROOT, clean)
        assert before_second_flock.wait(5)
        assert not second.done()
        release.set()
        results = [first.result(), second.result()]
    assert sorted(item["attempt_ordinal"] for item in results) == [1, 2]
    assert [path.name for path in s3._scan_preflight_attempts(clean / s3.PREFLIGHT_RELATIVE)] == [
        "ATTEMPT_000001", "ATTEMPT_000002"]


def test_ordinary_failed_preflight_is_sealed_and_allows_later_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean = tmp_path / "clean"; clean.mkdir()
    monkeypatch.setattr(s3, "_guard_git", lambda repo: {"execution_head": "b" * 40})
    calls = {"count": 0}
    @s3._locked_preflight
    def fail_then_pass(repo, clean_root, *, _attempt_root=None, _git_identity=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("ordinary injected failure")
        report = {"attempt_id": _attempt_root.name, "attempt_ordinal": int(_attempt_root.name[-6:])}
        (Path(_attempt_root) / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json").write_text(
            json.dumps(report), encoding="utf-8")
        return report
    with pytest.raises(RuntimeError):
        fail_then_pass(ROOT, clean)
    assert s3._attempt_terminal(clean / s3.PREFLIGHT_RELATIVE / "ATTEMPT_000001")["terminal_status"] == "PREFLIGHT_FAILED"
    assert fail_then_pass(ROOT, clean)["attempt_ordinal"] == 2


def test_replaced_lock_inode_cannot_enter_or_mutate_namespace(tmp_path: Path) -> None:
    import threading
    clean = tmp_path / "clean"; clean.mkdir()
    held, release = threading.Event(), threading.Event()
    failures = []
    def holder():
        try:
            with s3._preflight_namespace_lock(clean):
                held.set(); release.wait(5)
        except s3.Clean3S3Error as exc:
            failures.append(exc)
    thread = threading.Thread(target=holder); thread.start(); assert held.wait(5)
    namespace = clean / s3.PREFLIGHT_RELATIVE
    lock = namespace / ".namespace.lock"; copied = lock.read_bytes()
    lock.unlink(); lock.write_bytes(copied)
    with pytest.raises(s3.Clean3S3Error):
        with s3._preflight_namespace_lock(clean):
            (namespace / "ATTEMPT_000001").mkdir()
    release.set(); thread.join(5)
    assert failures and not (namespace / "ATTEMPT_000001").exists()


def test_s3_selection_race_fails_before_stage_creation(fake_s3, monkeypatch: pytest.MonkeyPatch) -> None:
    initial = s3._governance_preflight_guard(fake_s3["clean"], {"execution_head": "ignored"})
    changed = dict(initial); changed["attempt_id"] = "ATTEMPT_000002"; changed["attempt_ordinal"] = 2
    monkeypatch.setattr(s3, "_governance_preflight_guard", lambda clean, identity: dict(initial))
    monkeypatch.setattr(s3, "_select_governance_preflight_locked", lambda namespace, identity: dict(changed))
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"])
    assert caught.value.terminal_status == "FAILED_TECHNICAL_PREFLIGHT_SELECTION_RACE"
    assert not (fake_s3["clean"] / "stages" / s3.STAGE_ID).exists()
