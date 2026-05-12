"""中文说明：N7B2 contact-state v2 不能激活 solver prior。"""

import subprocess
import sys
from pathlib import Path


def test_go2_contact_v2_no_solver_activation_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_contact_v2_no_solver_activation.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
