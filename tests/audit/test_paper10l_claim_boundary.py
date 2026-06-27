"""中文说明：PAPER10L claim boundary 静态审计测试。"""

import subprocess
import sys
from pathlib import Path


def test_paper10l_claim_boundary_audit_passes():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "audit_paper10l_claim_boundary.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
