#!/usr/bin/env python3
"""Audit N6A LSIM/OIM definition probe.

中文说明：确认 N6A 在没有既有可执行定义时采用可审计定义；不读取 trace 或
final_v23 output 作为调权输入。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.source_aware.source_aware_definition_probe import probe_source_aware_definitions, write_probe_report


def _fail(message: str) -> None:
    raise SystemExit(f"audit_source_aware_definition_probe failed: {message}")


def main() -> int:
    report = probe_source_aware_definitions(ROOT)
    if report.get("found_existing_definition") is not False:
        _fail("unexpected pre-N6A concrete LSIM/OIM definition detected")
    if report.get("adopted_auditable_definition") is not True:
        _fail("auditable N6A definition was not adopted")
    if "LSIM" not in report.get("adopted_definition", {}) or "OIM" not in report.get("adopted_definition", {}):
        _fail("adopted LSIM/OIM definition missing")
    with tempfile.TemporaryDirectory(prefix="legsa_n6a_definition_probe_") as tmp:
        path = Path(tmp) / "SOURCE_AWARE_DEFINITION_PROBE_REPORT.json"
        write_probe_report(report, path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if loaded.get("trace_solver_input") or loaded.get("final_v23_output_solver_input"):
            _fail("definition probe leaked forbidden solver inputs")
    print("audit_source_aware_definition_probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
