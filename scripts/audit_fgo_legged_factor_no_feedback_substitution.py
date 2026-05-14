#!/usr/bin/env python3
"""Audit N8F legged factors remain no-feedback and no-substitution.

中文说明：复用 N8F toy 审计检查不反馈 EKF 且不替换 EKF NAV。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "no_feedback"], check=True)
    print("audit_fgo_legged_factor_no_feedback_substitution passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
