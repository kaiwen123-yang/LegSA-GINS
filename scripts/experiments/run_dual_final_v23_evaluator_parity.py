#!/usr/bin/env python3
"""Run N4R2 dual_final_v23 evaluator parity.

中文说明：只做 evaluator convention 验证，不修改 solver，不复制外部 artifacts。
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

from legsa_gins.evaluation.dual_final_v23_evaluator_parity import evaluate_dual_final_v23_evaluator_parity  # noqa: E402
from legsa_gins.source_audit.dual_final_v23_artifact_recovery import recover_dual_final_v23_artifacts  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    roots = {
        "EXTERNAL_KFGINS_ROOT": Path(args.external_source_root),
        "HOME_ROOT": Path.home(),
        "WINDOWS_YKW_ROOT": Path("/mnt") / "c" / "Users" / "ykw",
        "WINDOWS_86187_ROOT": Path("/mnt") / "c" / "Users" / "86187",
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    recovery = recover_dual_final_v23_artifacts(roots)
    _write_json(out / "DUAL_FINAL_V23_ARTIFACT_RECOVERY_REPORT.json", recovery)
    parity = evaluate_dual_final_v23_evaluator_parity(
        recovery.get("best_dual_candidate_group") if recovery.get("dual_artifact_found") else None,
        external_source_root=args.external_source_root,
        n4h2_artifacts_root=args.n4h2_artifacts_root,
        output_dir=out,
    )
    return parity


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    print(json.dumps({"evidence_status": report["evidence_status"], "dual_evaluator_profile_confirmed": report["dual_evaluator_profile_confirmed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
