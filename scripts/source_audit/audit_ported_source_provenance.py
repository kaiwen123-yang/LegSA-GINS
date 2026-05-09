#!/usr/bin/env python3
"""Audit provenance headers and port manifest for N4H4R1.

中文说明：确认移植文件有 source commit header，且 manifest 明确禁用 final_v23
输出替代、trace solver input 和性能 claim。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORT_ROOT = ROOT / "cpp/legsa_v23_port_core"
SOURCE_COMMIT = "5a4471efd4fcfcdc31e258a677af354c652ff16f"


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"Ported source provenance audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def main() -> int:
    manifest_path = PORT_ROOT / "PORT_MANIFEST.json"
    if not manifest_path.exists():
        return _fail("PORT_MANIFEST.json missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("copied_or_refactored_files"):
        return _fail("copied_or_refactored_files is empty")
    excluded = " ".join(manifest.get("excluded_files", []))
    for term in ["raw", "final_results", "tmp"]:
        if term not in excluded:
            return _fail("excluded_files missing required exclusion", [term])
    if manifest.get("final_v23_is_proposed") is not False:
        return _fail("final_v23_is_proposed must be false")
    if manifest.get("source_commit") != SOURCE_COMMIT:
        return _fail("source commit mismatch", [str(manifest.get("source_commit"))])

    source_files = [
        path
        for path in PORT_ROOT.rglob("*")
        if path.suffix in {".cpp", ".hpp", ".h"} and path.is_file()
    ]
    missing = []
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore")[:700]
        if SOURCE_COMMIT not in text or "Source reference: KF-GINS-graduation-design" not in text:
            missing.append(str(path.relative_to(ROOT)))
    if missing:
        return _fail("ported files missing source commit header", missing)
    print("Ported source provenance audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

