"""N7B5 audit 测试：horizontal prior 只允许 diagnostic-only。"""

import subprocess
import sys


def test_go2_horizontal_prior_boundary_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_horizontal_prior_boundary.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
