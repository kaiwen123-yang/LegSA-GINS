"""中文说明：运行 R3 toy clean config，确认报告和边界旗标生成。"""

import json
import subprocess
from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import copy_toy_inputs


ROOT = Path(__file__).resolve().parents[2]


def _write_toy_dual(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(160):
        time = i * 0.01
        lines.append(f"0 {time:.2f} 30.0 120.0 10.0 0 0 0 0 0 5.0\n")
    (root / "KF_GINS_Navresult.nav").write_text("".join(lines), encoding="utf-8")


def test_legsa_v23_port_clean_replay_toy(tmp_path):
    clean = tmp_path / "clean"
    dual = tmp_path / "dual"
    out = tmp_path / "out"
    copy_toy_inputs(clean)
    _write_toy_dual(dual)
    completed = subprocess.run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_clean_replay_parity.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--output-dir",
            str(out),
            "--build-dir",
            "build/cpp",
            "--exe",
            "./build/cpp/legsa_v23_port_core_demo",
            "--allow-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in [
        "LEGSA_PORT_CLEAN_REPLAY_SUMMARY.json",
        "LEGSA_PORT_CLEAN_REPLAY_REPORT.json",
        "LEGSA_PORT_CLEAN_REPLAY_GAP_SCREEN.json",
        "LEGSA_PORT_CLEAN_REPLAY_DECISION.json",
    ]:
        assert (out / name).exists()
    decision = json.loads((out / "LEGSA_PORT_CLEAN_REPLAY_DECISION.json").read_text(encoding="utf-8"))
    assert decision["paper_performance_claim"] is False
    assert decision["proposed_factor_claim"] is False
