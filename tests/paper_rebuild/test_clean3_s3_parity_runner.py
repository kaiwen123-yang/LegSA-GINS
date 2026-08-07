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
    loader = repo / s3.LOADER_EXTENSION_PATH
    loader.parent.mkdir(parents=True)
    loader.write_text("s2\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs/context.md").write_text("context\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "s2 repair")
    repair = _git(repo, "rev-parse", "HEAD")
    prior_tree = _git(repo, "rev-parse", "HEAD:cpp")
    (repo / "docs/context.md").write_text("pre parity\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pre parity")
    pre = _git(repo, "rev-parse", "HEAD")
    loader.write_text("s2 plus loader extension\n", encoding="utf-8")
    for relative in s3.FROZEN_CODE_PATHS[1:]:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "superseded runner freeze")
    old_c1 = _git(repo, "rev-parse", "HEAD")

    old_freeze_path = repo / s3.FREEZE_PATH
    old_freeze_path.parent.mkdir(parents=True, exist_ok=True)
    old_freeze_path.write_text("{}\n", encoding="utf-8")
    _git(repo, "add", s3.FREEZE_PATH)
    _git(repo, "commit", "-qm", "superseded authorization")
    old_c2 = _git(repo, "rev-parse", "HEAD")

    for relative in (
        "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
        "tests/paper_rebuild/test_clean3_s3_parity_runner.py",
    ):
        (repo / relative).write_text(f"replacement bytes for {relative}\n", encoding="utf-8")
    for relative in ("docs/paper_rebuild/ACTIVE_CONTEXT.md", "docs/paper_rebuild/CLEAN3_STATUS.md"):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"replacement governance for {relative}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "replacement runner freeze")
    runner_freeze = _git(repo, "rev-parse", "HEAD")

    monkeypatch.setattr(s3, "REPAIR_IMPLEMENTATION_COMMIT", repair)
    monkeypatch.setattr(s3, "PRE_PARITY_CONTEXT_COMMIT", pre)
    monkeypatch.setattr(s3, "PRIOR_REVIEWED_CPP_TREE", prior_tree)
    monkeypatch.setattr(s3, "SUPERSEDED_RUNNER_FREEZE_COMMIT", old_c1)
    monkeypatch.setattr(s3, "SUPERSEDED_AUTHORIZATION_COMMIT", old_c2)
    freeze_path = repo / s3.FREEZE_PATH
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    freeze = {
        "schema_version": "paper_rebuild.clean3_s3_execution_freeze.v1",
        "stage_id": s3.STAGE_ID, "protocol_id": s3.PROTOCOL_ID,
        "runner_freeze_commit": runner_freeze,
        "repair_implementation_commit": repair,
        "pre_parity_context_commit": pre,
        "supersedes_runner_freeze_commit": old_c1,
        "supersedes_authorization_commit": old_c2,
        "supersession_reason": "PRE_STAGE_MANIFEST_PROVENANCE_CONTRACT_REPAIR",
        "superseded_authorization_s3_started": False,
        "final_cpp_tree": _git(repo, "rev-parse", "HEAD:cpp"),
        "tracked_file_sha256": {relative: sha256_file(repo / relative) for relative in s3.FROZEN_CODE_PATHS},
    }
    freeze_path.write_text(json.dumps(freeze, sort_keys=True), encoding="utf-8")
    _git(repo, "add", s3.FREEZE_PATH)
    _git(repo, "commit", "-qm", "authorize S3")

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
            "old_c1": old_c1, "old_c2": old_c2, "runner_freeze": runner_freeze}


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


def test_wrong_lineage_rejected_before_commands(fake_s3, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s3, "REPAIR_IMPLEMENTATION_COMMIT", "0" * 40)
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_CONTRACT"
    assert commands == []


def test_cpp_scope_drift_rejected_before_commands(fake_s3) -> None:
    extra = fake_s3["repo"] / "cpp/extra.cpp"
    extra.write_text("scope drift\n", encoding="utf-8")
    _git(fake_s3["repo"], "add", ".")
    _git(fake_s3["repo"], "commit", "-qm", "cpp scope drift")
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_LINEAGE"
    assert commands == []


def test_replacement_c1b_scope_drift_rejected(fake_s3, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s3, "C1B_APPROVED_PATHS", s3.C1B_APPROVED_PATHS[:-1])
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT"
    assert commands == []


def test_superseded_lineage_drift_rejected(fake_s3, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze["supersedes_authorization_commit"] = fake_s3["old_c1"]
    fake_s3["freeze_path"].write_text(json.dumps(freeze, sort_keys=True), encoding="utf-8")
    _git(fake_s3["repo"], "add", s3.FREEZE_PATH)
    _git(fake_s3["repo"], "commit", "--amend", "-qm", "bad supersession authorization")
    monkeypatch.setattr(s3, "SUPERSEDED_AUTHORIZATION_COMMIT", fake_s3["old_c1"])
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_FREEZE_LINEAGE"
    assert commands == []


@pytest.mark.parametrize("relative", [
    s3.LOADER_EXTENSION_PATH,
    "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
])
def test_same_path_frozen_byte_drift_rejected(fake_s3, relative: str) -> None:
    freeze = dict(fake_s3["freeze"])
    freeze["tracked_file_sha256"] = dict(freeze["tracked_file_sha256"])
    freeze["tracked_file_sha256"][relative] = "0" * 64
    fake_s3["freeze_path"].write_text(json.dumps(freeze, sort_keys=True), encoding="utf-8")
    _git(fake_s3["repo"], "add", s3.FREEZE_PATH)
    _git(fake_s3["repo"], "commit", "--amend", "-qm", "authorize bad bytes")
    runner, commands = _runner(fake_s3)
    with pytest.raises(s3.Clean3S3Error) as caught:
        s3.run_s3_ab0000_parity(fake_s3["inputs"], command_runner=runner)
    assert caught.value.terminal_status == "FAILED_TECHNICAL_RUNNER_BYTE_DRIFT"
    assert commands == []


def test_cli_surface_has_only_s3_and_no_profile_selector() -> None:
    import importlib.util
    script = ROOT / "scripts/paper_rebuild/run_clean3_math_repair.py"
    spec = importlib.util.spec_from_file_location("clean3_cli", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    help_text = module.parser().format_help()
    assert "s3-ab0000-parity" in help_text
    with pytest.raises(SystemExit):
        module.parser().parse_args(["s4"])
    with pytest.raises(SystemExit):
        module.parser().parse_args(["s3-ab0000-parity", "--profile", "AB0001"])
