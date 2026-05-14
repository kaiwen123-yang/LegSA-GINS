#!/usr/bin/env python3
"""Audit N8F1 factor signal review.

中文说明：复用 N8F1 toy 审计的 factor signal 检查。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f1_legged_candidate_factor_visual_validation.py", "--check", "signal"], check=True)
    print("audit_n8f1_factor_signal_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

