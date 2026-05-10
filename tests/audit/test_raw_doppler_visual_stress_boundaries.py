import subprocess
import sys


def test_audit_raw_doppler_visual_stress_boundaries():
    # 中文说明：调用 N5D 边界审计脚本，防止 stress 诊断被写成性能/调参 claim。
    proc = subprocess.run([sys.executable, "scripts/audit_raw_doppler_visual_stress_boundaries.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
