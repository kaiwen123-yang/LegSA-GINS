#!/usr/bin/env python3
"""Run the N4H4C read-only update formula audit.

中文说明：脚本只读取 reference/final_v23_repo 和 /home/kaiwen/KF-GINS，
默认输出到 /tmp，不修改外部仓库。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from legsa_gins.source_audit.legsa_v23_update_formula_audit import write_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="/tmp/legsa_v23_update_formula_audit.json",
        help="Output JSON path; default stays outside the repository.",
    )
    args = parser.parse_args()
    path = write_report(Path(args.output))
    print(f"wrote read-only update formula audit: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
