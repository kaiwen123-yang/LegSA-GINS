#!/usr/bin/env python3
"""Audit N4H4D3 guarded formula fix plumbing.

中文说明：audit 使用 /tmp toy 输入验证 source-backed formulas、toy replay 和 forbidden flags；
不提交 runtime artifacts，不读取 trace/final_v23 output 作为 solver input。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOY_ROOT = Path("/tmp/legsa_n4h4d3_audit_toy_clean")
TOY_DUAL = Path("/tmp/legsa_n4h4d3_audit_toy_dual")
TOY_D2 = Path("/tmp/legsa_n4h4d3_audit_toy_d2")
TOY_OUT = Path("/tmp/legsa_n4h4d3_audit_output")

REQUIRED_FILES = [
    "src/legsa_gins/evaluation/legsa_v23_guarded_formula_fix_audit.py",
    "src/legsa_gins/evaluation/legsa_v23_guarded_fix_replay.py",
    "src/legsa_gins/evaluation/legsa_v23_guarded_fix_decision.py",
    "scripts/experiments/run_legsa_v23_guarded_formula_fix.py",
    "docs/experiments/n4h4d3_guarded_formula_fix.md",
    "docs/experiments/n4h4d3_source_backed_formula_changes.md",
    "docs/experiments/n4h4d3_guarded_fix_replay.md",
    "docs/experiments/n4h4d3_decision.md",
    "docs/codex_prompts/N4H4D3_guarded_formula_fix.md",
]

FORBIDDEN_STRINGS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    str(Path.home() / "legsa_n4h4d3_guarded_formula_fix"),
    str(Path.home() / "legsa_n4h4d2_formula_variants"),
    str(Path.home() / "legsa_n4h4d1_diagnostics"),
    str(Path.home() / "legsa_n4h4d_clean_parity"),
    str(Path.home() / "legsa_n4h2g_clean_replay"),
    str(Path.home() / "legsa_external_artifacts"),
]

ARTIFACT_PATTERNS = (
    "input.gnss",
    ".imu",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "summary.json",
    "error_series.csv",
    ".png",
    ".pdf",
    ".svg",
)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"N4H4D3 audit failed: {message}")
    for item in details or []:
        print(f"- {item}")
    return 1


def _write_toy_inputs() -> None:
    for path in [TOY_ROOT, TOY_DUAL, TOY_D2, TOY_OUT]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    (TOY_ROOT / "CLEAN_STATUS_YAW.imu").write_text(
        "\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 -0.0980665" for i in range(21)) + "\n",
        encoding="utf-8",
    )
    (TOY_ROOT / "CLEAN_STATUS_YAW.gnss").write_text(
        "\n".join(
            f"{i * 0.02:.2f} 31.0 121.0 10.0 1 1 1 0 0 0 0.1 0.1 0.1 10.0 1.5"
            for i in range(1, 10)
        )
        + "\n",
        encoding="utf-8",
    )
    (TOY_ROOT / "kf-gins-n4h2g-clean-replay.yaml").write_text(
        "\n".join(
            [
                "starttime: 0.0",
                "endtime: 0.20",
                "imudatalen: 7",
                "imudatarate: 100",
                "initpos: [31.0, 121.0, 10.0]",
                "initvel: [0.0, 0.0, 0.0]",
                "initatt: [0.0, 0.0, 10.0]",
                "initposstd: [1.0, 1.0, 1.0]",
                "initvelstd: [0.1, 0.1, 0.1]",
                "initattstd: [1.0, 1.0, 1.0]",
                "antlever: [0.0, 0.0, 0.0]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "KF_GINS_Navresult.nav").write_text(
        "\n".join(f"0 {i * 0.01:.2f} 31.0 121.0 10.0 0 0 0 0 0 10.0" for i in range(1, 21)) + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "error_series.csv").write_text(
        "timestamp,north_error_m,east_error_m,up_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        + "\n".join(f"{i * 0.01:.2f},0,0,0,0,0,0" for i in range(1, 21))
        + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "summary.json").write_text(
        json.dumps({"horizontal_rmse_m": 0, "up_rmse_m": 0, "yaw_rmse_deg": 0, "roll_rmse_deg": 0, "pitch_rmse_deg": 0, "count": 20})
        + "\n",
        encoding="utf-8",
    )
    (TOY_D2 / "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json").write_text(
        json.dumps(
            {
                "variant_summaries": {
                    "baseline_current": {"summary": {"horizontal_rmse_m": 10, "up_rmse_m": 10, "yaw_rmse_deg": 10, "roll_rmse_deg": 10, "pitch_rmse_deg": 10}},
                    "state_feedback_phi_negative": {"summary": {"horizontal_rmse_m": 5, "up_rmse_m": 5, "yaw_rmse_deg": 9, "roll_rmse_deg": 9, "pitch_rmse_deg": 9}},
                },
                "best_candidate_variant": "state_feedback_phi_negative",
                "candidate_fix_detected": False,
                "multi_issue_or_coupled_issue": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (TOY_D2 / "N4H4D2_DECISION_REPORT.json").write_text(
        json.dumps({"multi_issue_or_coupled_issue": True, "most_likely_issue": "position_H_phi_or_feedback_issue"}) + "\n",
        encoding="utf-8",
    )


def _check_required_files() -> int:
    missing = [path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()]
    if missing:
        return _fail("missing required files", missing)
    source = _run(
        [
            sys.executable,
            "-c",
            "import sys,json; sys.path.insert(0,'src'); from legsa_gins.evaluation.legsa_v23_guarded_formula_fix_audit import audit_guarded_fix_source; print(json.dumps(audit_guarded_fix_source('.')))",
        ]
    )
    if source.returncode != 0:
        return _fail("source audit import failed", [source.stdout, source.stderr])
    report = json.loads(source.stdout)
    if report.get("audit_status") != "passed" or report.get("source_backed_fix_applied") is not True:
        return _fail("source audit did not pass", [json.dumps(report, indent=2, sort_keys=True)])
    return 0


def _check_toy_run() -> int:
    _write_toy_inputs()
    completed = _run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_guarded_formula_fix.py",
            "--clean-root",
            str(TOY_ROOT),
            "--dual-root",
            str(TOY_DUAL),
            "--d2-root",
            str(TOY_D2),
            "--output-dir",
            str(TOY_OUT),
            "--exe",
            "./build/cpp/legsa_v23_core_demo",
            "--allow-run",
        ]
    )
    if completed.returncode != 0:
        return _fail("toy guarded formula runner failed", [completed.stdout, completed.stderr])
    required_outputs = [
        "GUARDED_FORMULA_FIX_AUDIT_REPORT.json",
        "GUARDED_FIX_CLEAN_REPLAY_SUMMARY.json",
        "GUARDED_FIX_CLEAN_REPLAY_GAP_SCREEN.json",
        "GUARDED_FIX_COMPARISON_REPORT.json",
        "N4H4D3_DECISION_REPORT.json",
    ]
    missing = [name for name in required_outputs if not (TOY_OUT / name).exists()]
    if missing:
        return _fail("toy guarded fix outputs missing", missing)
    for report_name in required_outputs:
        report = json.loads((TOY_OUT / report_name).read_text(encoding="utf-8"))
        for key in [
            "trace_solver_input",
            "final_v23_output_substitution",
            "output_only_correction",
            "bad_epoch_deletion_for_metric",
            "numerical_performance_claim",
        ]:
            if report.get(key) is not False:
                return _fail("forbidden report flag is not false", [report_name, key])
    audit = json.loads((TOY_OUT / "GUARDED_FORMULA_FIX_AUDIT_REPORT.json").read_text(encoding="utf-8"))
    if audit.get("source_backed_fix_applied") is not True:
        return _fail("source_backed_fix_applied missing")
    return 0


def _check_no_path_leaks_or_artifacts() -> int:
    for needle in FORBIDDEN_STRINGS:
        result = _run(["git", "grep", "-n", needle, "--", "."])
        if result.returncode == 0:
            return _fail("tracked local path leak detected", [needle, result.stdout])
    files = _run(["git", "ls-files"])
    if files.returncode != 0:
        return _fail("git ls-files failed", [files.stderr])
    hits = [line for line in files.stdout.splitlines() if line.endswith(ARTIFACT_PATTERNS)]
    if hits:
        return _fail("tracked runtime/raw artifact detected", hits)
    return 0


def main() -> int:
    for check in [_check_required_files, _check_toy_run, _check_no_path_leaks_or_artifacts]:
        result = check()
        if result:
            return result
    print("N4H4D3 guarded formula fix audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
