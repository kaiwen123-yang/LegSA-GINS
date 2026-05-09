"""中文说明：测试 N4H4R1 port-core audit，确认 toy demo 和边界字段。"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_n4h4r1_source_backed_port_core.py"


def test_n4h4r1_source_backed_port_core_audit_passes():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout.lower()

