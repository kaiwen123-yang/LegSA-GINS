"""中文说明：Go2 contact v2 physical sanity audit 必须保持 no solver activation。"""

import subprocess
import sys
from pathlib import Path


def test_go2_contact_v2_physical_sanity_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_contact_v2_physical_sanity.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
