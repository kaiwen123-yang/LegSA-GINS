"""中文说明：N7B3 runner 用合成数据和 fake runtime 执行端到端 diagnostic outputs。"""

import subprocess
import sys
from pathlib import Path

from scripts.audit_n7b3_go2_contact_velocity_diagnostic_activation import _prepare_runtime


def test_n7b3_go2_contact_velocity_diagnostic_toy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    _prepare_runtime(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/experiments/run_n7b3_go2_contact_velocity_diagnostic_activation.py"),
            "--n7a-root",
            str(tmp_path / "n7a"),
            "--n7b-root",
            str(tmp_path / "n7b"),
            "--n7b2-root",
            str(tmp_path / "n7b2"),
            "--n7b2a-root",
            str(tmp_path / "n7b2a"),
            "--n5b-root",
            str(tmp_path / "n5b"),
            "--n6b-root",
            str(tmp_path / "n6b"),
            "--clean-root",
            str(tmp_path / "clean"),
            "--output-dir",
            str(tmp_path / "out"),
            "--figure-output-dir",
            str(tmp_path / "fig"),
            "--build-dir",
            str(tmp_path / "build"),
            "--exe",
            str(tmp_path / "fake_demo.py"),
            "--allow-run",
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (tmp_path / "out/GO2_VELOCITY_FRAME_REVIEW_REPORT.json").exists()
    assert (tmp_path / "out/N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_DECISION_REPORT.json").exists()
    assert (tmp_path / "out/N7B3_FIGURE_MANIFEST.json").exists()
