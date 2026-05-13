"""中文说明：审计测试验证 N7C5 Go2 全字段仍是 observation 而非 truth。"""

import subprocess
import sys


def test_go2_full_field_not_truth_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_full_field_not_truth.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
