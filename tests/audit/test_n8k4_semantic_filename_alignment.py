import subprocess
import sys

# 中文说明：N8K4 主审计脚本的 toy fallback 应能独立通过。


def test_n8k4_semantic_filename_alignment_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_semantic_filename_alignment.py"], check=True)
