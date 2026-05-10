import subprocess
import sys


def test_audit_n5d_required_figures_nonempty():
    # 中文说明：mandatory figure 必须有绘图数据覆盖，不能只检查文件存在。
    proc = subprocess.run([sys.executable, "scripts/audit_n5d_required_figures_nonempty.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
