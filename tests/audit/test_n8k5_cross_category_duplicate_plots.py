import subprocess
import sys

# 中文说明：audit 脚本在无真实环境变量时也必须通过 toy fixture。


def test_audit_n8k5_cross_category_duplicate_plots():
    subprocess.run([sys.executable, "scripts/audit_n8k5_cross_category_duplicate_plots.py"], check=True)
