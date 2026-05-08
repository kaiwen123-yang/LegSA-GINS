"""Call the N4H3 transplant-plan audit.

中文说明：测试只验证 transplant plan 文档合同，不实现算法。
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_audit_n4h3_transplant_plan():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_n4h3_transplant_plan.py")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert "passed" in result.stdout
