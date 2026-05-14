#!/usr/bin/env python3
"""Audit Raw Doppler solver residual rows.

中文说明：包装 N8C3 toy 审计，只检查 solver residual 注入。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8c3_raw_doppler_fgo_factor_fix.py", "--check", "solver", "--skip-hygiene"], check=True)
    print("audit_fgo_raw_doppler_solver_residual passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
