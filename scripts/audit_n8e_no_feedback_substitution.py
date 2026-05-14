#!/usr/bin/env python3
"""Audit N8E no FGO feedback or substitution.

中文说明：包装 N8E 禁用 FGO 反馈和替换 EKF NAV 审计。
"""

from __future__ import annotations

from audit_n8e_formal_ablation_with_caveat import main


if __name__ == "__main__":
    raise SystemExit(main(["--check", "no_feedback_substitution"]))
