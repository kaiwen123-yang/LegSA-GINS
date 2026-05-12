"""中文说明：contact readiness boundary audit 防止 trace/final_v23 泄漏。"""

import subprocess
import sys
from pathlib import Path


def test_go2_contact_readiness_boundaries_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_contact_readiness_boundaries.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
