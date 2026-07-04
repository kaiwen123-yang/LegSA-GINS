"""Method contracts for the DA3R2 true dual-antenna stage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReproductionLevel(str, Enum):
    EXACT_REPRODUCTION = "EXACT_REPRODUCTION"
    FAITHFUL_ALGORITHM_REPRODUCTION = "FAITHFUL_ALGORITHM_REPRODUCTION"
    FAITHFUL_NON_OFFICIAL_ALGORITHM = "FAITHFUL_NON_OFFICIAL_ALGORITHM"
    FAITHFUL_MODULE_REPRODUCTION = "FAITHFUL_MODULE_REPRODUCTION"
    DIAGNOSTIC_STATUS_FALLBACK = "DIAGNOSTIC_STATUS_FALLBACK"
    BLOCKED_WITH_PROOF = "BLOCKED_WITH_PROOF"


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    method_name: str
    paper_source_id: str
    source_title: str
    backend_family: str
    reproduction_level: ReproductionLevel
    provider_layer_required: str
    exact_claim_allowed: bool
    notes: str


TARGET_METHODS: tuple[MethodContract, ...] = (
    MethodContract(
        "DA01_TEUNISSEN_CLAMBDA",
        "Teunissen C-LAMBDA constrained GNSS compass",
        "TEUNISSEN_CLAMBDA",
        "Integer least-squares theory for the GNSS compass / C-LAMBDA attitude ambiguity resolution",
        "baseline_length_constrained_integer_least_squares",
        ReproductionLevel.FAITHFUL_NON_OFFICIAL_ALGORITHM,
        "raw_carrier_rinex_rtklib_dd_ambiguity",
        False,
        "Non-official C-LAMBDA-style baseline-length constrained integer backend; RTKLIB supplies raw-carrier relative solution evidence.",
    ),
    MethodContract(
        "DA02_YANG_GPS_BDS_KF_MLAMBDA",
        "Yang GPS/BDS baseline-length constrained KF/MLAMBDA",
        "YANG_2024_GPS_BDS_KF_MLAMBDA",
        "GPS/BDS Dual-Antenna Attitude Determination With Baseline-Length Constrained Ambiguity Resolution",
        "sequential_baseline_kf_mlambda",
        ReproductionLevel.FAITHFUL_NON_OFFICIAL_ALGORITHM,
        "raw_carrier_rinex_rtklib_dd_ambiguity",
        False,
        "Sequential baseline/yaw filter with MLAMBDA-style integer candidate validation and baseline-length weighting.",
    ),
    MethodContract(
        "DA03_LIU_CWLS",
        "Liu constrained wrapped least squares",
        "LIU_CWLS_ARXIV_2112_14813",
        "Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination",
        "constrained_wrapped_least_squares",
        ReproductionLevel.FAITHFUL_NON_OFFICIAL_ALGORITHM,
        "raw_carrier_rinex_rtklib_dd_ambiguity",
        False,
        "Wrapped residual search/filter over raw-carrier backend yaw measurements; not status-yaw fallback.",
    ),
    MethodContract(
        "DA04_WU_ROBUST_EQKF_MISALIGNMENT",
        "Wu robust EQKF with misalignment compensation",
        "WU_ROBUST_EQKF_MISALIGNMENT",
        "Robust Dual-Antenna GNSS/INS Attitude Determination via Constrained Ambiguity Resolution and Misalignment Compensation",
        "robust_eqkf_misalignment",
        ReproductionLevel.FAITHFUL_NON_OFFICIAL_ALGORITHM,
        "raw_carrier_rinex_rtklib_dd_ambiguity_plus_go2_yaw_rate",
        False,
        "Robust yaw EQKF using Go2 yaw-rate source and raw-carrier dual-antenna updates; receiver IMU is forbidden.",
    ),
    MethodContract(
        "DA05_AFFINE_MILS_SINGLE_BASELINE",
        "Affine MILS single-baseline integer least squares",
        "AFFINE_MILS_SINGLE_BASELINE",
        "The affine constrained GNSS attitude model and its multivariate integer least-squares solution",
        "affine_mixed_integer_least_squares_single_baseline",
        ReproductionLevel.FAITHFUL_NON_OFFICIAL_ALGORITHM,
        "raw_carrier_rinex_rtklib_dd_ambiguity",
        False,
        "Single-baseline affine MILS-style constrained baseline projection over raw-carrier relative solution evidence.",
    ),
)


def target_method_ids() -> list[str]:
    return [method.method_id for method in TARGET_METHODS]


def get_method(method_id: str) -> MethodContract:
    for method in TARGET_METHODS:
        if method.method_id == method_id:
            return method
    raise KeyError(method_id)
