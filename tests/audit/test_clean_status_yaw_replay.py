"""中文说明：pytest wrapper 确认 N4H2G audit script 通过。"""

import subprocess
import sys


def test_clean_status_yaw_replay_audit_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/audit_clean_status_yaw_replay.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
