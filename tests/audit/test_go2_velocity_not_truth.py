"""中文说明：Go2 velocity not-truth audit 防止 claim 越界。"""

import subprocess
import sys
from pathlib import Path


def test_go2_velocity_not_truth_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_velocity_not_truth.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
