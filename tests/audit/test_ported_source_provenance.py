"""中文说明：测试 ported source provenance audit，不检查性能。"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/source_audit/audit_ported_source_provenance.py"


def test_ported_source_provenance_audit_passes():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout.lower()

