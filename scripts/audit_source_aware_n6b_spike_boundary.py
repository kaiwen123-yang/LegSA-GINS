#!/usr/bin/env python3
"""Audit N6B spike response remains evaluation-only.

中文说明：spike 时间只用于事后报告，不进入 solver policy。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.source_aware.source_aware_n6b_spike_response import (
    evaluate_n6b_spike_response,
    write_n6b_spike_response_report,
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_source_aware_n6b_spike_boundary failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def main() -> int:
    policy_text = "\n".join(
        [
            (ROOT / "src/legsa_gins/source_aware/source_aware_n6b_policy.py").read_text(encoding="utf-8"),
            (ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp").read_text(encoding="utf-8"),
        ]
    )
    if "96.4067945" in policy_text or "97.0067945" in policy_text:
        _fail("source-aware policy hardcodes N5D1 spike times")
    if "trace" in policy_text and "SOURCE_AWARE_WEIGHT_TRACE.csv" in policy_text:
        _fail("policy references trace file")
    spike_module = (ROOT / "src/legsa_gins/source_aware/source_aware_n6b_spike_response.py").read_text(encoding="utf-8")
    if "Evaluation-only" not in spike_module and "sentinels only" not in spike_module:
        _fail("N6B spike module missing evaluation-only boundary")
    exe = ROOT / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
        _run(["cmake", "--build", "build/cpp"], timeout=120)
    with tempfile.TemporaryDirectory(prefix="legsa_n6b_spike_") as tmp:
        tmp_path = Path(tmp)
        proc = _run([str(exe), "--dry-run-source-aware-toy", "--output-dir", str(tmp_path / "toy")], timeout=60)
        if proc.returncode != 0:
            _fail(f"N6B source-aware toy failed: {proc.stderr[-1000:]}")
        spike_path = tmp_path / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json"
        spike_path.write_text(json.dumps({"spike_epochs": [{"time": 0.6}], "spike_count": 1}), encoding="utf-8")
        report = evaluate_n6b_spike_response(
            spike_report_path=spike_path,
            source_aware_trace_path=tmp_path / "toy" / "SOURCE_AWARE_WEIGHT_TRACE.csv",
            tolerance_sec=0.2,
        )
        write_n6b_spike_response_report(report, tmp_path / "N6B_SPIKE_RESPONSE_REPORT.json")
        if not (tmp_path / "N6B_SPIKE_RESPONSE_REPORT.json").exists():
            _fail("toy N6B spike response report missing")
        if report.get("hardcoded_spike_time_weighting") or report.get("trace_solver_input"):
            _fail("spike boundary flags invalid")
    print("audit_source_aware_n6b_spike_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
