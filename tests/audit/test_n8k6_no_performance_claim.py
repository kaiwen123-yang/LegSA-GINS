import subprocess
import sys

# 中文说明：N8K6 测试确认没有论文性能 claim。


def test_audit_n8k6_no_performance_claim_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_no_performance_claim.py"], check=True)
