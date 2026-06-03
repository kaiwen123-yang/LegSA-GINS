"""Runtime-only BY2 formal LegSA algorithm runner wrapper.

The wrapper calls the existing ``legsa_v23_port_core_demo --config`` surface.
It does not implement EKF/FGO math and deliberately does not use the diagnostic
``legsa_gins --run-filter-csv`` path for formal algorithms.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


QA11F_CLASSIC5_METHODS = [
    "qa11e_nis_chi_square_EKF",
    "qa11e_mahalanobis_gate_EKF",
    "qa11e_covariance_matching_EKF",
    "qa11e_huber_weight_EKF",
    "qa11e_igg3_weight_EKF",
]

QA11F_RECENT5_METHODS = [
    "qa11e_dcs_weight_EKF",
    "qa11e_gnss_status_fix_EKF",
    "qa11e_position_std_adaptive_EKF",
    "qa11e_baseline_length_a1_EKF",
    "qa11e_yaw_std_adaptive_EKF",
]

QA11F_CLASSIC5_RECENT5_ALGORITHMS = QA11F_CLASSIC5_METHODS + QA11F_RECENT5_METHODS

QA11G_CLASSIC5_METHODS = [
    "qa11g_kalman1960_nis_chi_square_EKF",
    "qa11g_mahalanobis1936_innovation_gate_EKF",
    "qa11g_mehra1970_covariance_matching_EKF",
    "qa11g_huber1964_m_estimator_EKF",
    "qa11g_yang2002_igg3_equiv_weight_EKF",
]

QA11G_RECENT5_METHODS = [
    "qa11g_wang2020_tc_gnss_ins_fde_EKF",
    "qa11g_yan2021_irakf_solution_state_EKF",
    "qa11g_sun2022_dual_w_test_EKF",
    "qa11g_yin2023_improved_R_rakf_EKF",
    "qa11g_chen2025_fading_factor_arkf_EKF",
]

QA11G_CONCRETE_PAPER_10_METHODS = QA11G_CLASSIC5_METHODS + QA11G_RECENT5_METHODS

QA11G_METHOD_SOURCE_BINDINGS: dict[str, dict[str, str | int | bool]] = {
    "qa11g_kalman1960_nis_chi_square_EKF": {
        "method_group": "classic5",
        "source_id": "QA11G_SRC_KALMAN_1960_NIS",
        "title": "A New Approach to Linear Filtering and Prediction Problems",
        "authors": "R. E. Kalman",
        "year": 1960,
        "venue": "Journal of Basic Engineering",
        "doi_or_url": "https://doi.org/10.1115/1.3662552",
        "reimplementation_label": "CLASSIC_METHOD_BASELINE",
        "exact_reproduction": False,
        "core_rule": "NIS = nu^T S^-1 nu; inflate or cap R when normalized innovation exceeds fixed chi-square-style gates.",
    },
    "qa11g_mahalanobis1936_innovation_gate_EKF": {
        "method_group": "classic5",
        "source_id": "QA11G_SRC_MAHALANOBIS_1936_DISTANCE",
        "title": "On the Generalized Distance in Statistics",
        "authors": "P. C. Mahalanobis",
        "year": 1936,
        "venue": "Proceedings of the National Institute of Sciences of India",
        "doi_or_url": "https://insa.nic.in/writereaddata/UpLoadedFiles/PINSA/Vol02_1936_1_Art05.pdf",
        "reimplementation_label": "CLASSIC_METHOD_BASELINE",
        "exact_reproduction": False,
        "core_rule": "Use Mahalanobis innovation distance with a reject/downweight gate on BY2 EKF measurement residuals.",
    },
    "qa11g_mehra1970_covariance_matching_EKF": {
        "method_group": "classic5",
        "source_id": "QA11G_SRC_MEHRA_1970_COVARIANCE_MATCHING",
        "title": "On the Identification of Variances and Adaptive Kalman Filtering",
        "authors": "R. K. Mehra",
        "year": 1970,
        "venue": "IEEE Transactions on Automatic Control",
        "doi_or_url": "https://doi.org/10.1109/TAC.1970.1099422",
        "reimplementation_label": "CLASSIC_METHOD_BASELINE",
        "exact_reproduction": False,
        "core_rule": "Use innovation covariance mismatch to adaptively inflate measurement covariance.",
    },
    "qa11g_huber1964_m_estimator_EKF": {
        "method_group": "classic5",
        "source_id": "QA11G_SRC_HUBER_1964_M_ESTIMATOR",
        "title": "Robust Estimation of a Location Parameter",
        "authors": "P. J. Huber",
        "year": 1964,
        "venue": "Annals of Mathematical Statistics",
        "doi_or_url": "https://doi.org/10.1214/aoms/1177703732",
        "reimplementation_label": "CLASSIC_METHOD_BASELINE",
        "exact_reproduction": False,
        "core_rule": "Equivalent weight is one inside the Huber threshold and c / |r| outside it.",
    },
    "qa11g_yang2002_igg3_equiv_weight_EKF": {
        "method_group": "classic5",
        "source_id": "QA11G_SRC_YANG_2002_ROBUST_GEODETIC",
        "title": "Robust estimator for correlated observations based on bifactor equivalent weights",
        "authors": "Y. Yang, L. Song, T. Xu",
        "year": 2002,
        "venue": "Journal of Geodesy",
        "doi_or_url": "https://doi.org/10.1007/s00190-002-0256-7",
        "reimplementation_label": "CLASSIC_METHOD_BASELINE",
        "exact_reproduction": False,
        "core_rule": "Use a two-threshold geodetic equivalent-weight curve: full weight, tapered weight, then capped rejection.",
    },
    "qa11g_wang2020_tc_gnss_ins_fde_EKF": {
        "method_group": "recent5",
        "source_id": "QA11G_SRC_WANG_2020_TC_GNSS_INS_FDE",
        "title": "Fault Detection and Exclusion for Tightly Coupled GNSS/INS System Considering Fault in State Prediction",
        "authors": "Shizhuang Wang, Xingqun Zhan, Yawei Zhai, Baoyu Liu",
        "year": 2020,
        "venue": "Sensors",
        "doi_or_url": "https://doi.org/10.3390/s20030590",
        "reimplementation_label": "RECENT_PAPER_DERIVED_BY2_REIMPLEMENTATION",
        "exact_reproduction": False,
        "core_rule": "Use prediction-aware innovation fault detection; BY2 maps this to innovation gating with reject-extreme enabled.",
    },
    "qa11g_yan2021_irakf_solution_state_EKF": {
        "method_group": "recent5",
        "source_id": "QA11G_SRC_YAN_2021_IRAKF_GNSS_MEMS",
        "title": "An Improved Adaptive Kalman Filter for a Single Frequency GNSS/MEMS-IMU/Odometer Integrated Navigation Module",
        "authors": "Peihui Yan, Jinguang Jiang, Fangning Zhang, Dongpeng Xie, Jiaji Wu, Chao Zhang",
        "year": 2021,
        "venue": "Remote Sensing",
        "doi_or_url": "https://doi.org/10.3390/rs13214317",
        "reimplementation_label": "RECENT_PAPER_DERIVED_BY2_REIMPLEMENTATION",
        "exact_reproduction": False,
        "core_rule": "Use GNSS solution-quality state to scale measurement covariance; BY2 uses receiver position/std innovation fields.",
    },
    "qa11g_sun2022_dual_w_test_EKF": {
        "method_group": "recent5",
        "source_id": "QA11G_SRC_SUN_2022_DUAL_W_TEST",
        "title": "A Dual w-Test Based Quality Control Algorithm for Integrated IMU/GNSS Navigation in Urban Areas",
        "authors": "Rui Sun, Ming Qiu, Fei Liu, Zhi Wang, Washington Yotto Ochieng",
        "year": 2022,
        "venue": "Remote Sensing",
        "doi_or_url": "https://doi.org/10.3390/rs14092132",
        "reimplementation_label": "RECENT_PAPER_DERIVED_BY2_REIMPLEMENTATION",
        "exact_reproduction": False,
        "core_rule": "Use two-stage normalized residual tests for fault detection/isolation; BY2 maps them to innovation reject/downweight gates.",
    },
    "qa11g_yin2023_improved_R_rakf_EKF": {
        "method_group": "recent5",
        "source_id": "QA11G_SRC_YIN_2023_IMPROVED_R_RAKF",
        "title": "A Robust Adaptive Extended Kalman Filter Based on an Improved Measurement Noise Covariance Matrix for the Monitoring and Isolation of Abnormal Disturbances in GNSS/INS Vehicle Navigation",
        "authors": "Zhihui Yin, Jichao Yang, Yue Ma, Shengli Wang, Dashuai Chai, Haonan Cui",
        "year": 2023,
        "venue": "Remote Sensing",
        "doi_or_url": "https://doi.org/10.3390/rs15174125",
        "reimplementation_label": "RECENT_PAPER_DERIVED_BY2_REIMPLEMENTATION",
        "exact_reproduction": False,
        "core_rule": "Adapt measurement covariance from residual consistency while preserving a robust lower bound against overconfidence.",
    },
    "qa11g_chen2025_fading_factor_arkf_EKF": {
        "method_group": "recent5",
        "source_id": "QA11G_SRC_CHEN_2025_FADING_FACTOR_ARKF",
        "title": "An Improved Fading Factor-Based Adaptive Robust Filtering Algorithm for SINS/GNSS Integration with Dynamic Disturbance Suppression",
        "authors": "Zhaohao Chen, Yixu Liu, Shangguo Liu, Shengli Wang, Lei Yang",
        "year": 2025,
        "venue": "Remote Sensing",
        "doi_or_url": "https://doi.org/10.3390/rs17081449",
        "reimplementation_label": "RECENT_PAPER_DERIVED_BY2_REIMPLEMENTATION",
        "exact_reproduction": False,
        "core_rule": "Use fading-factor adaptive robust filtering; BY2 maps the disturbance response to stronger innovation-based R inflation.",
    },
}



FORMAL_ALGORITHMS = [
    "source_backed_EKF",
    "baseline_no_feedback_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "selected_feedback_EKF",
    "LegSA_full_EKF",
    "LegSA_QA_Fallback_EKF",
    "LegSA_9F_FGO_EKF",
    "robust_innovation_reject_EKF",
    "nis_adaptive_R_EKF",
    "doppler_consistency_gate_EKF",
] + QA11F_CLASSIC5_RECENT5_ALGORITHMS + QA11G_CONCRETE_PAPER_10_METHODS

REPO_RELATIVE_REQUIRED_INPUTS = {
    "raw_doppler": Path("运行结果") / "N5B_rtklib_doppler_provider_activation" / "RAW_DOPPLER_VELOCITY_FACTORS.csv",
    "go2_attitude": Path("运行结果")
    / "N7C6_go2_proprioceptive_joint_factor"
    / "priors"
    / "joint_rp1p6deg_hv1p0"
    / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv",
    "go2_horizontal_velocity": Path("运行结果")
    / "N7C6_go2_proprioceptive_joint_factor"
    / "priors"
    / "joint_rp1p6deg_hv1p0"
    / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv",
    "go2_joint": Path("运行结果")
    / "N7C6_go2_proprioceptive_joint_factor"
    / "priors"
    / "joint_rp1p6deg_hv1p0"
    / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv",
    "selected_feedback": Path("运行结果")
    / "N8J_feedback_final_validation"
    / "variants"
    / "n8j_selected_conservative_feedback"
    / "FGO_FEEDBACK_OBSERVATIONS.csv",
}

BASE_CONFIG_CANDIDATES = [
    Path("运行结果")
    / "N8J_feedback_final_validation"
    / "variants"
    / "baseline_no_feedback"
    / "config"
    / "legsa_v23_port_clean_replay.conf",
    Path("运行结果")
    / "N8J_feedback_final_validation"
    / "variants"
    / "n8j_selected_conservative_feedback"
    / "config"
    / "legsa_v23_port_clean_replay.conf",
    Path("运行结果")
    / "N5B_rtklib_doppler_provider_activation"
    / "runtime_configs"
    / "n5b_raw_doppler_enabled.yaml",
]


@dataclass(frozen=True)
class AlgorithmRunnerSpec:
    algorithm: str
    ablation_variant: str
    component_flags: dict[str, bool]
    status: str = "runnable_with_wrapper"
    role: str = "formal_algorithm"
    active_fgo_backend_available: bool = False
    solver_execution_allowed: bool = True
    complete_nine_factor_fgo_claim: bool = False
    config_overrides: dict[str, str] = field(default_factory=dict)


ALGORITHM_SPECS = {
    "source_backed_EKF": AlgorithmRunnerSpec(
        algorithm="source_backed_EKF",
        ablation_variant="n9b1f_source_backed_EKF_normal",
        component_flags={
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "baseline_no_feedback_EKF": AlgorithmRunnerSpec(
        algorithm="baseline_no_feedback_EKF",
        ablation_variant="n9b1f_baseline_no_feedback_EKF_normal",
        component_flags={
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "Raw_Doppler_EKF": AlgorithmRunnerSpec(
        algorithm="Raw_Doppler_EKF",
        ablation_variant="n9b1f_Raw_Doppler_EKF_normal",
        component_flags={
            "raw_doppler": True,
            "source_aware": False,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "source_aware_EKF": AlgorithmRunnerSpec(
        algorithm="source_aware_EKF",
        ablation_variant="n9b1f_source_aware_EKF_normal",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
    ),
    "Go2_joint_EKF": AlgorithmRunnerSpec(
        algorithm="Go2_joint_EKF",
        ablation_variant="n9b1f_Go2_joint_EKF_normal",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": False,
        },
    ),
    "selected_feedback_EKF": AlgorithmRunnerSpec(
        algorithm="selected_feedback_EKF",
        ablation_variant="n9b1f_selected_feedback_EKF_normal",
        component_flags={
            "raw_doppler": False,
            "source_aware": False,
            "go2_joint": False,
            "feedback": True,
        },
    ),
    "LegSA_full_EKF": AlgorithmRunnerSpec(
        algorithm="LegSA_full_EKF",
        ablation_variant="n9c0c_LegSA_full_EKF",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": True,
        },
    ),
    "LegSA_QA_Fallback_EKF": AlgorithmRunnerSpec(
        algorithm="LegSA_QA_Fallback_EKF",
        ablation_variant="qa2_LegSA_QA_Fallback_EKF",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": True,
        },
        status="qa_fallback_candidate",
        role="new_algorithm_candidate",
        active_fgo_backend_available=False,
        solver_execution_allowed=True,
        complete_nine_factor_fgo_claim=False,
    ),
    "LegSA_9F_FGO_EKF": AlgorithmRunnerSpec(
        algorithm="LegSA_9F_FGO_EKF",
        ablation_variant="n9g1b_LegSA_9F_FGO_EKF_phase1_candidate",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": True,
            "feedback": True,
        },
        status="phase1_candidate_backend_blocked",
        role="new_algorithm_candidate",
        active_fgo_backend_available=False,
        solver_execution_allowed=False,
        complete_nine_factor_fgo_claim=False,
    ),
    "robust_innovation_reject_EKF": AlgorithmRunnerSpec(
        algorithm="robust_innovation_reject_EKF",
        ablation_variant="qa10b_method_inspired_innovation_threshold_reject",
        component_flags={
            "raw_doppler": False,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
        status="method_inspired_baseline",
        role="literature_inspired_baseline",
        config_overrides={
            "source_aware_mode": "oim_only",
            "source_aware_policy_version": "n6b_conservative_innovation_covariance",
            "source_aware_use_innovation_covariance": "true",
            "source_aware_reject_extreme": "true",
            "source_aware_trace_enabled": "true",
        },
    ),
    "nis_adaptive_R_EKF": AlgorithmRunnerSpec(
        algorithm="nis_adaptive_R_EKF",
        ablation_variant="qa10b_method_inspired_nis_adaptive_R",
        component_flags={
            "raw_doppler": False,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
        status="method_inspired_baseline",
        role="literature_inspired_baseline",
        config_overrides={
            "source_aware_mode": "oim_only",
            "source_aware_policy_version": "n6b_conservative_innovation_covariance",
            "source_aware_use_innovation_covariance": "true",
            "source_aware_reject_extreme": "false",
            "source_aware_trace_enabled": "true",
        },
    ),
    "doppler_consistency_gate_EKF": AlgorithmRunnerSpec(
        algorithm="doppler_consistency_gate_EKF",
        ablation_variant="qa10b_method_inspired_raw_doppler_consistency_gate",
        component_flags={
            "raw_doppler": True,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
        status="method_inspired_baseline_partial_doppler_gate",
        role="literature_inspired_baseline",
        config_overrides={
            "source_aware_mode": "lsim_oim",
            "source_aware_policy_version": "n6b_conservative_innovation_covariance",
            "source_aware_use_innovation_covariance": "true",
            "source_aware_reject_extreme": "true",
            "raw_doppler_min_sat": "5",
            "raw_doppler_residual_gate_mps": "3.0",
            "raw_doppler_R_scale": "1.0",
            "source_aware_trace_enabled": "true",
        },
    ),
}


def _qa11e_source_only(source_name: str) -> dict[str, str]:
    sources = ["receiver_position", "receiver_velocity", "dual_antenna_yaw", "raw_doppler_velocity"]
    overrides: dict[str, str] = {}
    for source in sources:
        enabled = source == source_name
        overrides[f"source_aware_{source}_enabled"] = str(enabled).lower()
        overrides[f"source_aware_{source}_lsim_enabled"] = str(enabled).lower()
        overrides[f"source_aware_{source}_oim_enabled"] = str(enabled).lower()
    return overrides


def _qa11e_overrides(
    *,
    family: str,
    label: str,
    source_id: str,
    k0: float = 1.5,
    k1: float = 4.0,
    c: float = 2.5,
    alpha: float = 0.0,
    phi: float = 1.0,
    gain: float = 1.0,
    mode: str = "lsim_oim",
    reject_extreme: bool = False,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    overrides = {
        "qa11e_method_label": label,
        "qa11e_paper_source_id": source_id,
        "exact_reproduction": "false",
        "source_aware_mode": mode,
        "source_aware_policy_version": "n6b_conservative_innovation_covariance",
        "source_aware_method_family": family,
        "source_aware_method_k0": f"{k0}",
        "source_aware_method_k1": f"{k1}",
        "source_aware_method_c": f"{c}",
        "source_aware_method_alpha": f"{alpha}",
        "source_aware_method_phi": f"{phi}",
        "source_aware_method_base_gain": f"{gain}",
        "source_aware_use_innovation_covariance": "true",
        "source_aware_reject_extreme": str(reject_extreme).lower(),
        "source_aware_trace_enabled": "true",
        "source_aware_go2_attitude_roll_pitch_enabled": "false",
        "source_aware_go2_attitude_roll_pitch_lsim_enabled": "false",
        "source_aware_go2_attitude_roll_pitch_oim_enabled": "false",
        "source_aware_go2_horizontal_velocity_enabled": "false",
        "source_aware_go2_horizontal_velocity_lsim_enabled": "false",
        "source_aware_go2_horizontal_velocity_oim_enabled": "false",
    }
    if extra:
        overrides.update(extra)
    return overrides


def _qa11e_spec(algorithm: str, variant: str, overrides: dict[str, str]) -> AlgorithmRunnerSpec:
    return AlgorithmRunnerSpec(
        algorithm=algorithm,
        ablation_variant=variant,
        component_flags={
            "raw_doppler": False,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
        status="qa11e_executable_EKF_QC_config_variant",
        role="literature_inspired_baseline",
        active_fgo_backend_available=False,
        solver_execution_allowed=True,
        complete_nine_factor_fgo_claim=False,
        config_overrides=overrides,
    )


ALGORITHM_SPECS.update(
    {
        "qa11e_nis_chi_square_EKF": _qa11e_spec(
            "qa11e_nis_chi_square_EKF",
            "qa11e_literature20_nis_chi_square",
            _qa11e_overrides(
                family="nis_chi_square",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_NIS_CHI_SQUARE",
                k0=1.732,
                k1=3.0,
                gain=1.0,
            ),
        ),
        "qa11e_mahalanobis_gate_EKF": _qa11e_spec(
            "qa11e_mahalanobis_gate_EKF",
            "qa11e_literature20_mahalanobis_gate",
            _qa11e_overrides(
                family="mahalanobis_gate",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_MAHALANOBIS_GATING",
                k0=1.5,
                k1=3.5,
                gain=1.2,
                reject_extreme=True,
            ),
        ),
        "qa11e_covariance_matching_EKF": _qa11e_spec(
            "qa11e_covariance_matching_EKF",
            "qa11e_literature20_covariance_matching",
            _qa11e_overrides(
                family="covariance_matching",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_COVARIANCE_MATCHING",
                k0=1.2,
                k1=4.0,
                gain=0.6,
            ),
        ),
        "qa11e_huber_weight_EKF": _qa11e_spec(
            "qa11e_huber_weight_EKF",
            "qa11e_literature20_huber",
            _qa11e_overrides(
                family="huber",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_HUBER_ROBUST_EKF",
                c=1.5,
            ),
        ),
        "qa11e_cauchy_weight_EKF": _qa11e_spec(
            "qa11e_cauchy_weight_EKF",
            "qa11e_literature20_cauchy",
            _qa11e_overrides(
                family="cauchy",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_CAUCHY_ROBUST_EKF",
                c=2.0,
            ),
        ),
        "qa11e_tukey_biweight_EKF": _qa11e_spec(
            "qa11e_tukey_biweight_EKF",
            "qa11e_literature20_tukey_biweight",
            _qa11e_overrides(
                family="tukey",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_TUKEY_BIWEIGHT",
                c=4.685,
                reject_extreme=False,
            ),
        ),
        "qa11e_igg3_weight_EKF": _qa11e_spec(
            "qa11e_igg3_weight_EKF",
            "qa11e_literature20_igg3",
            _qa11e_overrides(
                family="igg3",
                label="CLASSIC_METHOD_BASELINE",
                source_id="QA11E_SRC_IGG3_GEODETIC_ROBUST",
                k0=1.5,
                k1=3.0,
            ),
        ),
        "qa11e_barron_loss_EKF": _qa11e_spec(
            "qa11e_barron_loss_EKF",
            "qa11e_literature20_barron_loss",
            _qa11e_overrides(
                family="barron",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_BARRON_GENERAL_ROBUST_LOSS",
                c=2.0,
                alpha=0.0,
                gain=0.8,
            ),
        ),
        "qa11e_dcs_weight_EKF": _qa11e_spec(
            "qa11e_dcs_weight_EKF",
            "qa11e_literature20_dcs",
            _qa11e_overrides(
                family="dcs",
                label="PAPER_DERIVED_BY2_REIMPLEMENTATION",
                source_id="QA11E_SRC_DYNAMIC_COVARIANCE_SCALING",
                phi=4.0,
            ),
        ),
        "qa11e_switchable_weight_EKF": _qa11e_spec(
            "qa11e_switchable_weight_EKF",
            "qa11e_literature20_switchable_constraint",
            _qa11e_overrides(
                family="switchable",
                label="PAPER_DERIVED_BY2_REIMPLEMENTATION",
                source_id="QA11E_SRC_SWITCHABLE_CONSTRAINTS",
                c=2.5,
            ),
        ),
        "qa11e_gnss_status_fix_EKF": _qa11e_spec(
            "qa11e_gnss_status_fix_EKF",
            "qa11e_literature20_gnss_status_fix",
            _qa11e_overrides(
                family="n6b_conservative_quadratic",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_GNSS_FIX_STATUS_QC",
                mode="lsim_only",
                extra={"source_aware_receiver_position_cap": "15.0", "source_aware_dual_yaw_cap": "15.0"},
            ),
        ),
        "qa11e_position_std_adaptive_EKF": _qa11e_spec(
            "qa11e_position_std_adaptive_EKF",
            "qa11e_literature20_position_std_adaptive",
            _qa11e_overrides(
                family="covariance_matching",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_GNSS_POSITION_STD_ADAPTIVE",
                k0=1.2,
                gain=0.8,
                extra=_qa11e_source_only("receiver_position"),
            ),
        ),
        "qa11e_velocity_std_adaptive_EKF": _qa11e_spec(
            "qa11e_velocity_std_adaptive_EKF",
            "qa11e_literature20_velocity_std_adaptive",
            _qa11e_overrides(
                family="covariance_matching",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_GNSS_VELOCITY_STD_ADAPTIVE",
                k0=1.2,
                gain=0.8,
                extra=_qa11e_source_only("receiver_velocity"),
            ),
        ),
        "qa11e_baseline_length_a1_EKF": _qa11e_spec(
            "qa11e_baseline_length_a1_EKF",
            "qa11e_literature20_a1_baseline_qc",
            _qa11e_overrides(
                family="n6b_conservative_quadratic",
                label="PAPER_DERIVED_BY2_REIMPLEMENTATION",
                source_id="QA11E_SRC_DUAL_ANTENNA_BASELINE_QC",
                mode="lsim_only",
                extra=_qa11e_source_only("dual_antenna_yaw"),
            ),
        ),
        "qa11e_yaw_std_adaptive_EKF": _qa11e_spec(
            "qa11e_yaw_std_adaptive_EKF",
            "qa11e_literature20_yaw_std_adaptive",
            _qa11e_overrides(
                family="huber",
                label="PAPER_DERIVED_BY2_REIMPLEMENTATION",
                source_id="QA11E_SRC_DUAL_YAW_STD_ADAPTIVE",
                c=1.8,
                extra=_qa11e_source_only("dual_antenna_yaw"),
            ),
        ),
        "qa11e_yaw_jump_monitor_EKF": _qa11e_spec(
            "qa11e_yaw_jump_monitor_EKF",
            "qa11e_literature20_yaw_jump_monitor",
            _qa11e_overrides(
                family="tukey",
                label="PAPER_DERIVED_BY2_REIMPLEMENTATION",
                source_id="QA11E_SRC_DUAL_YAW_JUMP_MONITOR",
                c=3.0,
                extra=_qa11e_source_only("dual_antenna_yaw"),
            ),
        ),
        "qa11e_time_continuity_EKF": _qa11e_spec(
            "qa11e_time_continuity_EKF",
            "qa11e_literature20_time_continuity_qc",
            _qa11e_overrides(
                family="n6b_conservative_quadratic",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_TIME_CONTINUITY_QC",
                mode="lsim_only",
            ),
        ),
        "qa11e_position_update_huber_EKF": _qa11e_spec(
            "qa11e_position_update_huber_EKF",
            "qa11e_literature20_position_only_huber",
            _qa11e_overrides(
                family="huber",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_POSITION_UPDATE_ROBUST_ONLY",
                c=1.5,
                extra=_qa11e_source_only("receiver_position"),
            ),
        ),
        "qa11e_velocity_update_huber_EKF": _qa11e_spec(
            "qa11e_velocity_update_huber_EKF",
            "qa11e_literature20_velocity_only_huber",
            _qa11e_overrides(
                family="huber",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_VELOCITY_UPDATE_ROBUST_ONLY",
                c=1.5,
                extra=_qa11e_source_only("receiver_velocity"),
            ),
        ),
        "qa11e_yaw_update_huber_EKF": _qa11e_spec(
            "qa11e_yaw_update_huber_EKF",
            "qa11e_literature20_yaw_only_huber",
            _qa11e_overrides(
                family="huber",
                label="RECENT_PAPER_MOTIVATED_VARIANT",
                source_id="QA11E_SRC_YAW_UPDATE_ROBUST_ONLY",
                c=1.5,
                extra=_qa11e_source_only("dual_antenna_yaw"),
            ),
        ),
    }
)


def _qa11g_overrides(
    *,
    algorithm: str,
    family: str,
    k0: float = 1.5,
    k1: float = 4.0,
    c: float = 2.5,
    alpha: float = 0.0,
    phi: float = 1.0,
    gain: float = 1.0,
    mode: str = "lsim_oim",
    reject_extreme: bool = False,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    binding = QA11G_METHOD_SOURCE_BINDINGS[algorithm]
    label = str(binding["reimplementation_label"])
    source_id = str(binding["source_id"])
    overrides = _qa11e_overrides(
        family=family,
        label=label,
        source_id=source_id,
        k0=k0,
        k1=k1,
        c=c,
        alpha=alpha,
        phi=phi,
        gain=gain,
        mode=mode,
        reject_extreme=reject_extreme,
        extra=extra,
    )
    overrides.update(
        {
            "qa11g_stage": "QA11G_CONCRETE_PAPER_SOURCED_10METHOD_RAW_BY2_FULL_MATRIX",
            "qa11g_method_group": str(binding["method_group"]),
            "qa11g_method_label": label,
            "qa11g_reimplementation_label": label,
            "qa11g_paper_source_id": source_id,
            "qa11g_concrete_paper_title": str(binding["title"]),
            "qa11g_concrete_paper_year": str(binding["year"]),
            "qa11g_concrete_paper_venue": str(binding["venue"]),
            "qa11g_concrete_paper_doi_or_url": str(binding["doi_or_url"]),
            "qa11g_core_formula_or_rule": str(binding["core_rule"]),
            "source_verification_status": "verified_concrete_doi_or_url",
            "trace_tuning": "false",
            "final_v23_tuning": "false",
            "trace_solver_input": "false",
            "final_v23_output_solver_input": "false",
            "receiver_imu_data_as_body_imu": "false",
            "exact_reproduction": "false",
        }
    )
    return overrides


def _qa11g_spec(algorithm: str, variant: str, overrides: dict[str, str]) -> AlgorithmRunnerSpec:
    return AlgorithmRunnerSpec(
        algorithm=algorithm,
        ablation_variant=variant,
        component_flags={
            "raw_doppler": False,
            "source_aware": True,
            "go2_joint": False,
            "feedback": False,
        },
        status="qa11g_concrete_paper_sourced_by2_reimplementation",
        role="concrete_paper_sourced_external_baseline",
        active_fgo_backend_available=False,
        solver_execution_allowed=True,
        complete_nine_factor_fgo_claim=False,
        config_overrides=overrides,
    )


ALGORITHM_SPECS.update(
    {
        "qa11g_kalman1960_nis_chi_square_EKF": _qa11g_spec(
            "qa11g_kalman1960_nis_chi_square_EKF",
            "qa11g_kalman1960_nis_chi_square",
            _qa11g_overrides(
                algorithm="qa11g_kalman1960_nis_chi_square_EKF",
                family="nis_chi_square",
                k0=1.732,
                k1=3.0,
                gain=1.0,
            ),
        ),
        "qa11g_mahalanobis1936_innovation_gate_EKF": _qa11g_spec(
            "qa11g_mahalanobis1936_innovation_gate_EKF",
            "qa11g_mahalanobis1936_innovation_gate",
            _qa11g_overrides(
                algorithm="qa11g_mahalanobis1936_innovation_gate_EKF",
                family="mahalanobis_gate",
                k0=1.5,
                k1=3.5,
                gain=1.2,
                reject_extreme=True,
            ),
        ),
        "qa11g_mehra1970_covariance_matching_EKF": _qa11g_spec(
            "qa11g_mehra1970_covariance_matching_EKF",
            "qa11g_mehra1970_covariance_matching",
            _qa11g_overrides(
                algorithm="qa11g_mehra1970_covariance_matching_EKF",
                family="covariance_matching",
                k0=1.2,
                k1=4.0,
                gain=0.6,
            ),
        ),
        "qa11g_huber1964_m_estimator_EKF": _qa11g_spec(
            "qa11g_huber1964_m_estimator_EKF",
            "qa11g_huber1964_m_estimator",
            _qa11g_overrides(
                algorithm="qa11g_huber1964_m_estimator_EKF",
                family="huber",
                c=1.5,
            ),
        ),
        "qa11g_yang2002_igg3_equiv_weight_EKF": _qa11g_spec(
            "qa11g_yang2002_igg3_equiv_weight_EKF",
            "qa11g_yang2002_igg3_equiv_weight",
            _qa11g_overrides(
                algorithm="qa11g_yang2002_igg3_equiv_weight_EKF",
                family="igg3",
                k0=1.5,
                k1=3.0,
            ),
        ),
        "qa11g_wang2020_tc_gnss_ins_fde_EKF": _qa11g_spec(
            "qa11g_wang2020_tc_gnss_ins_fde_EKF",
            "qa11g_wang2020_tc_gnss_ins_fde",
            _qa11g_overrides(
                algorithm="qa11g_wang2020_tc_gnss_ins_fde_EKF",
                family="mahalanobis_gate",
                k0=1.5,
                k1=3.0,
                gain=1.4,
                reject_extreme=True,
            ),
        ),
        "qa11g_yan2021_irakf_solution_state_EKF": _qa11g_spec(
            "qa11g_yan2021_irakf_solution_state_EKF",
            "qa11g_yan2021_irakf_solution_state",
            _qa11g_overrides(
                algorithm="qa11g_yan2021_irakf_solution_state_EKF",
                family="covariance_matching",
                k0=1.2,
                k1=4.0,
                gain=0.9,
                extra=_qa11e_source_only("receiver_position"),
            ),
        ),
        "qa11g_sun2022_dual_w_test_EKF": _qa11g_spec(
            "qa11g_sun2022_dual_w_test_EKF",
            "qa11g_sun2022_dual_w_test",
            _qa11g_overrides(
                algorithm="qa11g_sun2022_dual_w_test_EKF",
                family="mahalanobis_gate",
                k0=1.5,
                k1=3.0,
                gain=1.3,
                reject_extreme=True,
            ),
        ),
        "qa11g_yin2023_improved_R_rakf_EKF": _qa11g_spec(
            "qa11g_yin2023_improved_R_rakf_EKF",
            "qa11g_yin2023_improved_R_rakf",
            _qa11g_overrides(
                algorithm="qa11g_yin2023_improved_R_rakf_EKF",
                family="covariance_matching",
                k0=1.0,
                k1=4.0,
                gain=1.0,
            ),
        ),
        "qa11g_chen2025_fading_factor_arkf_EKF": _qa11g_spec(
            "qa11g_chen2025_fading_factor_arkf_EKF",
            "qa11g_chen2025_fading_factor_arkf",
            _qa11g_overrides(
                algorithm="qa11g_chen2025_fading_factor_arkf_EKF",
                family="covariance_matching",
                k0=1.0,
                k1=3.5,
                gain=1.5,
            ),
        ),
    }
)


def repo_to_wsl(path: str | Path) -> str:
    text = str(path)
    if re.match(r"^[A-Za-z]:", text):
        return f"/mnt/{text[0].lower()}{text[2:].replace(chr(92), '/')}"
    return text.replace(chr(92), "/")


def running_inside_wsl() -> bool:
    return Path("/proc/sys/kernel/osrelease").exists() and (
        "microsoft" in Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore").lower()
    )


def read_json(path: str | Path, default: Any = None) -> Any:
    source = Path(path)
    if not source.exists():
        return default
    try:
        return json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def find_base_config(workspace_root: Path) -> Path | None:
    return first_existing([workspace_root / rel for rel in BASE_CONFIG_CANDIDATES])


def parse_yaml_like(path: Path) -> dict[str, str]:
    kv: dict[str, str] = {}
    if not path.exists():
        return kv
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        kv[key.strip()] = value
    return kv


def load_base_config_values(workspace_root: Path) -> tuple[dict[str, str], Path | None]:
    base = find_base_config(workspace_root)
    values = parse_yaml_like(base) if base else {}
    return values, base


def resolve_port_core_executable(workspace_root: Path, data_paths_local: Path | None = None) -> dict[str, Any]:
    env_value = os.environ.get("LEGSA_PORT_CORE_EXE")
    candidates: list[str] = []
    if env_value:
        candidates.append(env_value)
    workspace_binary = workspace_root / "build" / "cpp" / "legsa_v23_port_core_demo"
    candidates.append(repo_to_wsl(workspace_binary))
    candidates.append(str(workspace_binary))
    local_doc = data_paths_local or workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    if local_doc.exists():
        text = local_doc.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"<WSL_ALGO_REPO>\s*\n([^\n`]+)", text)
        if match:
            wsl_repo = match.group(1).strip().rstrip("/")
            if wsl_repo.startswith("/"):
                candidates.append(f"{wsl_repo}/build/cpp/legsa_v23_port_core_demo")
            else:
                candidates.append(str(Path(wsl_repo) / "build" / "cpp" / "legsa_v23_port_core_demo"))

    probe_rows = []
    selected = None
    in_wsl = running_inside_wsl()
    for item in dict.fromkeys(candidates):
        if item.startswith("/"):
            probe_cmd = f"test -x {shlex.quote(item)}"
            if in_wsl:
                check = subprocess.run(["bash", "-lc", probe_cmd], check=False)
            else:
                check = subprocess.run(["wsl", "bash", "-lc", probe_cmd], check=False)
            exists = check.returncode == 0
        else:
            exists = Path(item).exists()
        probe_rows.append({"path": item, "exists": exists})
        if exists and selected is None:
            selected = item
    return {
        "runner_id": "legsa_v23_port_core_demo",
        "selected_path": selected,
        "exists": selected is not None,
        "candidate_paths": probe_rows,
        "supports_config_output_dir": selected is not None,
        "formal_runner_surface": "legsa_v23_port_core_demo --config <path> --output-dir <dir>",
    }


def validate_algorithm_inputs(workspace_root: Path, algorithm: str, base_values: dict[str, str]) -> list[str]:
    spec = ALGORITHM_SPECS[algorithm]
    missing: list[str] = []
    if not base_values.get("imupath"):
        missing.append("imupath from locked clean replay config")
    if not base_values.get("gnsspath"):
        missing.append("gnsspath from locked clean replay config")
    if spec.component_flags["raw_doppler"] and not (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]).exists():
        missing.append(str(REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"]))
    if spec.component_flags["go2_joint"]:
        for key in ["go2_attitude", "go2_horizontal_velocity", "go2_joint"]:
            if not (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS[key]).exists():
                missing.append(str(REPO_RELATIVE_REQUIRED_INPUTS[key]))
    if spec.component_flags["feedback"] and not (workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]).exists():
        missing.append(str(REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"]))
    return missing


def _base_config_lines(base_values: dict[str, str], output_dir_wsl: str) -> list[str]:
    def value(key: str, fallback: str) -> str:
        return base_values.get(key, fallback)

    return [
        "run_label: N4H4R3_clean_replay",
        f'imupath: "{value("imupath", "")}"',
        f'gnsspath: "{value("gnsspath", "")}"',
        f'outputpath: "{output_dir_wsl}"',
        "clean_input_provenance_label: clean_status_yaw_no_synthetic_noise",
        "config_policy_evidence_status: n9b1f_locked_normal_runtime_config",
        "imudatalen: 7",
        "imudatarate: 500",
        "starttime: 66.0",
        "endtime: 340.0",
        f"initpos: {value('initpos', '[ 39.98482973, 116.34312609, 41.80208107 ]')}",
        f"initvel: {value('initvel', '[ 0.0, 0.0, 0.0 ]')}",
        f"initatt: {value('initatt', '[ 0.0, 0.0, 0.688505 ]')}",
        f"initgyrbias: {value('initgyrbias', '[ 0.0, 0.0, 0.0 ]')}",
        f"initaccbias: {value('initaccbias', '[ 0.0, 0.0, 0.0 ]')}",
        f"initgyrscale: {value('initgyrscale', '[ 0.0, 0.0, 0.0 ]')}",
        f"initaccscale: {value('initaccscale', '[ 0.0, 0.0, 0.0 ]')}",
        f"initposstd: {value('initposstd', '[ 10.0, 10.0, 10.0 ]')}",
        f"initvelstd: {value('initvelstd', '[ 1.0, 1.0, 1.0 ]')}",
        f"initattstd: {value('initattstd', '[ 2.0, 2.0, 2.0 ]')}",
        f"arw: {value('arw', '[0.985, 0.985, 0.985]')}",
        f"vrw: {value('vrw', '[0.077, 0.077, 0.077]')}",
        f"gbstd: {value('gbstd', '[9.38, 9.38, 9.38]')}",
        f"abstd: {value('abstd', '[77.8, 77.8, 77.8]')}",
        f"gsstd: {value('gsstd', '[0.0, 0.0, 0.0]')}",
        f"asstd: {value('asstd', '[0.0, 0.0, 0.0]')}",
        "corrtime: 1.0",
        f"antlever: {value('antlever', '[ 0.0, 0.0, -0.25 ]')}",
        "initbgstd: [9.38, 9.38, 9.38]",
        "initbastd: [77.8, 77.8, 77.8]",
        "initsgstd: [0.0, 0.0, 0.0]",
        "initsastd: [0.0, 0.0, 0.0]",
    ]


def build_algorithm_config_text(workspace_root: Path, algorithm: str, output_dir: Path, base_values: dict[str, str]) -> str:
    spec = ALGORITHM_SPECS[algorithm]
    output_dir_wsl = repo_to_wsl(output_dir)
    raw_path = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["raw_doppler"])
    go2_attitude = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_attitude"])
    go2_velocity = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_horizontal_velocity"])
    go2_joint = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["go2_joint"])
    feedback = repo_to_wsl(workspace_root / REPO_RELATIVE_REQUIRED_INPUTS["selected_feedback"])
    qa_enabled = spec.algorithm == "LegSA_QA_Fallback_EKF"

    lines = _base_config_lines(base_values, output_dir_wsl)
    lines.extend(
        [
            "",
            "# N9B1F runtime-only formal LegSA runner config.",
            f"algorithm_id: {spec.algorithm}",
            f"algorithm_role: {spec.role}",
            f"ablation_variant: {spec.ablation_variant}",
            f"qa_passive_logging_enabled: {str(qa_enabled).lower()}",
            f"enable_qa_fallback: {str(qa_enabled).lower()}",
            f"qa_active_mode: {str(qa_enabled).lower()}",
            "qa_expected_a1_baseline_m: 0.5",
            "qa_a1_baseline_tolerance_m: 0.35",
            "qa_a1_min_valid_ratio: 0.6",
            "qa_a1_yaw_std_degraded_deg: 3.0",
            "qa_a1_yaw_std_invalid_deg: 10.0",
            "qa_a1_yaw_residual_degraded_deg: 6.0",
            "qa_a1_yaw_residual_invalid_deg: 15.0",
            "qa_a1_yaw_jump_invalid_deg: 20.0",
            "qa_gnss_pos_std_h_degraded_m: 3.0",
            "qa_gnss_pos_std_u_degraded_m: 5.0",
            "qa_gnss_pos_std_h_invalid_m: 15.0",
            "qa_gnss_pos_std_u_invalid_m: 25.0",
            "qa_raw_doppler_min_count: 5",
            "qa_recovery_required_consecutive_a1: 3",
            "qa_recovery_yaw_residual_gate_deg: 8.0",
            "qa_recovery_yaw_jump_gate_deg: 12.0",
            "qa_recovery_initial_yaw_r_scale: 6.0",
            "qa_recovery_max_yaw_correction_deg: 1.0",
            "qa_s1_yaw_r_scale: 2.0",
            "qa_s3_gnss_pos_r_scale: 9.0",
            "qa_s4_gnss_pos_r_scale: 25.0",
            "qa_a1_relpos_diff_valid_default: false",
            "qa_a1_baseline_m_default: 0.0",
            "qa_a1_baseline_default_available: false",
            "qa_a1_valid_ratio_default: 0.0",
            "qa_a1_valid_ratio_default_available: false",
            "qa_a1_quality_source: explicit_quality_missing_reject_yaw",
            f"active_fgo_backend_available: {str(spec.active_fgo_backend_available).lower()}",
            f"solver_execution_allowed: {str(spec.solver_execution_allowed).lower()}",
            f"complete_nine_factor_FGO_claim: {str(spec.complete_nine_factor_fgo_claim).lower()}",
            "enable_receiver_velocity_update: true",
            "receiver_velocity_stress_mode: none",
            "receiver_velocity_std_scale: 1.0",
            "receiver_velocity_outage_start_sec: 0.0",
            "receiver_velocity_outage_duration_sec: 0.0",
            "receiver_velocity_additive_noise_std_mps: 0.0",
            "receiver_velocity_additive_noise_seed: 20260510",
            f"enable_raw_doppler: {str(spec.component_flags['raw_doppler']).lower()}",
            f'raw_doppler_factor_path: "{raw_path if spec.component_flags["raw_doppler"] else ""}"',
            "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER",
            "raw_doppler_time_tolerance_sec: 0.08",
            "raw_doppler_min_sat: 5",
            "raw_doppler_residual_gate_mps: 3.0",
            "raw_doppler_R_scale: 1.0",
            "raw_doppler_mode: doppler_ls_velocity",
            f"enable_source_aware_weighting: {str(spec.component_flags['source_aware']).lower()}",
            "source_aware_policy_version: n6b_conservative_innovation_covariance",
            "source_aware_mode: lsim_oim",
            "source_aware_use_innovation_covariance: true",
            "source_aware_deadband_normalized: 1.5",
            "source_aware_moderate_normalized: 2.5",
            "source_aware_strong_normalized: 4.0",
            "source_aware_receiver_position_cap: 5.0",
            "source_aware_receiver_velocity_cap: 8.0",
            "source_aware_dual_yaw_cap: 10.0",
            "source_aware_raw_doppler_cap: 15.0",
            "source_aware_go2_attitude_cap: 10.0",
            "source_aware_go2_horizontal_velocity_cap: 10.0",
            "source_aware_global_cap: 25.0",
            "source_aware_max_R_scale: 25.0",
            "source_aware_reject_extreme: false",
            "source_aware_no_R_shrink: true",
            f"source_aware_trace_enabled: {str(spec.component_flags['source_aware']).lower()}",
            "source_aware_enable_rolling_innovation_baseline: true",
            "source_aware_rolling_window_size: 31",
            "source_aware_rolling_mad_floor: 0.5",
            f"source_aware_go2_attitude_roll_pitch_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_attitude_roll_pitch_lsim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_attitude_roll_pitch_oim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_horizontal_velocity_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_horizontal_velocity_lsim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"source_aware_go2_horizontal_velocity_oim_enabled: {str(spec.component_flags['go2_joint']).lower()}",
            f"enable_go2_attitude_weak_prior: {str(spec.component_flags['go2_joint']).lower()}",
            f'go2_attitude_prior_path: "{go2_attitude if spec.component_flags["go2_joint"] else ""}"',
            "go2_attitude_prior_time_tolerance_sec: 0.02",
            "go2_attitude_prior_std_roll_deg: 1.6",
            "go2_attitude_prior_std_pitch_deg: 1.6",
            "go2_attitude_prior_sourceaware: true",
            "go2_attitude_prior_diagnostic_only: false",
            f"enable_go2_horizontal_velocity_prior: {str(spec.component_flags['go2_joint']).lower()}",
            f'go2_horizontal_velocity_prior_path: "{go2_velocity if spec.component_flags["go2_joint"] else ""}"',
            "go2_horizontal_velocity_prior_std_scale: 1.0",
            "go2_horizontal_velocity_prior_vertical_disabled: true",
            "go2_horizontal_velocity_prior_source_aware_enabled: true",
            "go2_horizontal_velocity_prior_mode: horizontal_2d",
            "go2_horizontal_velocity_strength_policy: n7c6_hv1",
            f"enable_go2_proprioceptive_joint_factor: {str(spec.component_flags['go2_joint']).lower()}",
            f'go2_proprioceptive_joint_factor_path: "{go2_joint if spec.component_flags["go2_joint"] else ""}"',
            "go2_proprioceptive_joint_factor_mode: sequential_equivalent",
            "go2_proprioceptive_joint_factor_policy: joint_rp1p6deg_hv1p0",
            "go2_proprioceptive_source_aware_enabled: true",
            "enable_go2_velocity_prior_diagnostic: false",
            'go2_velocity_prior_diagnostic_path: ""',
            "go2_position_prior_enabled: false",
            "go2_velocity_prior_enabled: false",
            "go2_yaw_prior_enabled: false",
            "go2_vertical_velocity_prior_enabled: false",
            "enable_go2_yaw_rate_prior_diagnostic: false",
            'go2_yaw_rate_prior_diagnostic_path: ""',
            f"enable_fgo_feedback: {str(spec.component_flags['feedback']).lower()}",
            f'fgo_feedback_path: "{feedback if spec.component_flags["feedback"] else ""}"',
            "fgo_feedback_mode: pseudo_measurement",
            "fgo_feedback_position_enabled: false",
            f"fgo_feedback_velocity_enabled: {str(spec.component_flags['feedback']).lower()}",
            f"fgo_feedback_attitude_enabled: {str(spec.component_flags['feedback']).lower()}",
            "fgo_feedback_covariance_scale: 1.0",
            "fgo_feedback_max_position_correction_m: 6.0",
            "fgo_feedback_max_velocity_correction_mps: 0.5",
            "fgo_feedback_max_attitude_correction_deg: 4.0",
            "fgo_feedback_min_interval_s: 0.5",
            "fgo_feedback_no_future_data_required: true",
            "diagnostic_only: false",
            "diagnostic_stress_only: false",
            "proposed_factor_claim: false",
            "paper_performance_claim: false",
            "no_outperform_final_v23_claim: true",
            "trace_solver_input: false",
            "final_v23_output_solver_input: false",
            "output_only_correction: false",
            "bad_epoch_deletion_for_metric: false",
            "fgo: false",
        ]
    )
    if spec.config_overrides:
        pending = dict(spec.config_overrides)
        rewritten: list[str] = []
        for line in lines:
            key = line.split(":", 1)[0].strip() if ":" in line else ""
            if key in pending:
                rewritten.append(f"{key}: {pending.pop(key)}")
            else:
                rewritten.append(line)
        for key in sorted(pending):
            rewritten.append(f"{key}: {pending[key]}")
        lines = rewritten
    return "\n".join(lines) + "\n"


def write_algorithm_config(workspace_root: Path, algorithm: str, config_path: Path, output_dir: Path) -> dict[str, Any]:
    base_values, base_path = load_base_config_values(workspace_root)
    missing = validate_algorithm_inputs(workspace_root, algorithm, base_values)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(build_algorithm_config_text(workspace_root, algorithm, output_dir, base_values), encoding="utf-8")
    return {
        "algorithm": algorithm,
        "config_path": str(config_path),
        "config_path_wsl": repo_to_wsl(config_path),
        "base_config_path": str(base_path) if base_path else None,
        "missing_inputs": missing,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def append_case_level_overrides(config_path: Path, overrides: dict[str, str | None]) -> None:
    """Append explicit case-level input overrides to a generated runtime config."""
    clean = {key: value for key, value in overrides.items() if value not in {None, ""}}
    if not clean:
        return
    lines = ["", "# Case-level N9B input overrides."]
    for key, value in sorted(clean.items()):
        lines.append(f'{key}: "{str(value)}"')
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_solver_command_record(
    algorithm: str,
    runtime_config: str | Path,
    output_dir: str | Path,
    *,
    workspace_root: Path,
    port_core_exe: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    probe = resolve_port_core_executable(workspace_root)
    exe = port_core_exe or probe.get("selected_path") or "legsa_v23_port_core_demo"
    command = [exe, "--config", repo_to_wsl(runtime_config), "--output-dir", repo_to_wsl(output_dir)]
    return {
        "algorithm": algorithm,
        "command": command,
        "runner_surface": "legsa_v23_port_core_demo --config <runtime_config> --output-dir <output_dir>",
        "runtime_config": str(runtime_config),
        "runtime_config_wsl": repo_to_wsl(runtime_config),
        "output_dir": str(output_dir),
        "output_dir_wsl": repo_to_wsl(output_dir),
        "runner_probe": probe,
        "dry_run": dry_run,
        "executed_solver": False if dry_run else None,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "normal_parity_mode": False,
        "future_solver_entry": False,
    }


def run_formal_algorithm(
    workspace_root: Path,
    algorithm: str,
    output_dir: Path,
    *,
    port_core_exe: str | None = None,
    dry_run: bool = False,
    runtime_config: Path | None = None,
    case_overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    if algorithm not in ALGORITHM_SPECS:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if runtime_config:
        runtime_config = Path(runtime_config)
        clean_overrides = {key: value for key, value in (case_overrides or {}).items() if value not in {None, ""}}
        core_overrides = {
            "imupath": clean_overrides.get("imu_source_override"),
            "gnsspath": clean_overrides.get("gnss_input_override"),
            "outputpath": repo_to_wsl(output_dir),
            "fgo_feedback_path": clean_overrides.get("feedback_input_override"),
        }
        clean_core_overrides = {key: value for key, value in core_overrides.items() if value not in {None, ""}}
        effective_config = output_dir / "config" / "runtime_config.yaml"
        effective_config.parent.mkdir(parents=True, exist_ok=True)
        if runtime_config.exists():
            effective_config.write_text(runtime_config.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        else:
            effective_config.write_text("", encoding="utf-8")
        append_case_level_overrides(effective_config, clean_core_overrides)
        append_case_level_overrides(effective_config, clean_overrides)
        config_info = {
            "algorithm": algorithm,
            "config_path": str(effective_config),
            "config_path_wsl": repo_to_wsl(effective_config),
            "base_config_path": str(runtime_config),
            "missing_inputs": [],
            "case_overrides": clean_overrides,
            "core_config_overrides": clean_core_overrides,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "case_level_runtime_config": True,
            "source_runtime_config_copied": True,
        }
    else:
        config_info = write_algorithm_config(workspace_root, algorithm, output_dir / "config" / "runtime_config.yaml", output_dir)
        append_case_level_overrides(Path(config_info["config_path"]), case_overrides or {})
    spec = ALGORITHM_SPECS[algorithm]
    if not dry_run and not spec.solver_execution_allowed:
        return {
            "algorithm": algorithm,
            "run_status": "blocked",
            "blocked_reason": "active nine-factor FGO backend unavailable for this phase-1 candidate",
            "config": config_info,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "complete_nine_factor_FGO_claim": False,
        }
    probe = resolve_port_core_executable(workspace_root)
    exe = port_core_exe or probe.get("selected_path")
    if not exe:
        return {
            "algorithm": algorithm,
            "run_status": "blocked",
            "blocked_reason": "legsa_v23_port_core_demo executable missing",
            "config": config_info,
            "runner_probe": probe,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
    command_record = build_solver_command_record(
        algorithm,
        config_info["config_path"],
        output_dir,
        workspace_root=workspace_root,
        port_core_exe=exe,
        dry_run=dry_run,
    )
    if case_overrides:
        command_record["case_overrides"] = {key: value for key, value in case_overrides.items() if value not in {None, ""}}
    command = command_record["command"]
    write_json(output_dir / "solver_command.json", command_record)
    write_json(
        output_dir / "source_role.json",
        {
            "algorithm": algorithm,
            "trace_role": "evaluation_only_not_solver_input",
            "final_v23_role": "reference_only_not_solver_input",
            "runner": "legsa_v23_port_core_demo",
        },
    )
    write_json(
        output_dir / "output_lineage.json",
        {
            "algorithm": algorithm,
            "runner": "legsa_v23_port_core_demo",
            "config_path": str(config_info["config_path"]),
            "output_dir": str(output_dir),
            "diagnostic_generic_filter_core": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
        },
    )
    if config_info["missing_inputs"]:
        return {
            "algorithm": algorithm,
            "run_status": "blocked",
            "blocked_reason": "missing locked normal inputs",
            "missing_inputs": config_info["missing_inputs"],
            "config": config_info,
            "runner_probe": probe,
            "command": command_record,
        }
    if dry_run:
        return {
            "algorithm": algorithm,
            "run_status": "dry_run",
            "returncode": None,
            "config": config_info,
            "runner_probe": probe,
            "command": command_record,
        }
    shell_argv = ["bash", "-lc", shlex.join(command)] if running_inside_wsl() else ["wsl", "bash", "-lc", shlex.join(command)]
    completed = subprocess.run(
        shell_argv,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    (output_dir / "logs").mkdir(exist_ok=True)
    (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    manifest = read_json(output_dir / "RUN_MANIFEST.json", {})
    return {
        "algorithm": algorithm,
        "run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "config": config_info,
        "runner_probe": probe,
        "command": command_record,
        "manifest": manifest,
        "outputs": {
            name: str(output_dir / name)
            for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
            if (output_dir / name).exists()
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algorithm", choices=FORMAL_ALGORITHMS, required=True)
    parser.add_argument("--case-id", default="normal_condition")
    parser.add_argument("--imu-source", default=None)
    parser.add_argument("--gnss-input", default=None)
    parser.add_argument("--receiver-input", default=None)
    parser.add_argument("--velocity-input", default=None)
    parser.add_argument("--yaw-input", default=None)
    parser.add_argument("--raw-doppler-input", default=None)
    parser.add_argument("--go2-input", default=None)
    parser.add_argument("--feedback-input", default=None)
    parser.add_argument("--source-aware-input", default=None)
    parser.add_argument("--config-json", "--runtime-config", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-epochs", default=None)
    parser.add_argument("--normal-parity-mode", action="store_true")
    parser.add_argument("--workspace-root", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_root = Path(args.workspace_root).resolve() if args.workspace_root else Path.cwd().resolve()
    result = run_formal_algorithm(
        workspace_root,
        args.algorithm,
        Path(args.output_dir),
        dry_run=args.dry_run,
        runtime_config=Path(args.config_json) if args.config_json else None,
        case_overrides={
            "case_id": args.case_id,
            "imu_source_override": args.imu_source,
            "gnss_input_override": args.gnss_input,
            "receiver_input_override": args.receiver_input,
            "velocity_input_override": args.velocity_input,
            "yaw_input_override": args.yaw_input,
            "raw_doppler_input_override": args.raw_doppler_input,
            "go2_input_override": args.go2_input,
            "feedback_input_override": args.feedback_input,
            "source_aware_input_override": args.source_aware_input,
            "max_epochs": args.max_epochs,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result.get("run_status") in {"completed", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
