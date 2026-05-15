import subprocess
import sys

# 中文说明：yaw residual 与 yaw wrap check 的语义必须区分。


def test_n8k4_yaw_plot_semantics_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_yaw_plot_semantics.py"], check=True)
