"""Audit test for N8J no future data.

中文说明：selected feedback 必须满足 no-future-data。
"""

import subprocess
import sys


def test_audit_n8j_no_future_data():
    subprocess.run([sys.executable, "scripts/audit_n8j_no_future_data.py"], check=True)
