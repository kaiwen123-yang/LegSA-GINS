"""N8H toy integration runs the visual validation pipeline without local runtime paths.

中文说明：toy 集成测试不依赖本机运行期绝对路径。
"""

import subprocess
import sys


def test_n8h_fgo_feedback_visual_validation_toy():
    subprocess.run([sys.executable, "scripts/audit_n8h_fgo_feedback_visual_validation.py"], check=True)
