import subprocess
import sys


def test_audit_n5d_raw_doppler_visual_stress_protocol():
    # 中文说明：调用 N5D visual/stress 总审计脚本。
    proc = subprocess.run([sys.executable, "scripts/audit_n5d_raw_doppler_visual_stress_protocol.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
