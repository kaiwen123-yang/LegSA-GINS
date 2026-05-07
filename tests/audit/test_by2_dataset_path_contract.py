import subprocess
import sys
from pathlib import Path


def test_by2_dataset_path_contract_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_by2_data_path_contract.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
