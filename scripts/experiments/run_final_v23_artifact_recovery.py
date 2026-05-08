#!/usr/bin/env python3
"""Run final_v23 artifact recovery to a runtime output directory.

中文说明：只写 runtime JSON；不提交 artifact，不复制外部源码，不写 tracked local path。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.source_audit.final_v23_artifact_recovery import recover_final_v23_artifacts  # noqa: E402


def _default_roots() -> dict[str, Path]:
    return {
        "EXTERNAL_KFGINS_ROOT": Path.home() / "KF-GINS",
        "HOME_ROOT": Path.home(),
        "MNT_C_USERS_YKW": Path("/mnt") / "c" / "Users" / "ykw",
        "MNT_C_USERS_86187": Path("/mnt") / "c" / "Users" / "86187",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-depth", type=int, default=6)
    args = parser.parse_args()
    report = recover_final_v23_artifacts(_default_roots(), max_depth=args.max_depth)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "FINAL_V23_ARTIFACT_RECOVERY_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"artifact_groups_found": report["artifact_groups_found"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
