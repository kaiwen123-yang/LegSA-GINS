"""中文说明：调用 source-backed math port static parity audit。"""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_kfgins_math_port_static_parity_audit():
    completed = subprocess.run(
        ["python3", "scripts/source_audit/audit_kfgins_math_port_static_parity.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
