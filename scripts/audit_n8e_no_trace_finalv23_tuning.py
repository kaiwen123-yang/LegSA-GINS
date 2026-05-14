#!/usr/bin/env python3
"""Audit N8E no trace/final_v23 solver input or tuning.

中文说明：包装 N8E 禁用 trace/final_v23 调权和输入审计。
"""

from __future__ import annotations

from audit_n8e_formal_ablation_with_caveat import main


if __name__ == "__main__":
    raise SystemExit(main(["--check", "no_trace_finalv23_tuning"]))
