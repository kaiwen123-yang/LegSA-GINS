#!/usr/bin/env python3
"""Run N4R2 dual_final_v23 artifact recovery.

中文说明：该脚本只读搜索 runtime artifact，不复制外部源码，不提交 raw data。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.source_audit.dual_final_v23_artifact_recovery import recover_dual_final_v23_artifacts  # noqa: E402


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--home-root", default=str(Path.home()))
    parser.add_argument("--windows-ykw-root", default=str(Path("/mnt") / "c" / "Users" / "ykw"))
    parser.add_argument("--windows-86187-root", default=str(Path("/mnt") / "c" / "Users" / "86187"))
    parser.add_argument("--max-depth", type=int, default=9)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict:
    roots = {
        "EXTERNAL_KFGINS_ROOT": Path(args.external_source_root),
        "HOME_ROOT": Path(args.home_root),
        "WINDOWS_YKW_ROOT": Path(args.windows_ykw_root),
        "WINDOWS_86187_ROOT": Path(args.windows_86187_root),
    }
    report = recover_dual_final_v23_artifacts(roots, max_depth=args.max_depth)
    _write_json(Path(args.output_dir) / "DUAL_FINAL_V23_ARTIFACT_RECOVERY_REPORT.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    print(json.dumps({"evidence_status": report["evidence_status"], "dual_artifact_found": report["dual_artifact_found"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
