"""中文说明：Go2 metric namespace guard audit 防止指标命名误读。"""

import subprocess
import sys
from pathlib import Path


def test_go2_metric_namespace_guard_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_metric_namespace_guard.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
