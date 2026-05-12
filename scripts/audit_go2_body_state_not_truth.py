#!/usr/bin/env python3
"""Compatibility audit for N7A Go2 body-state not-truth boundary.

中文说明：N7A 原始审计名为 audit_go2_weak_prior_not_truth.py；本入口只复用该
审计，便于后续 release gate 使用更直观的 body-state 命名，不修改 solver。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 中文说明：直接执行本脚本时，确保可以导入同目录上层的 scripts 审计模块。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_go2_weak_prior_not_truth import main


if __name__ == "__main__":
    raise SystemExit(main())
