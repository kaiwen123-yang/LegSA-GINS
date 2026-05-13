"""N7B4 audit 测试：Go2 activation 只能 diagnostic-only。"""

import subprocess
import sys


def test_go2_diagnostic_activation_only_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_diagnostic_activation_only.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
