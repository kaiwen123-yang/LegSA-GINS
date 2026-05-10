#!/usr/bin/env python3
"""Audit N6A spike-response boundary.

中文说明：N5D1 spike 时间只能作为 evaluation-only sentinel；source-aware policy
必须使用 residual/metadata，而不是硬编码 spike epoch。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.source_aware.source_aware_spike_response import evaluate_spike_response, write_spike_response_report


def _fail(message: str) -> None:
    raise SystemExit(f"audit_source_aware_spike_response_boundary failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def main() -> int:
    policy_text = "\n".join(
        [
            (ROOT / "src/legsa_gins/source_aware/lsim_metric.py").read_text(encoding="utf-8"),
            (ROOT / "src/legsa_gins/source_aware/oim_metric.py").read_text(encoding="utf-8"),
            (ROOT / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp").read_text(encoding="utf-8"),
        ]
    )
    if "96.4067945" in policy_text or "97.0067945" in policy_text:
        _fail("source-aware policy hardcodes N5D1 spike times")
    if "residual" not in policy_text or "metadata" not in policy_text:
        _fail("source-aware policy does not visibly use residual/metadata")
    spike_module = (ROOT / "src/legsa_gins/source_aware/source_aware_spike_response.py").read_text(encoding="utf-8")
    if "evaluation-only" not in spike_module and "事后 sentinel" not in spike_module:
        _fail("spike response module does not state evaluation-only boundary")
    exe = ROOT / "build/cpp/legsa_v23_port_core_demo"
    if not exe.exists():
        _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
        _run(["cmake", "--build", "build/cpp"], timeout=120)
    with tempfile.TemporaryDirectory(prefix="legsa_n6a_spike_") as tmp:
        tmp_path = Path(tmp)
        proc = _run([str(exe), "--dry-run-source-aware-toy", "--output-dir", str(tmp_path / "toy")], timeout=60)
        if proc.returncode != 0:
            _fail(f"source-aware toy failed: {proc.stderr[-1000:]}")
        spike_report = {
            "spike_epochs": [
                {"time": 0.6},
            ],
            "spike_count": 1,
        }
        spike_path = tmp_path / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json"
        spike_path.write_text(json.dumps(spike_report), encoding="utf-8")
        report = evaluate_spike_response(
            spike_report_path=spike_path,
            source_aware_trace_path=tmp_path / "toy" / "SOURCE_AWARE_WEIGHT_TRACE.csv",
            tolerance_sec=0.2,
        )
        write_spike_response_report(report, tmp_path / "N6A_SPIKE_RESPONSE_REPORT.json")
        if not (tmp_path / "N6A_SPIKE_RESPONSE_REPORT.json").exists():
            _fail("toy spike response report missing")
        if report.get("hardcoded_spike_time_weighting") or report.get("trace_solver_input"):
            _fail("spike boundary flags invalid")
    print("audit_source_aware_spike_response_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
