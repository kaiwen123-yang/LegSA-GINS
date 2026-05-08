#!/usr/bin/env python3
"""Run N4R2 N4H2 replay profile re-evaluation.

中文说明：只重算 evaluator 指标，不修改 replay/solver 输出。
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

from legsa_gins.evaluation.n4h2_replay_profile_revaluation import reevaluate_n4h2_replay_profiles  # noqa: E402


def _load_confirmed_profile(path_text: str | None) -> dict | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report.get("evaluator_profile_confirmed"):
        return None
    profile = report.get("confirmed_profile")
    return profile if isinstance(profile, dict) else None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--confirmed-profile-report", default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = reevaluate_n4h2_replay_profiles(
        args.n4h2_artifacts_root,
        output_dir=args.output_dir,
        confirmed_dual_profile=_load_confirmed_profile(args.confirmed_profile_report),
    )
    print(json.dumps({"evidence_status": report["evidence_status"], "recommended_profile_status": report["recommended_profile_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
