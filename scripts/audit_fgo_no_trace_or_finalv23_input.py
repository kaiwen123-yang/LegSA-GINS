#!/usr/bin/env python3
"""Audit N8A trace/final_v23 input boundary.

中文说明：验证 trace/final_v23 output 不作为 FGO factor 输入。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_backend_discovery import discover_fgo_backend
from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


def main() -> int:
    backend = discover_fgo_backend()
    registry = build_default_factor_registry()
    if backend.get("trace_solver_input") or backend.get("final_v23_output_solver_input"):
        raise SystemExit("backend trace/final_v23 boundary failed")
    if registry.get("trace_solver_input") or registry.get("final_v23_output_solver_input"):
        raise SystemExit("registry trace/final_v23 boundary failed")
    for factor in registry.get("factors", []):
        if factor.get("trace_input") or factor.get("finalv23_input"):
            raise SystemExit(f"factor boundary failed: {factor.get('factor_name')}")
    print("audit_fgo_no_trace_or_finalv23_input passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
