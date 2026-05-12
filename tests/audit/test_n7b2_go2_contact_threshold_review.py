"""中文说明：N7B2 主审计脚本必须通过。"""

import subprocess
import sys
from pathlib import Path


def test_n7b2_go2_contact_threshold_review_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_n7b2_go2_contact_threshold_review.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
