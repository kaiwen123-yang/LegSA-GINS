#!/usr/bin/env python3
"""Audit N8D has no paper performance claim.

中文说明：N8D 输出仅是工程审查，不声明论文性能提升。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8d_fgo_factor_weight_policy_review.py", "--check", "no_paper_claim"], check=True)
    print("audit_fgo_weight_policy_no_paper_claim passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
