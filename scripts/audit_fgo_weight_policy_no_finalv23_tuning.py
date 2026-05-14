#!/usr/bin/env python3
"""Audit N8D does not tune weights with final_v23.

中文说明：final_v23 不进入 solver input，也不用于权重选择。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8d_fgo_factor_weight_policy_review.py", "--check", "no_finalv23"], check=True)
    print("audit_fgo_weight_policy_no_finalv23_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
