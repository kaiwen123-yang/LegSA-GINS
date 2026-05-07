import subprocess
import sys
from pathlib import Path


def test_frame_contract_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_frame_contract.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
