"""中文说明：N4H4A audit 测试只检查框架边界，不验证性能。"""

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/audit_n4h4a_legsa_v23_core_foundation.py"


def test_n4h4a_legsa_v23_core_foundation_audit_passes():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "N4H4A LegSA-v23-core foundation audit passed." in completed.stdout
