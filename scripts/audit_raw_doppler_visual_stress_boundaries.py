#!/usr/bin/env python3
"""Audit N5D raw Doppler visual/stress claim boundaries.

中文说明：确认 N5D 不把 NAV-PVT、.gnss velocity、RTKLIB position solution、
stress/R-scale/STD-scale 诊断写成 proposed/paper claim。
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
            "docs/experiments/n5d_raw_doppler_visual_validation.md",
            "docs/experiments/n5d_raw_doppler_stress_protocol.md",
            "docs/experiments/n5d_decision.md",
            "CLAIM_BOUNDARY.md",
        ]
    )
    code = "\n".join(
        _read(rel)
        for rel in [
            "src/legsa_gins/raw_gnss/raw_doppler_stress_matrix.py",
            "src/legsa_gins/raw_gnss/raw_doppler_stress_runner.py",
            "src/legsa_gins/raw_gnss/raw_doppler_visual_loader.py",
            "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
            "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp",
        ]
    )
    for phrase in [
        "NAV-PVT velocity is not raw Doppler",
        ".gnss vn/ve/vd is not raw Doppler",
        "RTKLIB position solution must not be used as LegSA solver input",
        "Receiver velocity stress variants are diagnostic-only",
        "R-scale and STD-scale screens are not tuning claims",
        "paper performance claim: false",
        "No LSIM/OIM, Go2 prior, or FGO",
    ]:
        if phrase not in docs:
            _fail(f"missing boundary phrase: {phrase}")
    for snippet in [
        "diagnostic_stress_only",
        "receiver_velocity_stress_mode",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "RTKLIB Doppler provider",
        "不是 NAV-PVT",
        "不是 raw Doppler 来源",
    ]:
        if snippet not in code:
            _fail(f"missing code boundary snippet: {snippet}")
    _check_no_local_path_leak()
    print("audit_raw_doppler_visual_stress_boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
