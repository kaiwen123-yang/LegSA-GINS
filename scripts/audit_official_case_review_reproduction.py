#!/usr/bin/env python3
"""Audit N4R official case-review reproduction scope and toy behavior.

中文说明：本 audit 使用 toy artifacts 验证 evaluator parity，不读取真实 raw data，
不把 trace/reference 用作 solver input。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/official_case_review_reproduction.py",
    "src/legsa_gins/evaluation/yaw_evaluator_parity.py",
    "src/legsa_gins/evaluation/error_series_parity.py",
    "src/legsa_gins/evaluation/yaw_convention_transforms.py",
    "src/legsa_gins/evaluation/replay_official_yaw_parity.py",
    "scripts/experiments/run_official_final_v23_case_review_reproduction.py",
    "docs/experiments/official_final_v23_case_review_reproduction.md",
    "docs/experiments/yaw_evaluator_parity.md",
    "docs/experiments/error_series_parity.md",
    "docs/experiments/n4r_yaw_evaluator_decision.md",
    "docs/codex_prompts/N4R_official_case_review_reproduction.md",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_toy(root: Path) -> tuple[Path, Path, Path]:
    source = root / "external" / "runs" / "nominal_none"
    n4h2 = root / "n4h2"
    out = root / "out"
    nav_lines = [
        "0 0 40.0 116.0 10.0 0 0 0 0 0 0\n",
        "0 1 40.0 116.0 10.0 0 0 0 0 0 0\n",
        "0 2 40.0 116.0 10.0 0 0 0 0 0 0\n",
    ]
    _write(source / "KF_GINS_Navresult.nav", "".join(nav_lines))
    _write(source / "KF_GINS_STD.txt", "".join(nav_lines))
    _write(source / "input.gnss", "0 40 116 10 0 0 0 1 1 1 0 1 1 1 1\n")
    _write(
        source / "summary.json",
        json.dumps(
            {
                "position": {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0},
                "attitude": {"roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0, "yaw_rmse_deg": 0.0},
                "meta": {"num_samples": 3},
            }
        )
        + "\n",
    )
    _write(
        source / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        "0,0,0,0,0,0,0\n1,0,0,0,0,0,0\n2,0,0,0,0,0,0\n",
    )
    _write(
        n4h2 / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        "0,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "1,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "2,40,116,10,0,0,0,0,0,0,baseline,baseline\n",
    )
    _write(
        n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "0,0,0,0,0,0,0,0,0,-90\n"
        "1,1,0,0,0,0,0,0,0,-90\n"
        "2,2,0,0,0,0,0,0,0,-90\n",
    )
    return source.parent.parent, n4h2, out


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")

    with tempfile.TemporaryDirectory(prefix="legsa_n4r_audit_") as tmp_name:
        external, n4h2, out = _make_toy(Path(tmp_name))
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/experiments/run_official_final_v23_case_review_reproduction.py"),
                "--external-source-root",
                str(external),
                "--n4h2-artifacts-root",
                str(n4h2),
                "--output-dir",
                str(out),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        decision = json.loads((out / "N4R_DECISION_REPORT.json").read_text(encoding="utf-8"))
        official = json.loads((out / "OFFICIAL_CASE_REPRODUCTION_REPORT.json").read_text(encoding="utf-8"))
        direct_yaw = official["direct_recompute_summary"]["yaw_rmse_deg"]
        best_yaw = official["best_transform_summary"]["yaw_rmse_deg"]
        if direct_yaw < 80.0:
            raise AssertionError("toy direct evaluator did not mismatch")
        if best_yaw > 0.1:
            raise AssertionError("toy transform candidate did not match official")
        if "evaluator_convention" not in decision["recommended_next_stage"]:
            raise AssertionError("toy decision did not recommend evaluator convention path")
        for report_name in [
            "OFFICIAL_CASE_REPRODUCTION_REPORT.json",
            "REPLAY_OFFICIAL_YAW_PARITY_REPORT.json",
            "N4R_DECISION_REPORT.json",
        ]:
            report = json.loads((out / report_name).read_text(encoding="utf-8"))
            if report.get("trace_solver_input") is not False:
                raise AssertionError(f"{report_name} trace_solver_input is not false")
            if report.get("output_only_correction") is not False:
                raise AssertionError(f"{report_name} output_only_correction is not false")
            if report.get("numerical_performance_claim") is not False:
                raise AssertionError(f"{report_name} numerical_performance_claim is not false")

    tracked_docs = [
        root / "docs/experiments/official_final_v23_case_review_reproduction.md",
        root / "docs/experiments/yaw_evaluator_parity.md",
        root / "docs/experiments/error_series_parity.md",
        root / "docs/experiments/n4r_yaw_evaluator_decision.md",
        root / "docs/codex_prompts/N4R_official_case_review_reproduction.md",
    ]
    forbidden = [
        "/home/kaiwen/",
        "/mnt/c/Users/",
        "C:" + "\\Users",
    ]
    for doc in tracked_docs:
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        audit(root)
    except AssertionError as exc:
        print(f"N4R official case-review reproduction audit failed: {exc}")
        return 1
    print("N4R official case-review reproduction audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
