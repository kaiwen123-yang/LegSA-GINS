"""中文说明：集成测试使用 toy 流程验证 N7C3 有界自适应策略可生成完整报告。"""

import subprocess
import sys


def test_n7c3_go2_horizontal_velocity_bounded_adaptive_std_toy():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c3_go2_horizontal_velocity_bounded_adaptive_std.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
