"""中文说明：N4E audit 测试运行脚本级审计，确保 toy adapter 输出和边界字符串闭合。
"""

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_by2_input_adapter_audit_script_passes():
    result = subprocess.run(
        [sys.executable, "scripts/audit_by2_input_adapters.py"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert "passed" in result.stdout
