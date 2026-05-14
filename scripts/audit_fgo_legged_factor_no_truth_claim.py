#!/usr/bin/env python3
"""Audit N8F legged factors make no Go2 truth claim.

中文说明：复用 N8F toy 审计检查 Go2 不被写成真值。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "no_truth"], check=True)
    print("audit_fgo_legged_factor_no_truth_claim passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
