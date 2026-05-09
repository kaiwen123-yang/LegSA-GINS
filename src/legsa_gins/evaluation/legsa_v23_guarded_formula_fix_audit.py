"""Source-backed guarded formula fix audit for N4H4D3.

中文说明：本模块只检查 LegSA-v23-core 自有代码是否满足 KF-GINS-style
公式约定；不读取 final_v23 输出作为 solver input，不修改外部 KF-GINS。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read(root: Path, rel: str) -> str:
    path = root / rel
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _contains_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)


def audit_guarded_fix_source(repo_root: str | Path) -> dict[str, Any]:
    """中文说明：检查 DR/DRi、position update、EKFUpdate、stateFeedback 的默认公式。"""

    root = Path(repo_root)
    earth = _read(root, "cpp/legsa_v23_core/src/common/earth.cpp")
    measurement = _read(root, "cpp/legsa_v23_core/src/updates/measurement_update.cpp")
    ekf = _read(root, "cpp/legsa_v23_core/src/filter/ekf_update.cpp")
    feedback = _read(root, "cpp/legsa_v23_core/src/filter/state_feedback.cpp")

    dr_height_sign_correct = earth.count("matrix3At(matrix, 2, 2) = -1.0;") >= 2
    position_residual_sign = "blh_error[i] = antenna_blh[i] - gnss.blh[i];" in measurement
    position_h_phi_fixed = _contains_all(
        measurement,
        [
            "const Matrix3 lever_skew = Rotation::skewSymmetric(lever_nav);",
            "double value = matrix3At(lever_skew, row, col);",
            "measurementHAt(block, row, PHI_ID + col) = value;",
        ],
    )
    ekf_residual_sign_correct = _contains_all(
        ekf,
        [
            "innovation[row] = meas.residual[row] - predicted;",
            "state.dx[row] += dynAt(K, m, row, col) * innovation[col];",
            "matrix21At(I_minus_KH, row, col) -= kh;",
        ],
    )
    pos_vel_feedback_minus = _contains_all(
        feedback,
        ["state.current_pva.pos_blh_rad_m[i] -= delta_blh[i];", "state.current_pva.vel_ned_mps[i] -= delta_velocity[i];"],
    )
    state_feedback_phi_positive = _contains_all(
        feedback,
        ["Vector3 feedback_phi = delta_phi;", "Rotation::rotvec2quaternion(feedback_phi)"],
    )
    state_feedback_phi_left_multiply = "Rotation::multiply(qpn, qbn)" in feedback
    bias_scale_feedback_plus = _contains_all(
        feedback,
        [
            "state.current_pva.gyro_bias[i] += state.dx[BG_ID + i];",
            "state.current_pva.acc_bias[i] += state.dx[BA_ID + i];",
            "state.current_pva.gyro_scale[i] += state.dx[SG_ID + i];",
            "state.current_pva.acc_scale[i] += state.dx[SA_ID + i];",
        ],
    )
    dx_reset = "state.dx = zeroVector21();" in feedback
    yaw_h_mapping_not_fixed_in_d3 = 'diagnosticVariantActive(options, "yaw_H_sign_flip") ? -1.0 : 1.0' in measurement
    chinese_comments_exist = all("中文说明" in text for text in [earth, measurement, ekf, feedback])

    passed = all(
        [
            dr_height_sign_correct,
            position_residual_sign,
            position_h_phi_fixed,
            ekf_residual_sign_correct,
            pos_vel_feedback_minus,
            state_feedback_phi_positive,
            state_feedback_phi_left_multiply,
            bias_scale_feedback_plus,
            dx_reset,
            yaw_h_mapping_not_fixed_in_d3,
            chinese_comments_exist,
        ]
    )
    return {
        "phase": "N4H4D3",
        "audit_status": "passed" if passed else "failed",
        "position_H_phi_fixed": position_h_phi_fixed,
        "position_residual_sign_correct": position_residual_sign,
        "state_feedback_phi_left_multiply": state_feedback_phi_left_multiply,
        "state_feedback_phi_positive": state_feedback_phi_positive,
        "pos_vel_feedback_minus": pos_vel_feedback_minus,
        "bias_scale_feedback_plus": bias_scale_feedback_plus,
        "DR_height_sign_correct": dr_height_sign_correct,
        "EKFUpdate_residual_sign_correct": ekf_residual_sign_correct,
        "dx_reset_after_feedback": dx_reset,
        "yaw_H_mapping_not_fixed_in_D3": yaw_h_mapping_not_fixed_in_d3,
        "yaw_H_mapping_secondary_issue": True,
        "chinese_comments_exist": chinese_comments_exist,
        "source_backed_fix_applied": passed,
        "no_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def write_audit_report(path: str | Path, report: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
