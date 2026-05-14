"""中文说明：测试 N8C 必需图像非空审计入口。"""

import subprocess
import sys


def test_audit_n8c_required_figures_nonempty() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8c_required_figures_nonempty.py"], check=True)
