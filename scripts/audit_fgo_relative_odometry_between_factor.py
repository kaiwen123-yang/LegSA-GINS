#!/usr/bin/env python3
"""Audit N8F relative odometry between factor.

中文说明：复用 N8F toy 审计检查相对里程计 between residual。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "relative"], check=True)
    print("audit_fgo_relative_odometry_between_factor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
