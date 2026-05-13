"""中文说明：审计测试确认 N7C4 不把 Go2 velocity 当 truth。"""

import subprocess
import sys


def test_go2_prior_strength_no_truth_claim_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_prior_strength_no_truth_claim.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
