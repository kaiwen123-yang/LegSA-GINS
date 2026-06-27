"""中文说明：PAPER10L 禁止大矩阵运行静态审计测试。"""

import subprocess
import sys
from pathlib import Path


def test_paper10l_no_large_run_audit_passes():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "audit_paper10l_no_large_run.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
