#!/usr/bin/env python3
"""Audit N8C2 RawDopplerVelocityFactor activation report.

中文说明：包装 N8C2 toy 审计，只检查 Raw Doppler 激活分类。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8c2_fgo_factor_activation_review.py", "--check", "raw", "--skip-hygiene"], check=True)
    print("audit_fgo_raw_doppler_factor_activation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
