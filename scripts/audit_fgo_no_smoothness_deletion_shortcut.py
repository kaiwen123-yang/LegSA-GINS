#!/usr/bin/env python3
"""Audit N8D does not delete smoothness as a final shortcut.

中文说明：no_smoothness 只能是 diagnostic-only，不能成为最终捷径。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8d_fgo_factor_weight_policy_review.py", "--check", "no_smoothness_deletion"], check=True)
    print("audit_fgo_no_smoothness_deletion_shortcut passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
