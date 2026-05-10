import subprocess
import sys


def test_audit_n5c_raw_doppler_ablation_protocol():
    # 中文说明：测试直接调用 N5C 审计脚本，确保协议边界与 toy 报告可复现。
    proc = subprocess.run([sys.executable, "scripts/audit_n5c_raw_doppler_ablation_protocol.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "passed" in proc.stdout
