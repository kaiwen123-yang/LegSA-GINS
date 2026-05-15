"""N8J toy integration runs final validation audits without local runtime paths.

中文说明：toy 集成测试验证 N8J 审计链路，不依赖真实 BY2 或本地绝对路径。
"""

import subprocess
import sys


def test_n8j_feedback_final_validation_toy():
    subprocess.run([sys.executable, "scripts/audit_n8j_feedback_final_validation.py"], check=True)
