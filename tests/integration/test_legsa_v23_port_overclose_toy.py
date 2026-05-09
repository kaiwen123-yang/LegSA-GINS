"""中文说明：运行 R3B toy over-close audit，确认 runtime-only 报告生成。"""

import subprocess
from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import copy_toy_inputs


ROOT = Path(__file__).resolve().parents[2]


def _write_toy_dual(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(180):
        time = i * 0.01
        lines.append(f"0 {time:.2f} 30.0 120.0 10.0 0 0 0 0 0 5.0\n")
    (root / "KF_GINS_Navresult.nav").write_text("".join(lines), encoding="utf-8")


def test_legsa_v23_port_overclose_toy(tmp_path):
    clean = tmp_path / "clean"
    dual = tmp_path / "dual"
    r3 = tmp_path / "r3"
    r3a = tmp_path / "r3a"
    out = tmp_path / "out"
    copy_toy_inputs(clean)
    _write_toy_dual(dual)
    r3.mkdir()
    r3a.mkdir()
    result = subprocess.run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_overclose_audit.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--r3-root",
            str(r3),
            "--r3a-root",
            str(r3a),
            "--output-dir",
            str(out),
            "--allow-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for name in [
        "PORT_MEASUREMENT_COPY_GUARD_REPORT.json",
        "PORT_REFERENCE_INDEPENDENCE_REPORT.json",
        "PORT_COVARIANCE_CONFIG_PARITY_REPORT.json",
        "PORT_RESIDUAL_GAIN_AUDIT_REPORT.json",
        "PORT_OVERCLOSE_AUDIT_REPORT.json",
        "PORT_OVERCLOSE_DECISION_REPORT.json",
    ]:
        assert (out / name).exists()
