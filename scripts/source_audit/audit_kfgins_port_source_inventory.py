#!/usr/bin/env python3
"""Audit N4H4R1 source inventory for controlled KF-GINS/final_v23 porting.

中文说明：本脚本生成只读 source inventory，不复制源码文件，不编译 reference。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.source_audit.kfgins_port_source_inventory import (  # noqa: E402
    collect_kfgins_port_source_inventory,
    dumps_report,
)


def main() -> int:
    report = collect_kfgins_port_source_inventory(ROOT)
    print(dumps_report(report))
    if not report["commit_matches_expected"]:
        print("KF-GINS port source inventory audit failed: commit mismatch")
        return 1
    missing = [name for name, entry in report["entries"].items() if not entry.get("found")]
    if missing:
        print("KF-GINS port source inventory audit failed: missing sources")
        for name in missing:
            print(f"- {name}")
        return 1
    if report["final_v23_output_solver_input"] or report["trace_solver_input"]:
        print("KF-GINS port source inventory audit failed: forbidden input flag set")
        return 1
    print("KF-GINS port source inventory audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

