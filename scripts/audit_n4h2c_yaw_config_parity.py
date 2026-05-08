#!/usr/bin/env python3
"""Audit N4H2C yaw config parity planning scope.

中文说明：本脚本只验证 N4H2C 计划文档和边界字符串，不实现 yaw 修正、
不调参、不读取 trace 作为 solver input，也不做性能结论。
"""

from __future__ import annotations

from pathlib import Path
import sys


DOC = Path("docs/experiments/n4h2c_yaw_config_parity_audit.md")
PROMPT = Path("docs/codex_prompts/N4H2C_yaw_config_parity_audit.md")

REQUIRED_TERMS = [
    "yaw_sign",
    "yaw_install_offset_deg",
    "yaw_std_mode",
    "A1_dual_diff formula",
    "yaw_ned = 90 - yaw_body",
    "trace yaw convention",
    "antlever / antenna order",
    "no trace solver input",
    "no output-only correction",
    "no formal offset selection without physical antenna-order evidence",
    "no formal numerical performance claim",
    "no raw Doppler",
    "no Go2 prior",
    "no source-aware weighting",
    "no LSIM/OIM",
    "no FGO",
    "no full EKF implementation",
]


def _read(path: Path, root: Path) -> str:
    full_path = root / path
    if not full_path.exists():
        raise AssertionError(f"missing required file: {path}")
    return full_path.read_text(encoding="utf-8")


def audit(root: Path) -> None:
    text = _read(DOC, root) + "\n" + _read(PROMPT, root)
    missing = [term for term in REQUIRED_TERMS if term not in text]
    if missing:
        raise AssertionError(f"missing N4H2C planning terms: {missing}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        audit(root)
    except AssertionError as exc:
        print(f"N4H2C yaw config parity audit failed: {exc}")
        return 1
    print("N4H2C yaw config parity audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
