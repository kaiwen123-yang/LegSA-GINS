"""中文说明：N7B3 workflow audit smoke。"""

import subprocess
import sys
from pathlib import Path


def test_n7b3_go2_contact_velocity_diagnostic_activation_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_n7b3_go2_contact_velocity_diagnostic_activation.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
