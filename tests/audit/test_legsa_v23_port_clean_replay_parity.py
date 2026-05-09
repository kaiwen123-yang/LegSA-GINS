"""中文说明：调用 N4H4R3 clean replay parity 审计脚本。"""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_legsa_v23_port_clean_replay_parity_audit():
    completed = subprocess.run(
        ["python3", "scripts/audit_legsa_v23_port_clean_replay_parity.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
