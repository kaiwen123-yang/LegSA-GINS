#!/usr/bin/env python3
"""Audit N4H4D2 formula parity and diagnostic variant plumbing.

中文说明：audit 使用 /tmp toy 输入验证公式报告、diagnostic model variants 和 forbidden flags；
不提交 runtime artifacts，不读取 trace/final_v23 output 作为 solver input。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOY_ROOT = Path("/tmp/legsa_n4h4d2_audit_toy_clean")
TOY_DUAL = Path("/tmp/legsa_n4h4d2_audit_toy_dual")
TOY_D1 = Path("/tmp/legsa_n4h4d2_audit_d1")
TOY_OUT = Path("/tmp/legsa_n4h4d2_audit_output")

REQUIRED_FILES = [
    "src/legsa_gins/evaluation/legsa_v23_formula_parity_audit.py",
    "src/legsa_gins/evaluation/legsa_v23_mechanization_sanity.py",
    "src/legsa_gins/evaluation/legsa_v23_update_feedback_variant_matrix.py",
    "src/legsa_gins/evaluation/legsa_v23_variant_decision.py",
    "scripts/experiments/run_legsa_v23_formula_variant_audit.py",
    "docs/experiments/n4h4d2_formula_parity_audit.md",
    "docs/experiments/n4h4d2_mechanization_sanity.md",
    "docs/experiments/n4h4d2_update_feedback_variant_matrix.md",
    "docs/experiments/n4h4d2_decision.md",
    "docs/codex_prompts/N4H4D2_formula_variant_audit.md",
]

FORBIDDEN_STRINGS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
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
    print(f"N4H4D2 audit failed: {message}")
    for item in details or []:
        print(f"- {item}")
    return 1


def _write_toy_inputs() -> None:
    for path in [TOY_ROOT, TOY_DUAL, TOY_D1, TOY_OUT]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    (TOY_ROOT / "CLEAN_STATUS_YAW.imu").write_text(
        "\n".join(f"{i * 0.01:.2f} 0 0 0 0 0 -0.0980665" for i in range(41)) + "\n",
        encoding="utf-8",
    )
    (TOY_ROOT / "CLEAN_STATUS_YAW.gnss").write_text(
        "\n".join(
            f"{i * 0.05:.2f} 31.0 121.0 10.0 1 1 1 0 0 0 0.1 0.1 0.1 {10 + i * 10:.1f} 1.5"
            for i in range(1, 7)
        )
        + "\n",
        encoding="utf-8",
    )
    (TOY_ROOT / "kf-gins-n4h2g-clean-replay.yaml").write_text(
        "\n".join(
            [
                "starttime: 0.0",
                "endtime: 0.40",
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
        "\n".join(f"0 {i * 0.01:.2f} 31.0 121.0 10.0 0 0 0 0 0 10.0" for i in range(1, 41)) + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "error_series.csv").write_text(
        "timestamp,north_error_m,east_error_m,up_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        + "\n".join(f"{i * 0.01:.2f},0,0,0,0,0,0" for i in range(1, 41))
        + "\n",
        encoding="utf-8",
    )
    (TOY_DUAL / "summary.json").write_text(
        json.dumps(
            {
                "horizontal_rmse_m": 0,
                "up_rmse_m": 0,
                "yaw_rmse_deg": 0,
                "roll_rmse_deg": 0,
                "pitch_rmse_deg": 0,
                "count": 40,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _check_required_files() -> int:
    missing = [path for path in REQUIRED_FILES if not (REPO_ROOT / path).is_file()]
    if missing:
        return _fail("missing required files", missing)
    demo = (REPO_ROOT / "cpp/legsa_v23_core/src/legsa_v23_core_demo.cpp").read_text(encoding="utf-8")
    for token in ["--diagnostic-model-variant", "baseline_current"]:
        if token not in demo:
            return _fail("C++ diagnostic variant flag missing", [token])
    manifest = (REPO_ROOT / "cpp/legsa_v23_core/src/writers/run_manifest_writer.cpp").read_text(encoding="utf-8")
    for token in ["diagnostic_model_variant", "solver_output_changed_by_diagnostic_variant", "diagnostic_only"]:
        if token not in manifest:
            return _fail("RUN_MANIFEST diagnostic variant field missing", [token])
    return 0


def _check_toy_run() -> int:
    _write_toy_inputs()
    for command in [["cmake", "-S", "cpp", "-B", "build/cpp"], ["cmake", "--build", "build/cpp"]]:
        completed = _run(command)
        if completed.returncode != 0:
            return _fail("CMake failed", [completed.stdout, completed.stderr])
    d1 = _run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_first_epoch_diagnostics.py",
            "--clean-root",
            str(TOY_ROOT),
            "--dual-root",
            str(TOY_DUAL),
            "--output-dir",
            str(TOY_D1),
            "--exe",
            "./build/cpp/legsa_v23_core_demo",
            "--allow-run",
            "--run-isolation-matrix",
        ]
    )
    if d1.returncode != 0:
        return _fail("toy D1 diagnostics prerequisite failed", [d1.stdout, d1.stderr])
    d2 = _run(
        [
            sys.executable,
            "scripts/experiments/run_legsa_v23_formula_variant_audit.py",
            "--clean-root",
            str(TOY_ROOT),
            "--dual-root",
            str(TOY_DUAL),
            "--d1-root",
            str(TOY_D1),
            "--external-source-root",
            str(REPO_ROOT / "cpp"),
            "--reference-root",
            "reference/final_v23_repo",
            "--output-dir",
            str(TOY_OUT),
            "--exe",
            "./build/cpp/legsa_v23_core_demo",
            "--allow-run",
            "--run-variant-matrix",
        ]
    )
    if d2.returncode != 0:
        return _fail("toy D2 formula variant runner failed", [d2.stdout, d2.stderr])
    required_outputs = [
        "FORMULA_PARITY_AUDIT_REPORT.json",
        "MECHANIZATION_SANITY_REPORT.json",
        "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json",
        "N4H4D2_DECISION_REPORT.json",
        "variants/baseline_current/RUN_MANIFEST.json",
        "variants/position_H_phi_sign_flip/RUN_MANIFEST.json",
    ]
    missing = [name for name in required_outputs if not (TOY_OUT / name).exists()]
    if missing:
        return _fail("toy D2 outputs missing", missing)
    for report_name in [
        "FORMULA_PARITY_AUDIT_REPORT.json",
        "MECHANIZATION_SANITY_REPORT.json",
        "UPDATE_FEEDBACK_VARIANT_MATRIX_REPORT.json",
        "N4H4D2_DECISION_REPORT.json",
    ]:
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
        if report.get("diagnostic_only") is not True:
            return _fail("diagnostic_only missing", [report_name])
    manifest = json.loads((TOY_OUT / "variants/position_H_phi_sign_flip/RUN_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("diagnostic_model_variant") != "position_H_phi_sign_flip":
        return _fail("variant manifest did not record diagnostic_model_variant")
    if manifest.get("solver_output_changed_by_diagnostic_variant") is not True:
        return _fail("variant manifest did not flag solver output change")
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
    print("N4H4D2 formula variant audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
