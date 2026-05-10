import subprocess
import sys


def test_audit_raw_doppler_ablation_boundaries():
    # 中文说明：测试边界审计，防止把 receiver-native velocity 或 RTKLIB position solution 冒充 raw Doppler。
    proc = subprocess.run([sys.executable, "scripts/audit_raw_doppler_ablation_boundaries.py"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "passed" in proc.stdout
