#!/usr/bin/env python3
"""Audit N8F1 no-feedback boundary.

中文说明：复用 N8F1 toy 审计检查不反馈 EKF、不替换 NAV。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f1_legged_candidate_factor_visual_validation.py", "--check", "no_feedback"], check=True)
    print("audit_n8f1_no_feedback_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

