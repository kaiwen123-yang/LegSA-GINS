"""中文说明：调用 R3B over-close audit 脚本。"""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_legsa_v23_port_overclose_audit_script():
    result = subprocess.run(
        ["python3", "scripts/audit_legsa_v23_port_overclose_audit.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout
