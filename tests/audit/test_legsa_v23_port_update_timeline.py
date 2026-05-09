"""中文说明：调用 N4H4R3A update timeline 审计脚本。"""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_legsa_v23_port_update_timeline_audit():
    result = subprocess.run(
        ["python3", "scripts/audit_legsa_v23_port_update_timeline.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout
