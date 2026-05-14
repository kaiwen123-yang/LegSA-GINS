#!/usr/bin/env python3
"""Audit N8E no paper-performance or outperform-final_v23 claim.

中文说明：包装 N8E 无论文性能 claim 专项审计。
"""

from __future__ import annotations

from audit_n8e_formal_ablation_with_caveat import main


if __name__ == "__main__":
    raise SystemExit(main(["--check", "no_performance_claim"]))
