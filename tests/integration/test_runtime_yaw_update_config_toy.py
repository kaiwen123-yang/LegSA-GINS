"""中文说明：N4H2C-runtime toy integration 不读取真实 artifacts。"""

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_artifacts(tmp_path: Path) -> tuple[Path, Path, Path]:
    dual = tmp_path / "dual"
    n4h2 = tmp_path / "n4h2"
    source = tmp_path / "source"
    source.mkdir(parents=True)
    _write(
        dual / "input.gnss",
        "0 40 116 10 1 1 1 1 0 0 0.1 0.1 0.1 10 1.5\n"
        "1 40 116.00001 10 1 1 1 1 0 0 0.1 0.1 0.1 20 1.5\n",
    )
    _write(
        n4h2 / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss",
        "0 40 116 10 1 1 1 1 0 0 0.1 0.1 0.1 10 1.5\n"
        "1 40 116.00001 10 1 1 1 1 0 0 0.1 0.1 0.1 20 1.5\n",
    )
    _write(dual / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 100\n0 1 40 116.00001 10 0 0 0 0 0 110\n")
    _write(n4h2 / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116.00001 10 0 0 0 0 0 20\n")
    _write(
        dual / "summary.json",
        json.dumps({"position": {"horizontal_rmse_m": 0.353, "up_rmse_m": 0.818}, "attitude": {"yaw_rmse_deg": 1.814}}),
    )
    _write(
        n4h2 / "replay" / "N4H2_REPLAY_REPORT.json",
        json.dumps({"evaluation": {"horizontal_rmse_m": 0.348, "up_rmse_m": 0.794, "yaw_rmse_deg": 93.55}}),
    )
    _write(
        n4h2 / "replay" / "kf-gins-n4h2-replay.yaml",
        "imupath: input.imu\n"
        "gnsspath: input.gnss\n"
        "initatt:\n"
        "- 0\n"
        "- 0\n"
        "- 0.7\n",
    )
    subprocess.run(["git", "init"], cwd=source, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "toy@example.invalid"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "Toy"], cwd=source, check=True)
    _write(source / "src" / "kf-gins" / "gi_engine.cpp", "double r = wrap(euler[2] - gnssdata.yaw); // scheme_C\n")
    subprocess.run(["git", "add", "src/kf-gins/gi_engine.cpp"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "yaw"], cwd=source, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return dual, n4h2, source


def test_runtime_yaw_update_config_runner_toy(tmp_path) -> None:
    dual, n4h2, source = _make_artifacts(tmp_path)
    out = tmp_path / "out"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/experiments/run_runtime_yaw_update_config_audit.py"),
            "--dual-root",
            str(dual),
            "--n4h2-artifacts-root",
            str(n4h2),
            "--external-source-root",
            str(source),
            "--output-dir",
            str(out),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    for name in [
        "ACTUAL_REPLAY_YAW_PATH_REPORT.json",
        "RUNTIME_CONFIG_PARITY_REPORT.json",
        "CURRENT_YAW_UPDATE_SOURCE_AUDIT.json",
        "YAW_UPDATE_SOURCE_HISTORY_REPORT.json",
        "YAW_RUNTIME_PATH_DIAGNOSTICS.json",
        "N4H2C_RUNTIME_YAW_DECISION_REPORT.json",
        "n4h2c_runtime_yaw_update_config_audit.md",
    ]:
        assert (out / name).exists()
    decision = json.loads((out / "N4H2C_RUNTIME_YAW_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["trace_solver_input"] is False
    assert decision["output_only_correction"] is False
    assert decision["numerical_performance_claim"] is False
    assert decision["solver_output_changed"] is False
