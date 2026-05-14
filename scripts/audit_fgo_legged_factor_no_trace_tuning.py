#!/usr/bin/env python3
"""Audit N8F legged factors do not use trace/final_v23 tuning.

中文说明：复用 N8F toy 审计检查 trace/final_v23 不参与调权。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "no_trace"], check=True)
    print("audit_fgo_legged_factor_no_trace_tuning passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
