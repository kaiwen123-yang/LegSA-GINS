#!/usr/bin/env python3
"""Audit N5C raw Doppler ablation claim/input boundaries.

中文说明：确认 raw Doppler 消融不把 NAV-PVT、.gnss velocity 或 RTKLIB position solution 当作 solver 输入。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"FAILED: {message}")


def _read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        _fail(f"missing {rel}")
    return path.read_text(encoding="utf-8", errors="ignore")


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for pattern in [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]:
        if _git_lines(["grep", "-n", pattern, "--", "."]):
            _fail(f"local path leak: {pattern}")


def main() -> int:
    docs = "\n".join(
        _read(rel)
        for rel in [
            "docs/experiments/n5c_raw_doppler_ablation_protocol.md",
            "docs/experiments/n5c_raw_doppler_velocity_comparison.md",
            "docs/experiments/n5c_ablation_decision.md",
            "CLAIM_BOUNDARY.md",
        ]
    )
    code = "\n".join(
        _read(rel)
        for rel in [
            "src/legsa_gins/raw_gnss/raw_doppler_ablation_matrix.py",
            "src/legsa_gins/raw_gnss/raw_doppler_ablation_evaluator.py",
            "src/legsa_gins/raw_gnss/raw_doppler_velocity_comparison.py",
            "scripts/experiments/run_n5c_raw_doppler_ablation_protocol.py",
            "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
        ]
    )
    required_doc_phrases = [
        "NAV-PVT velocity is not raw Doppler",
        ".gnss vn/ve/vd is not raw Doppler",
        "RTKLIB position solution must not be used as LegSA solver input",
        "velocity-isolation variants are diagnostic-only",
        "R_scale screen is diagnostic-only",
        "paper performance claim: false",
    ]
    for phrase in required_doc_phrases:
        if phrase not in docs:
            _fail(f"missing boundary phrase: {phrase}")
    if "possible_pvt_velocity_copy_suspect" not in code:
        _fail("velocity comparison does not guard copy suspect")
    if "position_yaw_plus_raw_doppler_r1" not in code or "baseline_plus_raw_doppler_r0p5" not in code:
        _fail("diagnostic variants missing from code")
    if "proposed_factor_claim: false" not in code:
        _fail("runtime config does not force proposed_factor_claim false")
    if "paperPerformance" in code:
        _fail("unexpected paper performance symbol")
    _check_no_local_path_leak()
    print("audit_raw_doppler_ablation_boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
