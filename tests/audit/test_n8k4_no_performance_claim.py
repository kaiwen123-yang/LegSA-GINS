import subprocess
import sys

# 中文说明：N8K4 测试确认没有论文性能 claim。


def test_n8k4_no_performance_claim_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_no_performance_claim.py"], check=True)
