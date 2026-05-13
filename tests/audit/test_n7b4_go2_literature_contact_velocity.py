"""N7B4 audit 测试：验证 runner 和边界审计。"""

import subprocess
import sys


def test_n7b4_go2_literature_contact_velocity_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7b4_go2_literature_contact_velocity.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
