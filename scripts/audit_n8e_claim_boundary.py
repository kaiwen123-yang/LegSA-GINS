#!/usr/bin/env python3
"""Audit N8E claim boundary.

中文说明：包装 N8E claim boundary 专项审计。
"""

from __future__ import annotations

from audit_n8e_formal_ablation_with_caveat import main


if __name__ == "__main__":
    raise SystemExit(main(["--check", "claim_boundary"]))
