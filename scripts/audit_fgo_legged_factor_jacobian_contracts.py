#!/usr/bin/env python3
"""Audit N8F legged factor Jacobian contracts.

中文说明：复用 N8F toy 审计检查四类候选因子的 Jacobian 合同。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "jacobian"], check=True)
    print("audit_fgo_legged_factor_jacobian_contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
