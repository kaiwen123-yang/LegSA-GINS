#!/usr/bin/env python3
"""Audit N8F1 required figures are generated and nonempty.

中文说明：复用 N8F1 toy 审计的图像非空检查。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f1_legged_candidate_factor_visual_validation.py", "--check", "figures"], check=True)
    print("audit_n8f1_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

