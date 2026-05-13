"""中文说明：审计测试运行 N7C5 Go2 full proprioceptive factor mining workflow。"""

import subprocess
import sys


def test_n7c5_go2_full_proprioceptive_factor_mining_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c5_go2_full_proprioceptive_factor_mining.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
