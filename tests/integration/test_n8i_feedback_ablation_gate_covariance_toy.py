"""N8I toy integration runs feedback ablation audits without local runtime paths.

中文说明：toy 集成测试验证 N8I 审计链路，不依赖真实 BY2 或本地绝对路径。
"""

import subprocess
import sys


def test_n8i_feedback_ablation_gate_covariance_toy():
    subprocess.run([sys.executable, "scripts/audit_n8i_feedback_ablation_gate_covariance.py"], check=True)
