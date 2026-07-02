"""A1 runnable external dual-antenna method contracts."""

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
    source_year: str
    source_type: str
    official_code_status: str
    reproduction_type: ReproductionType
    state_model_available: bool
    measurement_model_available: bool
    backend_available: bool
    by2_provider_inputs_available: bool
    yaw_frame_policy: str
    expected_outputs: str
    claim_level: str
    notes: str


METHOD_CATALOG: tuple[MethodContract, ...] = (
    MethodContract("DA02_LIU_CONSTRAINED_WRAPPED_WLS", "Liu constrained wrapped least-squares attitude", "Liu constrained wrapped least-squares dual-antenna attitude", "", "dual_antenna_short_baseline_attitude", "no_official_code_used", ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION, True, True, True, True, "BY2 GNSS2-GNSS1 status relpos difference plus fixed +90 deg body conversion", "yaw_only_epoch_output", "appendix_candidate", "Non-official wrapped WLS yaw implementation on real BY2 status short-baseline observations."),
    MethodContract("DA03_YANG_BASELINE_KF_STATUS", "Yang baseline-length constrained KF yaw implementation", "Yang GPS/BDS baseline-length constrained KF / MLAMBDA family", "2024", "dual_antenna_baseline_kf", "no_official_code_used", ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION, True, True, True, True, "BY2 GNSS2-GNSS1 status relpos difference plus fixed +90 deg body conversion", "yaw_only_epoch_output", "appendix_candidate", "Yaw-state KF with baseline-length measurement weighting; raw ambiguity component is not claimed exact."),
    MethodContract("DA04_WU_ROBUST_EQKF_GO2", "Wu robust dual-antenna GNSS/INS EQKF yaw implementation", "Wu robust dual-antenna GNSS/INS EQKF", "", "dual_antenna_gnss_ins_robust_filter", "no_official_code_used", ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION, True, True, True, True, "BY2 GNSS2-GNSS1 status relpos difference plus fixed +90 deg body conversion", "yaw_only_epoch_output", "appendix_candidate", "Robust yaw-state EKF uses Go2 sportmodestate yaw_rate as body source; receiver imu-data.csv is not used."),
    MethodContract("DA01_TEUNISSEN_CLAMBDA_COMPASS", "Teunissen C-LAMBDA short-baseline GNSS compass", "Teunissen C-LAMBDA / GNSS compass", "", "carrier_phase_integer_attitude", "not_available", ReproductionType.BLOCKED_WITH_PROOF, True, True, False, True, "not_run", "blocked_with_proof", "blocked_with_proof", "Blocked because this A1 implementation does not close a carrier DD/LOS integer ambiguity backend."),
    MethodContract("DA05_TEUNISSEN_AFFINE_MILS", "Teunissen affine MILS fallback attitude", "Teunissen affine constrained MILS", "", "mixed_integer_least_squares_attitude", "not_available", ReproductionType.BLOCKED_WITH_PROOF, True, True, False, True, "not_run", "blocked_with_proof", "blocked_with_proof", "Blocked because affine MILS ambiguity backend is not closed without reducing it to a policy baseline."),
    MethodContract("DA06_PAVLASEK_TWO_RECEIVER_IEKF", "Pavlasek two-receiver IEKF", "Pavlasek two-receiver IEKF", "", "two_receiver_gnss_ins_filter", "not_available", ReproductionType.DIAGNOSTIC_ONLY, False, True, False, True, "not_selected", "not_selected", "diagnostic_only", "Not selected for A1 because the full IEKF/MEKF frame closure remains higher risk."),
)


def selected_methods() -> tuple[MethodContract, ...]:
    return tuple(method for method in METHOD_CATALOG if method.reproduction_type == ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION)
