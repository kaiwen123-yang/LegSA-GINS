#!/usr/bin/env python3
"""Audit Raw Doppler is not proxy-only after N8C3.

中文说明：包装 N8C3 toy 审计，确认 Raw Doppler 有 direct equation。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8c3_raw_doppler_fgo_factor_fix.py", "--check", "no_proxy", "--skip-hygiene"], check=True)
    print("audit_fgo_raw_doppler_no_proxy_only passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
