"""中文说明：调用 N4H4R2 source-backed math port audit。"""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_n4h4r2_source_backed_math_port_audit():
    completed = subprocess.run(
        ["python3", "scripts/audit_n4h4r2_source_backed_math_port.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
