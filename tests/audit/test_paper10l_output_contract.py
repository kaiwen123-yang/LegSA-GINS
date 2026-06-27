"""中文说明：PAPER10L 输出合同和 solver 输入边界静态审计测试。"""

import subprocess
import sys
from pathlib import Path


def test_paper10l_output_contract_audit_passes():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "audit_paper10l_output_contract.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
