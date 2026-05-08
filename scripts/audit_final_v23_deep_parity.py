#!/usr/bin/env python3
"""Audit N4H2C deep final_v23 parity tooling and boundary docs.

中文说明：本脚本只用 toy data 验证新增 deep parity 模块；不读取真实 BY2 路径，
不复制外部源码，不运行 proposed solver，也不做 formal performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REQUIRED_FILES = [
    "src/legsa_gins/source_audit/__init__.py",
    "src/legsa_gins/source_audit/final_v23_artifact_recovery.py",
    "src/legsa_gins/source_audit/final_v23_deep_source_audit.py",
    "src/legsa_gins/source_audit/process_data_runtime_audit.py",
    "src/legsa_gins/source_audit/yaw_update_runtime_audit.py",
    "src/legsa_gins/evaluation/final_v23_input_diff.py",
    "src/legsa_gins/evaluation/kfgins_framework_parity.py",
    "src/legsa_gins/evaluation/replay_yaw_diagnostics.py",
    "src/legsa_gins/evaluation/yaw_input_variant_matrix.py",
    "scripts/experiments/run_final_v23_artifact_recovery.py",
    "scripts/experiments/run_final_v23_deep_parity_audit.py",
    "scripts/experiments/run_yaw_input_variant_matrix.py",
    "scripts/audit_final_v23_deep_parity.py",
    "docs/source_audit/final_v23_artifact_recovery.md",
    "docs/source_audit/final_v23_deep_source_map.md",
    "docs/source_audit/process_data_deep_audit.md",
    "docs/source_audit/process_data_runtime_parameter_audit.md",
    "docs/experiments/final_v23_actual_input_diff.md",
    "docs/experiments/n4h2c_yaw_config_parity_decision.md",
    "docs/experiments/kfgins_framework_parity_matrix.md",
    "docs/experiments/replay_yaw_diagnostics.md",
    "docs/experiments/yaw_input_variant_matrix.md",
    "docs/experiments/yaw_update_runtime_audit.md",
    "docs/codex_prompts/N4H2C_deep_final_v23_parity_audit.md",
    "tests/unit/test_final_v23_artifact_recovery.py",
    "tests/unit/test_final_v23_input_diff.py",
    "tests/unit/test_kfgins_framework_parity.py",
    "tests/unit/test_process_data_runtime_audit.py",
    "tests/unit/test_replay_yaw_diagnostics.py",
    "tests/unit/test_yaw_input_variant_matrix.py",
    "tests/unit/test_yaw_update_runtime_audit.py",
    "tests/integration/test_final_v23_deep_parity_toy.py",
    "tests/audit/test_final_v23_deep_parity.py",
]

REQUIRED_OUTPUTS = [
    "FINAL_V23_CASE_ROOT_PROBE.json",
    "FINAL_V23_ARTIFACT_RECOVERY_REPORT.json",
    "FINAL_V23_INPUT_DIFF_REPORT.json",
    "PROCESS_DATA_RUNTIME_PARAMETER_REPORT.json",
    "PROCESS_DATA_DEEP_AUDIT.json",
    "FINAL_V23_ENGINE_SOURCE_AUDIT.json",
    "YAW_INPUT_VARIANT_MATRIX_REPORT.json",
    "YAW_UPDATE_RUNTIME_AUDIT.json",
    "REPLAY_YAW_DIAGNOSTICS_REPORT.json",
    "KFGINS_CORE_FLOW_AUDIT.json",
    "LEGSA_KFGINS_FRAMEWORK_PARITY_MATRIX.json",
    "N4H2C_DECISION_REPORT.json",
    "n4h2c_yaw_config_parity_case_review.md",
]

FORBIDDEN_PATH_SNIPPETS = [
    "/mnt/c/Users",
    "C:" + "\\Users",
    "/home/kaiwen/" + "legsa_n4h2_artifacts",
]


def _write_gnss(path: Path, yaw_offset: float) -> None:
    lines = []
    for index in range(20):
        time = float(index)
        yaw = 10.0 + yaw_offset
        values = [
            time,
            30.0 + index * 1.0e-7,
            120.0 + index * 1.0e-7,
            5.0 + index * 0.01,
            0.02,
            0.02,
            0.03,
            0.1,
            0.2,
            -0.1,
            0.05,
            0.05,
            0.05,
            yaw,
            1.5,
        ]
        lines.append(" ".join(str(value) for value in values))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_toy_source(root: Path) -> None:
    (root / "bin").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "bin" / "process_data.py").write_text(
        "\n".join(
            [
                "# toy process_data.py",
                "yaw_source_mode = 'status_yaw'",
                "yaw_std_mode = 'fixed_1p5'",
                "BASE_TIME = 1772784000.0",
                "USE_STATUS_YAW = True",
                "YAW_SIGN = 1",
                "YAW_INSTALL_OFFSET_DEG = 0",
                "AUTO_APPLY_BEST_INSTALL = False",
                "YAW_SOURCE_MODE = 'status'",
                "YAW_NOISE_STD_DEG = 0.0",
                "OUTAGE_DURATION_SEC = 0.0",
                "OUTLIER_RATIO_DEFAULT = 0.0",
                "OUTLIER_MODE_DEFAULT = 'none'",
                "STATUS_YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                "STATUS_FIXED_YAW_STD_DEG_DEFAULT = 1.5",
                "YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                "IMU_INSTALL_ROLL_DEG_DEFAULT = -1.0",
                "IMU_INSTALL_PITCH_DEG_DEFAULT = 0.0",
                "IMU_INSTALL_YAW_DEG_DEFAULT = 0.0",
                "IMU_GNSS_TIME_OFFSET_SEC_DEFAULT = 0.0",
                "# process_data.py --generate_both_gnss --yaw_source_mode status --outlier_mode none --yaw_noise_std_deg 0",
                "def generate_both_gnss(): pass",
                "final_status_fixed1p5 = True",
                "antlever = [0, 0, 0]",
                "initatt = [0, 0, 0]",
                "imunoise = [1, 1, 1]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "gnssfileloader.cpp").write_text(
        "\n".join(
            [
                "class GnssFileLoader {};",
                "gnssdata.blh = value;",
                "gnssdata.std = value;",
                "gnssdata.vel = value;",
                "gnssdata.vel_std = value;",
                "gnssdata.yaw = value;",
                "gnssdata.yaw_std = value;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "gi_engine.cpp").write_text(
        "\n".join(
            [
                "void addImuData() {}",
                "void addGnssData() {}",
                "void newImuProcess() { imuInterpolate(); imuCompensate(); insPropagation(); }",
                "bool isToUpdate() { return true; }",
                "void EKFPredict() {}",
                "void EKFUpdate() {}",
                "void gnssUpdate() { H_gnssvel; H_gnssyaw; /* velocity update yaw update */ }",
                "void stateFeedback() {}",
                "void INSMech::insMech() {}",
                "void velUpdate() {}",
                "void posUpdate() {}",
                "void attUpdate() {}",
                "double Phi, Qd, F_, G_;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "src" / "kf_gins.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("N4H2C deep parity audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    decision_doc = root / "docs/experiments/n4h2c_yaw_config_parity_decision.md"
    decision_text = decision_doc.read_text(encoding="utf-8")
    for needle in ["trace_solver_input=false", "final_v23_is_proposed=false", "no formal performance claim"]:
        if needle not in decision_text:
            print(f"N4H2C deep parity audit failed. Decision doc missing: {needle}")
            return 1
    for forbidden in FORBIDDEN_PATH_SNIPPETS:
        if forbidden in decision_text:
            print("N4H2C deep parity audit failed. Decision doc contains a local absolute path.")
            return 1

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4h2c_audit_"))
    try:
        case_root = tmp / "actual_case"
        artifacts_root = tmp / "artifacts"
        source_root = tmp / "external_source"
        _write_gnss(case_root / "input.gnss", yaw_offset=90.0)
        _write_gnss(artifacts_root / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss", yaw_offset=0.0)
        (case_root / "KF_GINS_Navresult.nav").write_text("toy\n", encoding="utf-8")
        (case_root / "KF_GINS_STD.txt").write_text("toy\n", encoding="utf-8")
        (case_root / "summary.json").write_text('{"yaw_rmse_deg": 1.0}\n', encoding="utf-8")
        (case_root / "error_series.csv").write_text("time,yaw\n0,0\n", encoding="utf-8")
        summary_path = artifacts_root / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text('{"yaw_rmse_deg": 93.0}\n', encoding="utf-8")
        replay_nav = artifacts_root / "replay" / "standardized" / "FINAL_V23_NAV.csv"
        replay_nav.parent.mkdir(parents=True, exist_ok=True)
        replay_nav.write_text(
            "gps_week,tow,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
            + "\n".join(f"0,{i},0,0,0,0,0,0,0,0,10,baseline,baseline" for i in range(20))
            + "\n",
            encoding="utf-8",
        )
        error_series = artifacts_root / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv"
        error_series.write_text(
            "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
            + "\n".join(f"{i},{i},0,0,0,0,0,0,0,0" for i in range(20))
            + "\n",
            encoding="utf-8",
        )
        _write_toy_source(source_root)

        out = tmp / "out"
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/experiments/run_final_v23_deep_parity_audit.py"),
                "--final-v23-case-root",
                str(case_root),
                "--n4h2-artifacts-root",
                str(artifacts_root),
                "--external-source-root",
                str(source_root),
                "--output-dir",
                str(out),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print("N4H2C deep parity audit failed. Toy runner failed.")
            print(completed.stdout)
            print(completed.stderr)
            return 1
        missing_outputs = [name for name in REQUIRED_OUTPUTS if not (out / name).exists()]
        if missing_outputs:
            print("N4H2C deep parity audit failed. Missing toy outputs:")
            for name in missing_outputs:
                print(f"- {name}")
            return 1
        input_diff = _load_json(out / "FINAL_V23_INPUT_DIFF_REPORT.json")
        if input_diff.get("input_diff_status") != "input_position_matched_but_yaw_mismatch":
            print("N4H2C deep parity audit failed. Toy input mismatch status was not detected.")
            return 1
        decision = _load_json(out / "N4H2C_DECISION_REPORT.json")
        if decision.get("recommended_next_stage") != "N4H2C_yaw_input_config_fix":
            print("N4H2C deep parity audit failed. Toy decision was not yaw input config fix.")
            return 1
        review = (out / "n4h2c_yaw_config_parity_case_review.md").read_text(encoding="utf-8")
        for needle in ["trace_solver_input=false", "final_v23_is_proposed=false", "no formal performance claim"]:
            if needle not in review:
                print(f"N4H2C deep parity audit failed. Toy review missing: {needle}")
                return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("N4H2C final_v23 deep parity audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
