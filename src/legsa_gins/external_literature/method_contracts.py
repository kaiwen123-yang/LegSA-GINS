"""Method contracts for DA2R2 true/faithful dual-antenna execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    name: str
    family: str
    reproduction_type: str
    claim_level: str
    outputs_position: bool
    outputs_yaw: bool
    state_model: str
    measurement_model: str
    backend: str


DA2R2_METHODS: tuple[MethodContract, ...] = (
    MethodContract(
        method_id="DA2R2_A_TWO_RECEIVER_IEKF",
        name="Two-Receiver IEKF / Pavlasek-style simplified invariant EKF",
        family="two_receiver_gnss_ins_heading",
        reproduction_type="FAITHFUL_NON_OFFICIAL_ALGORITHM",
        claim_level="main_candidate_caveated",
        outputs_position=True,
        outputs_yaw=True,
        state_model="local ENU position, velocity, body yaw, simplified yaw-rate propagation",
        measurement_model="GNSS1 receiver position plus GNSS2-GNSS1 baseline-derived body yaw",
        backend="discrete EKF with prediction/update and wrapped yaw update",
    ),
    MethodContract(
        method_id="DA2R2_B_DUAL_HEADING_AIDED_EKF",
        name="Dual-Antenna Heading-Aided EKF / MEKF-style",
        family="dual_antenna_heading_aided_gnss_ins",
        reproduction_type="FAITHFUL_NON_OFFICIAL_ALGORITHM",
        claim_level="main_candidate_caveated",
        outputs_position=True,
        outputs_yaw=True,
        state_model="local ENU position, velocity, body yaw",
        measurement_model="GNSS position, finite-difference receiver velocity, dual-antenna yaw",
        backend="heading-aided EKF with independent state and wrapped yaw innovation",
    ),
    MethodContract(
        method_id="DA2R2_C_CONSTRAINED_BASELINE_WLS",
        name="Constrained Baseline WLS / GNSS Compass",
        family="gnss_compass_constrained_baseline_wls",
        reproduction_type="FAITHFUL_MODULE_REPRODUCTION",
        claim_level="main_candidate_caveated",
        outputs_position=False,
        outputs_yaw=True,
        state_model="per-epoch baseline heading with temporal circular smoothing",
        measurement_model="GNSS2-GNSS1 status baseline, rel_acc/yaw_std weights, baseline length prior",
        backend="weighted least-squares baseline projection with wrap-safe heading smoothing",
    ),
)


def get_method_contract(method_id: str) -> MethodContract:
    for method in DA2R2_METHODS:
        if method.method_id == method_id:
            return method
    raise KeyError(method_id)
