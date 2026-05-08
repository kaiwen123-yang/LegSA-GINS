"""Call the N4H3 final_v23 reference-import audit.

中文说明：测试只调用 audit 脚本，确认 reference import 边界通过。
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_audit_final_v23_reference_import():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_final_v23_reference_import.py")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert "passed" in result.stdout
