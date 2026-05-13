"""中文说明：测试 state/epoch mapping 审计脚本入口。"""

import subprocess
import sys


def test_audit_fgo_state_epoch_mapping() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_state_epoch_mapping.py"], check=True)
