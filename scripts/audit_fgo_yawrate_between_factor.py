#!/usr/bin/env python3
"""Audit N8F yaw-rate between factor.

中文说明：复用 N8F toy 审计检查 yaw-rate between residual 和 wrap 合同。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "yawrate"], check=True)
    print("audit_fgo_yawrate_between_factor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
