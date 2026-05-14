#!/usr/bin/env python3
"""Audit N8C mandatory figure contract.

中文说明：复用 N8C toy runner，确认 22 张必需图像非空。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8c_no_feedback_fgo_visual_validation.py"], check=True)
    print("audit_n8c_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
