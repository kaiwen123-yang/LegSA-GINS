from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.audit import audit_clean_runtime, audit_passed
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.paths import load_clean_paths
from legsa_gins.paper_rebuild.providers import build_physical_dual_yaw_provider
from legsa_gins.paper_rebuild.runner import CleanPaperRunner, CleanRunError


def _write_hash_lock(clean: Path, raw: Path, source: Path) -> str:
    digest = sha256_file(source)
    lock = clean / "01_RAW_HASH_LOCK" / "RAW_FILE_HASH_LOCK.csv"
    lock.parent.mkdir(parents=True)
    with lock.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerow(
            {
                "relative_path": source.relative_to(raw).as_posix(),
                "size_bytes": source.stat().st_size,
                "sha256": digest,
            }
        )
    return digest


def _write_fake_solver(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'LegSA_PORT_NAV.nav').write_text('# h\\n0 0 0 0 0 0 0 0 0 0\\n1 0 0 0 0 0 0 0 0 0\\n')\n"
        "(out / 'LegSA_PORT_STD.csv').write_text('row,std\\n0,1\\n1,1\\n')\n"
        "(out / 'EVAL_NAV.csv').write_text('time,lat_deg\\n0,40\\n1,40\\n')\n"
        "(out / 'RUN_MANIFEST.json').write_text(json.dumps({'position_update_count': 2, 'yaw_update_count': 2}))\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _clean_fixture(tmp_path: Path) -> tuple[Path, Path]:
    code = tmp_path / "code"
    raw = tmp_path / "project" / "data" / "raw"
    clean = tmp_path / "project" / "clean"
    fix = raw / "BY2" / "fix"
    body = raw / "BY2" / "by2.txt"
    provider = clean / "providers"
    runtime = clean / "runtime"
    for path in (code, fix, provider, runtime):
        path.mkdir(parents=True, exist_ok=True)
    body.write_text("raw body source\n", encoding="utf-8")
    raw_source = fix / "gnss1-status.csv"
    raw_source.write_text("raw source\n", encoding="utf-8")
    raw_digest = _write_hash_lock(clean, raw, raw_source)

    artifacts = {
        "imu_runtime_input": provider / "runtime_inputs" / "BY2.imu",
        "gnss_runtime_input": provider / "runtime_inputs" / "BY2.gnss",
        "dual_yaw_provider": provider / "providers" / "dual.csv",
        "go2_attitude_prior": provider / "providers" / "attitude.csv",
        "go2_horizontal_velocity_prior": provider / "providers" / "velocity.csv",
    }
    for artifact in artifacts.values():
        artifact.parent.mkdir(parents=True, exist_ok=True)
    artifacts["imu_runtime_input"].write_text(
        "\n".join(f"{index * 0.1} 0 0 0 0 0 0" for index in range(31)) + "\n",
        encoding="utf-8",
    )
    artifacts["gnss_runtime_input"].write_text(
        "0 40 116 10 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 90 1.5\n"
        "1 40 116 10 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 90 1.5\n"
        "2 40 116 10 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 90 1.5\n",
        encoding="utf-8",
    )
    artifacts["dual_yaw_provider"].write_text("time,body_yaw_ned_deg\n0,90\n", encoding="utf-8")
    artifacts["go2_attitude_prior"].write_text("time,roll_rad,pitch_rad\n0,0.01,0.02\n", encoding="utf-8")
    artifacts["go2_horizontal_velocity_prior"].write_text("time,vn,ve\n0,0,0\n", encoding="utf-8")
    provider_hashes = {role: sha256_file(path) for role, path in artifacts.items()}
    input_manifest = {
        "schema_version": "paper-rebuild-clean-input-v1",
        "data_mode": "real_by2_raw",
        "raw_source_hashes": {raw_source.relative_to(raw).as_posix(): raw_digest},
        "provider_hashes": provider_hashes,
        "artifacts": {
            role: {"relative_path": path.relative_to(provider).as_posix()} for role, path in artifacts.items()
        },
        "source_roles": {raw_source.relative_to(raw).as_posix(): "GNSS status source"},
        "yaw_contract": {
            "gnss_order": "GNSS2-GNSS1",
            "lateral_to_body_offset_deg": 90.0,
            "wrap_safe_residual": True,
            "physical_baseline_gate_pass": True,
            "trace_sign_or_offset_selection": False,
        },
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
    }
    _write_fake_solver(code / "build" / "cpp" / "legsa_v23_port_core_demo")
    config = tmp_path / "DATA_PATHS.local.yaml"
    config.write_text(
        json.dumps(
            {
                "paths": {
                    "code_root": str(code),
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
    subprocess.run(["git", "init", "-q"], cwd=code, check=True)
    subprocess.run(["git", "config", "user.email", "clean-test@example.invalid"], cwd=code, check=True)
    subprocess.run(["git", "config", "user.name", "Clean Test"], cwd=code, check=True)
    subprocess.run(["git", "add", "build/cpp/legsa_v23_port_core_demo"], cwd=code, check=True)
    subprocess.run(["git", "commit", "-qm", "test solver"], cwd=code, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=code, check=True, capture_output=True, text=True
    ).stdout.strip()
    input_manifest.update(
        {
            "generator_code_commit": commit,
            "generator_worktree_dirty": False,
            "generator_config_hash": raw_digest,
            "local_path_config_hash": sha256_file(config),
        }
    )
    (provider / "CLEAN_INPUT_MANIFEST.json").write_text(json.dumps(input_manifest), encoding="utf-8")
    return config, runtime / "smoke" / "basic_dual_yaw_EKF"


def test_basic_clean_smoke_manifest_and_audit(tmp_path: Path) -> None:
    config, output = _clean_fixture(tmp_path)
    manifest = CleanPaperRunner(config).run()
    assert manifest["terminal_status"] == "PASS"
    assert manifest["old_runtime_input_count"] == 0
    assert manifest["synthetic_data_used"] is False
    assert manifest["trace_used_online"] is False
    assert manifest["receiver_imu_as_body_imu"] is False
    assert manifest["final_v23_output_solver_input"] is False
    assert manifest["LegSA_output_solver_input"] is False
    config_text = (output / "runtime_config" / "CLEAN_RUNTIME_CONFIG.yaml").read_text(encoding="utf-8")
    assert "enable_basic_dual_yaw_baseline: true" in config_text
    assert "trace_solver_input: false" in config_text
    assert audit_passed(audit_clean_runtime(load_clean_paths(config), output))


def test_clean_smoke_requires_explicit_exact_replacement(tmp_path: Path) -> None:
    config, output = _clean_fixture(tmp_path)
    runner = CleanPaperRunner(config)
    runner.run()
    sentinel = output / "stale-output.txt"
    sentinel.write_text("must disappear\n", encoding="utf-8")
    with pytest.raises(CleanRunError, match="already exists"):
        runner.run()
    runner.run(replace=True)
    assert not sentinel.exists()


def test_dirty_code_blocks_before_existing_smoke_is_replaced(tmp_path: Path) -> None:
    config, output = _clean_fixture(tmp_path)
    runner = CleanPaperRunner(config)
    runner.run()
    sentinel = output / "preserve-on-block.txt"
    sentinel.write_text("still here\n", encoding="utf-8")
    code_root = load_clean_paths(config).code_root
    solver = code_root / "build" / "cpp" / "legsa_v23_port_core_demo"
    solver.write_text(solver.read_text(encoding="utf-8") + "# dirty\n", encoding="utf-8")
    with pytest.raises(CleanRunError, match="clean committed Git worktree"):
        runner.run(replace=True)
    assert sentinel.is_file()


def test_dual_yaw_provider_locks_gnss2_minus_gnss1_plus_90(tmp_path: Path) -> None:
    fields = [
        "Time",
        "header.stamp.secs",
        "header.stamp.nsecs",
        "rel_pos_n",
        "rel_pos_e",
        "rel_pos_d",
        "rel_acc_n",
        "rel_acc_e",
        "rel_acc_d",
        "rel_valid",
        "ant_valid",
        "ant_state",
    ]
    sources = []
    for receiver, north in (("gnss1", 0.0), ("gnss2", 0.35)):
        path = tmp_path / f"{receiver}-status.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for index in range(3):
                writer.writerow(
                    {
                        "Time": 1000 + index,
                        "header.stamp.secs": 1000 + index,
                        "header.stamp.nsecs": 0,
                        "rel_pos_n": north,
                        "rel_pos_e": 0.0,
                        "rel_pos_d": 0.0,
                        "rel_acc_n": 0.01,
                        "rel_acc_e": 0.01,
                        "rel_acc_d": 0.01,
                        "rel_valid": "true",
                        "ant_valid": "true",
                        "ant_state": 2,
                    }
                )
        sources.append(path)
    rows, audit = build_physical_dual_yaw_provider(sources[0], sources[1], base_time=0.0)
    assert audit["physical_baseline_gate_pass"] is True
    assert audit["gnss_order"] == "GNSS2-GNSS1"
    assert math.isclose(rows[0]["baseline_length_m"], 0.35)
    assert math.isclose(rows[0]["body_yaw_ned_deg"], 90.0)
    assert rows[0]["wrap_safe_residual"] is True
