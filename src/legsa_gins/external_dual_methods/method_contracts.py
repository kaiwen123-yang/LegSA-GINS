"""Contracts for PAPER10Q2R2 external dual-antenna methods."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReproductionType(str, Enum):
    EXACT_REPRODUCTION = "EXACT_REPRODUCTION"
    FAITHFUL_ALGORITHM_REPRODUCTION = "FAITHFUL_ALGORITHM_REPRODUCTION"
    FAITHFUL_MODULE_REPRODUCTION = "FAITHFUL_MODULE_REPRODUCTION"
    PAPER_DERIVED_POLICY_BASELINE = "PAPER_DERIVED_POLICY_BASELINE"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    BLOCKED_WITH_PROOF = "BLOCKED_WITH_PROOF"


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    method_name: str
    source_paper: str
    source_title: str
    source_year: str
    source_venue_or_journal: str
    algorithm_family: str
    target_reproduction_type: ReproductionType
    required_inputs: tuple[str, ...]
    required_backend: str
    selected_for_q2r2: bool
    notes: str


# 中文说明：这些合同只声明外部算法复现目标，不代表已经完成。
# trace 只能用于 evaluation；final_v23/LegSA 输出不能作为 solver input。
METHOD_CATALOG: tuple[MethodContract, ...] = (
    MethodContract(
        method_id="DA01_TEUNISSEN_CLAMBDA_COMPASS",
        method_name="Teunissen C-LAMBDA short-baseline GNSS compass",
        source_paper="Teunissen C-LAMBDA / GNSS compass",
        source_title="Constrained LAMBDA attitude ambiguity resolution",
        source_year="",
        source_venue_or_journal="GNSS attitude literature",
        algorithm_family="dual_antenna_short_baseline_attitude",
        target_reproduction_type=ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION,
        required_inputs=("gnss1_raw", "gnss2_raw", "corr_raw", "dual_status", "trace_eval_reference"),
        required_backend="carrier/DD/LOS ambiguity backend with baseline-length constraint",
        selected_for_q2r2=True,
        notes="Selected only if BY2 raw carrier/correction inputs and DD/LOS backend can close.",
    ),
    MethodContract(
        method_id="DA02_LIU_CONSTRAINED_WRAPPED_WLS",
        method_name="Liu constrained wrapped least-squares attitude",
        source_paper="Liu constrained wrapped least-squares",
        source_title="Constrained weighted least-squares dual-antenna attitude",
        source_year="",
        source_venue_or_journal="dual-antenna attitude literature",
        algorithm_family="dual_antenna_wrapped_yaw_wls",
        target_reproduction_type=ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION,
        required_inputs=("dual_status", "baseline_length", "trace_eval_reference"),
        required_backend="wrapped residual WLS with fixed baseline-length constraint",
        selected_for_q2r2=True,
        notes="Can use source-backed dual status only if it is not LegSA/final_v23 output.",
    ),
    MethodContract(
        method_id="DA03_YANG_BASELINE_KF_MLAMBDA",
        method_name="Yang GPS/BDS baseline-length constrained KF/MLAMBDA",
        source_paper="Yang GPS/BDS baseline KF/MLAMBDA",
        source_title="GPS/BDS dual-antenna baseline-length constrained KF/MLAMBDA",
        source_year="2024",
        source_venue_or_journal="GNSS/INS attitude literature",
        algorithm_family="dual_antenna_kf_mlambda",
        target_reproduction_type=ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION,
        required_inputs=("gnss1_raw", "gnss2_raw", "corr_raw", "dual_status", "trace_eval_reference"),
        required_backend="KF baseline state plus MLAMBDA ambiguity resolution",
        selected_for_q2r2=True,
        notes="Selected only if raw GNSS and ambiguity backend are available.",
    ),
    MethodContract(
        method_id="DA04_WU_ROBUST_DA_EQKF",
        method_name="Wu robust dual-antenna GNSS/INS EQKF",
        source_paper="Wu robust DA GNSS/INS EQKF",
        source_title="Robust dual-antenna GNSS/INS EQKF with misalignment compensation",
        source_year="",
        source_venue_or_journal="GNSS/INS attitude literature",
        algorithm_family="dual_antenna_gnss_ins_eqkf",
        target_reproduction_type=ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION,
        required_inputs=("dual_status", "go2_body_imu", "trace_eval_reference"),
        required_backend="external EQKF state propagation with body IMU and dual-antenna yaw update",
        selected_for_q2r2=True,
        notes="Receiver imu-data.csv is forbidden as Go2 body IMU; by2.txt is required if body IMU is used.",
    ),
    MethodContract(
        method_id="DA05_TEUNISSEN_AFFINE_MILS",
        method_name="Teunissen affine MILS fallback attitude",
        source_paper="Teunissen affine constrained MILS",
        source_title="Affine constrained mixed-integer least-squares attitude fallback",
        source_year="",
        source_venue_or_journal="GNSS attitude literature",
        algorithm_family="dual_antenna_affine_mils",
        target_reproduction_type=ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION,
        required_inputs=("gnss1_raw", "gnss2_raw", "corr_raw", "trace_eval_reference"),
        required_backend="affine MILS ambiguity backend",
        selected_for_q2r2=True,
        notes="Fallback candidate if C-LAMBDA backend can be reduced without policy-baseline promotion.",
    ),
    MethodContract(
        method_id="DA06_PAVLASEK_TWO_RECEIVER_IEKF",
        method_name="Pavlasek two-receiver IEKF",
        source_paper="Pavlasek two-receiver IEKF",
        source_title="Two-receiver GNSS/INS IEKF attitude method",
        source_year="",
        source_venue_or_journal="GNSS/INS attitude literature",
        algorithm_family="two_receiver_gnss_ins_iekf",
        target_reproduction_type=ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION,
        required_inputs=("dual_status", "go2_body_imu", "trace_eval_reference"),
        required_backend="IEKF/MEKF with external body IMU and two-receiver measurement model",
        selected_for_q2r2=False,
        notes="Held as backup because body IMU/provider closure is higher risk.",
    ),
)


def selected_methods() -> tuple[MethodContract, ...]:
    return tuple(method for method in METHOD_CATALOG if method.selected_for_q2r2)
