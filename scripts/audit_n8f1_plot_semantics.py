#!/usr/bin/env python3
"""Audit N8F1 plot semantics.

中文说明：复用 N8F1 toy 审计检查图像语义不越界。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f1_legged_candidate_factor_visual_validation.py", "--check", "semantics"], check=True)
    print("audit_n8f1_plot_semantics passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

