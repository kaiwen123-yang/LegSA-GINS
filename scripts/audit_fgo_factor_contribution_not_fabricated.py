#!/usr/bin/env python3
"""Audit N8C2 candidate contribution is not fabricated or formalized.

中文说明：包装 N8C2 toy 审计，确认候选因子没有被伪造成正式贡献。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8c2_fgo_factor_activation_review.py", "--check", "contribution", "--skip-hygiene"], check=True)
    print("audit_fgo_factor_contribution_not_fabricated passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
