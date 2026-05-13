#!/usr/bin/env python3
"""Audit N8A Go2 candidate factor boundaries.

中文说明：验证 Go2 foot/yawrate/relative-odometry/contact 只作为 diagnostic candidate。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


def main() -> int:
    registry = build_default_factor_registry()
    candidates = set(registry.get("diagnostic_candidate_factors", []))
    expected = {"Go2FootKinematicVelocityFactor", "Go2YawRateBetweenFactor", "Go2RelativeOdometryBetweenFactor", "ContactProbabilityWeightingFactor"}
    if not expected.issubset(candidates):
        raise SystemExit("missing diagnostic Go2 candidate")
    for factor in registry.get("factors", []):
        if factor.get("factor_name") in expected and not factor.get("diagnostic_only"):
            raise SystemExit(f"candidate not diagnostic-only: {factor.get('factor_name')}")
        if factor.get("factor_name") == "ContactProbabilityWeightingFactor" and factor.get("active_default"):
            raise SystemExit("contact probability must not be hard active factor")
    print("audit_fgo_go2_candidate_factor_boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
