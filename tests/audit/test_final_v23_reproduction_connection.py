import subprocess
import sys
from pathlib import Path


def test_final_v23_reproduction_connection_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_final_v23_reproduction_connection.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
