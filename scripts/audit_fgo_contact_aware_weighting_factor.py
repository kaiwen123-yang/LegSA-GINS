#!/usr/bin/env python3
"""Audit N8F contact-aware weighting layer.

中文说明：复用 N8F toy 审计检查 contact 只作为权重层。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "contact"], check=True)
    print("audit_fgo_contact_aware_weighting_factor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
