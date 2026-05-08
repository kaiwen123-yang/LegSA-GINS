"""中文说明：调用 process_data noise provenance audit 脚本并确认 passed。"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_audit_process_data_noise_provenance():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_process_data_noise_provenance.py")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert "passed" in result.stdout
