"""中文说明：调用 N4H2G2 clean replay independence audit 脚本。"""

import subprocess
import sys


def test_clean_replay_independence_audit_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/audit_clean_replay_independence.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
