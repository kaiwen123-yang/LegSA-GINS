"""中文说明：N7B audit 测试通过脚本入口验证合同。"""

import subprocess
import sys
from pathlib import Path


def test_n7b_go2_velocity_contact_readiness_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_n7b_go2_velocity_contact_readiness.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
