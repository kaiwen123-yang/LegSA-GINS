"""中文说明：集成测试复用 N7C5 toy audit 验证 runner 可完整产物化。"""

import subprocess
import sys


def test_n7c5_go2_full_proprioceptive_factor_mining_toy():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c5_go2_full_proprioceptive_factor_mining.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
