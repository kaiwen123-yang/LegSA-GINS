import subprocess
import sys


def test_audit_n5d1_visual_data_coverage_spike_audit():
    # 中文说明：调用 N5D1 coverage/spike 总审计脚本。
    proc = subprocess.run([sys.executable, "scripts/audit_n5d1_visual_data_coverage_spike_audit.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
