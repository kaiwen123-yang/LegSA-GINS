"""中文说明：测试 N8B smoothness 不被删除过关审计入口。"""

import subprocess
import sys


def test_audit_fgo_smoothness_not_deleted_for_metric() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_smoothness_not_deleted_for_metric.py"], check=True)
