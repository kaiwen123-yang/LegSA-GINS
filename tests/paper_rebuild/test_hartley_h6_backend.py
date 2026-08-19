from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO / "src/legsa_gins/paper_rebuild/horizontal_literature"


def _isolated_h5():
    package_name = "_test_hartley_h6_backend_isolated"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5"):
        name = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / f"{basename}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h5"]


h5 = _isolated_h5()


def _record(index: int) -> str:
    return f"""stamp:
  sec: {100 + index}
  nanosec: 0
imu_state:
  gyroscope: [0.0, 0.0, 0.0]
  accelerometer: [0.0, -0.1712081071, 9.808505889]
foot_force: [40,41,42,43]
foot_position_body: [0.3,0.2,-0.4,0.3,-0.2,-0.4,-0.3,0.2,-0.4,-0.3,-0.2,-0.4]
---
"""


def _cache(tmp_path: Path) -> Path:
    source = tmp_path / "by2.txt"
    source.write_text("header: fixture\n" + "".join(_record(index) for index in range(7)))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    identity = h5.verify_source_identity(
        source, expected_raw_size=source.stat().st_size, expected_raw_sha256=digest,
        prefix_end_exclusive=source.stat().st_size, expected_prefix_sha256=digest,
    )
    cache = tmp_path / "cache.bin"
    h5.build_immutable_cache(identity, cache, tmp_path / "events.jsonl", expected_records=7)
    return cache


def _config(cache: Path, run_id: str, yaw: float | None) -> str:
    values = [
        ("run_id", run_id), ("backend_id", h5.H5_BACKEND_ID),
        ("process_policy", "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61"),
        ("sigma_fk_m", "0.010"), ("expected_records", "7"),
        ("cache_sha256", h5.sha256_file(cache)), ("code_commit", "fixture"),
        ("task_start_head", "fixture"), ("task_start_dirty_or_precommit", "true"),
        ("scoped_source_manifest_sha256", "fixture"),
        ("native_executable_sha256", "fixture"),
        ("later_final_commit_mapping", "NOT_AVAILABLE_PRECOMMIT"),
    ]
    if yaw is not None:
        values.extend((("execution_phase", "H6_GAUGE_ENSEMBLE"), ("initial_gauge_yaw_deg", f"{yaw:.1f}")))
    base = "".join(f"{key}={value}\n" for key, value in values)
    return base + f"config_hash={hashlib.sha256(base.encode()).hexdigest()}\n"


def _run(executable: Path, cache: Path, output: Path, run_id: str, yaw: float | None) -> None:
    output.mkdir()
    config = output / "NATIVE_CONFIG.cfg"
    config.write_text(_config(cache, run_id, yaw))
    environment = dict(os.environ)
    environment.update({key: "1" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    subprocess.run([str(executable), str(cache), str(config), str(output)], check=True, env=environment)


def test_native_zero_runner_parity_and_nonzero_full_initial_transform(tmp_path: Path) -> None:
    executable = Path(os.environ.get("HARTLEY_H6_RUNNER", "/tmp/hartley_h6_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H6 native fixture runner is not built")
    cache = _cache(tmp_path)
    h5_output = tmp_path / "h5"
    zero_output = tmp_path / "zero"
    nonzero_output = tmp_path / "nonzero"
    _run(executable, cache, h5_output, h5.H5_PRIMARY_RUN_ID, None)
    _run(executable, cache, zero_output, "H6_YAW_000_PARITY", 0.0)
    _run(executable, cache, nonzero_output, "H6_YAW_M050", -50.0)
    scientific = (
        "NAV.csv", "COVARIANCE_DIAGONALS.csv", "CONTACT_STATE.csv",
        "CONTACT_EVENT_LEDGER.csv", "KINEMATIC_INNOVATIONS.csv", "NIS_DIAGNOSTICS.csv",
        "COVARIANCE_CHECKPOINT_INDEX.csv", "EXECUTION_LEDGER.csv", "COVARIANCE_CHECKPOINTS.bin",
    )
    assert all((h5_output / name).read_bytes() == (zero_output / name).read_bytes() for name in scientific)
    summary = json.loads((nonzero_output / "NATIVE_SUMMARY.json").read_text())
    assert summary["initial_gauge_yaw_deg"] == -50
    assert summary["expected_native_euler_yaw_offset_deg"] == 50
    assert summary["initial_contact_general_rule_applied"] is True
    assert summary["initial_contact_transform_residual"] < 1.0e-14
    assert summary["initial_covariance_congruence_relative_fro_error"] < 1.0e-14
    h5_nav = list(csv.DictReader((h5_output / "NAV.csv").open()))
    gauge_nav = list(csv.DictReader((nonzero_output / "NAV.csv").open()))
    zero_yaw = np.arctan2(float(h5_nav[0]["r10"]), float(h5_nav[0]["r00"]))
    gauge_yaw = np.arctan2(float(gauge_nav[0]["r10"]), float(gauge_nav[0]["r00"]))
    assert gauge_yaw - zero_yaw == pytest.approx(np.deg2rad(50.0), abs=2.0e-14)
