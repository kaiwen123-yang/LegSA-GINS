#!/usr/bin/env python3
"""Audit N4H2D replay reference mapping/stale summary tooling.

中文说明：只使用 toy official/replay artifacts；不读取真实 raw data，不修改 solver，
不写入外部 KF-GINS。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/replay_reference_mapping_audit.py",
    "src/legsa_gins/evaluation/fresh_replay_evaluator.py",
    "src/legsa_gins/evaluation/official_reference_reconstruction.py",
    "src/legsa_gins/evaluation/summary_staleness_audit.py",
    "scripts/experiments/run_replay_reference_mapping_audit.py",
    "docs/experiments/replay_reference_mapping_audit.md",
    "docs/experiments/fresh_replay_evaluation_against_dual_reference.md",
    "docs/experiments/summary_staleness_audit.md",
    "docs/experiments/n4h2d_replay_reference_mapping_decision.md",
    "docs/codex_prompts/N4H2D_replay_reference_mapping_audit.md",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_toy(tmp: Path) -> tuple[Path, Path]:
    dual = tmp / "dual"
    n4h2 = tmp / "n4h2"
    _write(dual / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n")
    _write(
        dual / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n0,0,0,0,0,0,2\n1,0,0,0,0,0,2\n",
    )
    _write(
        dual / "summary.json",
        json.dumps({"position": {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0}, "attitude": {"roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0, "yaw_rmse_deg": 2.0}}),
    )
    _write(n4h2 / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n")
    _write(n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json", json.dumps({"yaw_rmse_deg": 93.0, "horizontal_rmse_m": 0.0, "up_rmse_m": 0.0, "count": 2}))
    _write(n4h2 / "replay" / "N4H2_REPLAY_REPORT.json", json.dumps({"reference_role": "trace_evaluation_only"}))
    return dual, n4h2


def _assert_boundary(report: dict, name: str) -> None:
    for key in ["trace_solver_input", "output_only_correction", "solver_output_changed", "numerical_performance_claim"]:
        if report.get(key) is not False:
            raise AssertionError(f"{name} {key} must be false")


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")
    with tempfile.TemporaryDirectory(prefix="legsa_n4h2d_audit_") as tmp_name:
        tmp = Path(tmp_name)
        dual, n4h2 = _make_toy(tmp)
        out = tmp / "out"
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/experiments/run_replay_reference_mapping_audit.py"),
                "--dual-root",
                str(dual),
                "--n4h2-artifacts-root",
                str(n4h2),
                "--output-dir",
                str(out),
            ],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        decision = json.loads((out / "N4H2D_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision["official_reference_reconstruction"]["actual_dual_summary_reproduced"] is not True:
            raise AssertionError("toy official summary should reproduce")
        if decision["fresh_replay_summary"]["yaw_rmse_deg"] != 2.0:
            raise AssertionError("toy fresh replay yaw should be 2 deg")
        if decision["old_summary_invalidated"] is not True:
            raise AssertionError("old yaw 93 should be invalidated")
        _assert_boundary(decision, "decision")
        for name in [
            "OFFICIAL_REFERENCE_RECONSTRUCTION_REPORT.json",
            "FRESH_REPLAY_EVALUATION_REPORT.json",
            "OLD_VS_FRESH_REPLAY_SUMMARY_REPORT.json",
            "SUMMARY_STALENESS_AUDIT_REPORT.json",
        ]:
            report = json.loads((out / name).read_text(encoding="utf-8"))
            _assert_boundary(report, name)

    docs = [
        root / "docs/experiments/replay_reference_mapping_audit.md",
        root / "docs/experiments/fresh_replay_evaluation_against_dual_reference.md",
        root / "docs/experiments/summary_staleness_audit.md",
        root / "docs/experiments/n4h2d_replay_reference_mapping_decision.md",
        root / "docs/codex_prompts/N4H2D_replay_reference_mapping_audit.md",
    ]
    forbidden = [
        str(Path("/home") / "kaiwen") + "/",
        str(Path("/mnt") / "c" / "Users") + "/",
        "C:" + "\\Users",
    ]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    try:
        audit(REPO_ROOT)
    except AssertionError as exc:
        print(f"N4H2D replay reference mapping audit failed: {exc}")
        return 1
    print("N4H2D replay reference mapping audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
