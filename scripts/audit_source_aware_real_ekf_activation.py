#!/usr/bin/env python3
"""Audit source-aware R scaling enters the real EKFUpdate path.

中文说明：本审计确认 scaled_R 进入 EKFUpdate，而不是 output-only correction。
"""

from __future__ import annotations

import csv
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_source_aware_real_ekf_activation failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def main() -> int:
    options = (
        (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp").read_text(encoding="utf-8")
        + "\n"
        + (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/measurement_source.hpp").read_text(encoding="utf-8")
    )
    if "enable_source_aware_weighting = false" not in options:
        _fail("enable_source_aware_weighting default is not false")
    gi = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "EKFUpdate(dz, H, scaled_R)" not in gi:
        _fail("EKFUpdate does not receive scaled_R")
    if "applySourceAwareWeighting" not in gi or "scale(R, result.combined_R_scale)" not in gi:
        _fail("source-aware R scaling path missing")
    exe = ROOT / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        if _run(["cmake", "-S", "cpp", "-B", "build/cpp"]).returncode != 0:
            _fail("cmake configure failed")
        if _run(["cmake", "--build", "build/cpp"], timeout=120).returncode != 0:
            _fail("cmake build failed")
    with tempfile.TemporaryDirectory(prefix="legsa_n6a_real_ekf_") as tmp:
        proc = _run([str(exe), "--dry-run-source-aware-toy", "--output-dir", tmp], timeout=60)
        if proc.returncode != 0:
            _fail(f"source-aware toy failed: {proc.stderr[-1000:]}")
        rows = list(csv.DictReader((Path(tmp) / "SOURCE_AWARE_WEIGHT_TRACE.csv").open("r", encoding="utf-8-sig")))
        manifest = json.loads((Path(tmp) / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if max(float(row["combined_R_scale"]) for row in rows) <= 1.0:
            _fail("toy trace has no R scale inflation")
        if not manifest.get("source_aware_R_scale_p50_p95_max_by_source"):
            _fail("manifest missing R scale stats by source")
        if manifest.get("paper_performance_claim"):
            _fail("manifest made paper claim")
    print("audit_source_aware_real_ekf_activation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
