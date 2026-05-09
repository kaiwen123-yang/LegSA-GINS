"""中文说明：调用 N4H4D5 gain/feedback isolation audit。"""

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_n4h4d5_gain_feedback_isolation_audit():
    result = subprocess.run(
        [sys.executable, "scripts/audit_legsa_v23_gain_feedback_isolation.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "audit_legsa_v23_gain_feedback_isolation passed" in result.stdout
