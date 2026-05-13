"""N7B4 integration toy 测试：用合成数据跑完整 diagnostic 流程。"""

import subprocess
import sys


def test_n7b4_go2_literature_contact_velocity_toy():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7b4_go2_literature_contact_velocity.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
