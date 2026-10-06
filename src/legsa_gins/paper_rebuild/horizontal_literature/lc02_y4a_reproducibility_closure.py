"""Bounded Yin-2023 Y4A source closure and guarded draft-publication audit.

This module contains deterministic small-matrix reproducibility oracles only.
It has no navigation mechanization, Kalman-filter runner, BY2 reader, provider,
evaluator, trace/reference reader, or comparison-method dependency.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from pypdf import PdfReader

from . import lc02_y0_y3_audit as y0_y3


METHOD_ID = "LC02_YIN2023_RAEKF"
START_HEAD = "5805a7cecb1b6d72c7bb16264b460ab353dd6a25"
AUTHORIZED_COMMIT_SUBJECT = "Close Yin 2023 RAEKF reproduction semantics"
TERMINAL_STATUS = "NO_GO_LC02_YIN2023_RAEKF_AS_FORMAL_PRIMARY"
ORIGINAL_MANIFEST_SHA256 = "2a20c89f0fec71c241cc736680f78991e1fff9cc086c17e5fb644fab2e2e239f"
INITIAL_DRAFT_Y4A_MANIFEST_SHA256 = "4798a559ccf95dd357fe4eb37f7610069e2576c3a864c926b5be2cd74203891a"
FIRST_CORRECTION_Y4A_MANIFEST_SHA256 = "2f0cd31647f83bc11ff5810ef7927cea9cd9704ef4d7195d67efa773e35ca1a8"
SECOND_CORRECTION_Y4A_MANIFEST_SHA256 = "bbc2b34d2f31767e778b00dea6f8ab4e491ab3cbc98dec5354ce79dadb4031b3"
THIRD_CORRECTION_Y4A_MANIFEST_SHA256 = "f073ed1d1964814683d10cf4a761a88b97408496109664adbbd9d566b8067ee6"
PRE_CORRECTION_Y4A_MANIFEST_SHA256 = THIRD_CORRECTION_Y4A_MANIFEST_SHA256
ORIGINAL_FILE_COUNT = 47
Y4A_APPEND_FILE_COUNT = 32
FINAL_STAGE_FILE_COUNT = 79
ORACLE_COUNT = 28
REQUIRED_ORACLE_IDS = frozenset(
    {
        "EKF_1D_UPDATE_IDENTITY",
        "EKF_3D_UPDATE_IDENTITY",
        "AKF_ALPHA_ONE_EQUALS_EKF",
        "IGGIII_INLIER_INFORMATION_NOMINAL",
        "IGGIII_MIDDLE_WEIGHT_FINITE_POSITIVE",
        "ZERO_WEIGHT_NO_UNIQUE_YIN_POLICY",
        "ZERO_WEIGHT_SCALAR_LIMIT",
        "ZERO_WEIGHT_DIAGONAL_ROW_OMISSION",
        "ZERO_WEIGHT_CORRELATED_PATH_DEPENDENCE",
        "EQ12_STATE_WEIGHTED_FUSION_EXACT",
        "EQ13_COVARIANCE_WEIGHTED_FUSION_EXACT",
        "NED_PERMUTATION_EQUIVARIANCE",
        "DIAGONAL_R_UNIT_EXPONENT_M2",
    }
)
ALLOWED_LZ_DECISIONS = frozenset(
    {
        "SOURCE_CLOSED_TYPOGRAPHICAL_ALIAS",
        "DISTINCT_SYMBOLS_WITH_CLOSED_RELATION",
        "UNRESOLVED",
    }
)
ALLOWED_AKF_DECISIONS = frozenset(
    {
        "PAPER_DIRECT_CLOSED",
        "CITED_STANDARD_COMPLETION_CLOSED",
        "MULTIPLE_PLAUSIBLE_COMPLETIONS",
        "UNRESOLVED",
    }
)
SCOPED_TEST_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src "
    "python3 -m pytest -q tests/paper_rebuild/test_lc02_yin2023_y4a.py"
)
COMBINED_TEST_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src "
    "python3 -m pytest -q tests/paper_rebuild/test_lc02_yin2023_y0_y3.py "
    "tests/paper_rebuild/test_lc02_yin2023_y4a.py"
)
FULL_TEST_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src "
    "python3 -m pytest -q tests/paper_rebuild"
)
EXPECTED_FULL_FAILURE_NODE_IDS = (
    "tests/paper_rebuild/test_horizontal_phase4_c00.py::"
    "test_preflight_hash_only_collision_and_paper_closure_when_available",
    "tests/paper_rebuild/test_horizontal_phase5_c00.py::"
    "test_dirty_untracked_source_snapshot_is_hash_complete_and_explicit",
)
EXPECTED_DURABLE_VALIDATION = {
    "scoped": {
        "command": SCOPED_TEST_COMMAND,
        "result": "PASS_16_PASSED",
        "return_code": 0,
        "passed": 16,
        "failed": 0,
        "skipped": 0,
    },
    "combined_lc02": {
        "command": COMBINED_TEST_COMMAND,
        "result": "PASS_36_PASSED",
        "return_code": 0,
        "passed": 36,
        "failed": 0,
        "skipped": 0,
    },
    "full_paper_rebuild": {
        "command": FULL_TEST_COMMAND,
        "result": "EXPECTED_UNCHANGED_TWO_STALE_FAILURES_ONLY",
        "return_code": 1,
        "passed": 1082,
        "failed": 2,
        "skipped": 20,
        "new_failures": 0,
        "failure_node_ids": list(EXPECTED_FULL_FAILURE_NODE_IDS),
    },
}
ADMINISTRATIVE_VALIDATION_INVENTORY = {
    "original_files_content_read_for_integrity_count": 47,
    "original_structured_JSON_YAML_CSV_parsed_count": 36,
    "Y4A_structured_JSON_YAML_CSV_parsed_count": 22,
    "augmented_stage_structured_JSON_YAML_CSV_parsed_count": 58,
    "Y0_status_gate_documents_semantically_checked_count": 1,
    "Canonical_files_hash_read_only_count": 2,
    "authorized_frozen_Y0_Y3_input_contract_fact_reuse_count": 4,
    "new_frozen_Y0_Y3_scientific_content_open_count": 0,
    "old_performance_runtime_trace_fact_reuse_count": 0,
}
AUTHORIZED_FROZEN_INPUT_CONTRACT_FACT_REUSE = {
    "fact_count": 4,
    "facts": {
        "GNSS1_epoch_and_Q_identity": "1510/1510; Q=1",
        "PDOP_min": 1.13,
        "PDOP_max": 1.74,
        "per_axis_covariance_variation": True,
    },
    "old_performance_runtime_trace_reuse_count": 0,
}
SOURCE_ACCESS_COUNTS = {
    "public_author_upload_full_text_inspected_count": 4,
    "request_only_author_upload_metadata_inspected_count": 1,
}
Y4A_ROOT = "07_Y4A_REPRODUCIBILITY_CLOSURE"
NEW_REPORTS = frozenset(
    {
        "11_REPORT/LC02_Y4A_REPRODUCIBILITY_CLOSURE_REPORT.md",
        "11_REPORT/LC02_Y4A_STATUS.json",
        "11_REPORT/LC02_FORMAL_ADMISSION_DECISION.md",
    }
)
NO_GO_ONLY = frozenset(
    {
        f"{Y4A_ROOT}/06_ADMISSION_DECISION/LC02_YIN2023_NO_GO_REASON.md",
        f"{Y4A_ROOT}/06_ADMISSION_DECISION/LC02_NEXT_PAPER_SELECTION_REQUIREMENTS.md",
    }
)
SOURCE_FILES = {
    "CN117647251A.pdf": {
        "sha256": "83069a9fa7441468ade83c9295e8ab440b0942506229dfbbfc22382e76934edd",
        "bytes": 1_146_875,
        "pages": 21,
    },
    "yin2023_vor_28p.pdf": {
        "sha256": "b67f07908671bbda54ffd8a3981f7e365ff97f387698d2b558305044f11eec04",
        "bytes": 4_550_872,
        "pages": 28,
    },
    "yin2023_v2_24p.pdf": {
        "sha256": "198da0283cabddc97446bf9cf9138d8b7ee0b1d1a78f9bdbbe8265c711302f0c",
        "bytes": 21_097_265,
        "pages": 24,
    },
    "niu2022_rs14102449.pdf": {
        "sha256": "96b953d6ebd819a620948767c90cc78ad544efe8b00a5bf9ab9ae328bcdec487",
        "bytes": 13_374_059,
        "pages": 34,
    },
    "tcrtkins_13e8fa1_Fusion.cpp": {
        "sha256": "df4cb2783fdfa07932e25a726739c2716c112ac607e72dd9411e42b7fa2a43df",
        "bytes": 37_929,
    },
    "tcrtkins_13e8fa1_TC_conf.ini": {
        "sha256": "6694285358c6cf3bb84596f0e9945caa0e7e0c63f0a04a632d4624beb3337758",
        "bytes": 5_228,
    },
    "yin2023_peer_review_author_response_jina.md": {
        "sha256": "46c6bd33f49aab98ea0b9333f1ddce3298991ae55422ed440806a7d2dca313ce",
        "bytes": 18_305,
    },
    "yin2023_official_article_jina.md": {
        "sha256": "26784270d28e208184610db5bfcb1dadae4c810885c7f5d52f5240e5acb73426",
        "bytes": 104_971,
    },
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def authorized_git_state(repo: Path) -> str:
    """Accept the precommit anchor or its exact authorized one-commit descendant."""

    head = git_head(repo)
    if head == START_HEAD:
        return "PRECOMMIT_START_HEAD"
    parents = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", head],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().split()
    subject = subprocess.run(
        ["git", "show", "-s", "--format=%s", head],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.rstrip("\n")
    if len(parents) == 2 and parents[1] == START_HEAD and subject == AUTHORIZED_COMMIT_SUBJECT:
        return "AUTHORIZED_ONE_COMMIT_DESCENDANT"
    raise ValueError("Git state is neither the precommit anchor nor its exact authorized descendant")


def default_stage_root(repo: Path) -> Path:
    local_paths = repo / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
    values = y0_y3.load_local_paths(local_paths)
    return Path(values["clean_root"]) / (
        "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/"
        "08_LC02_YIN2023_RAEKF"
    )


def _format_float(value: float) -> str:
    return format(float(value), ".12g")


def iggiii_weight(value: float, k0: float = 1.15, k1: float = 4.45) -> float:
    """Yin Eq. (10), used only as a scalar algebra oracle."""

    magnitude = abs(float(value))
    if magnitude <= k0:
        return 1.0
    if magnitude <= k1:
        return (k0 / magnitude) * ((k1 - magnitude) / (k1 - k0)) ** 3
    return 0.0


def _oracle_row(
    oracle_id: str,
    claim: str,
    observed: float,
    expected: str,
    tolerance: float,
    passed: bool,
    meaning: str,
) -> dict[str, str]:
    return {
        "oracle_id": oracle_id,
        "claim": claim,
        "observed": _format_float(observed),
        "expected": expected,
        "tolerance": _format_float(tolerance),
        "passed": str(bool(passed)).lower(),
        "meaning": meaning,
    }


def linear_oracle_rows() -> list[dict[str, str]]:
    """Return deterministic algebra checks; passing never proves source uniqueness."""

    rows: list[dict[str, str]] = []
    residual = np.array([4.0, 2.0])
    prior = np.diag([4.0, 9.0, 16.0])
    design = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    measurement = np.diag([1.0, 4.0])
    innovation_covariance = design @ prior @ design.T + measurement
    state_trace_stat = math.sqrt(float(residual @ residual) / float(np.trace(prior)))
    innovation_trace_stat = math.sqrt(
        float(residual @ residual) / float(np.trace(innovation_covariance))
    )
    state_alpha = min(1.0, 1.0 / state_trace_stat)
    innovation_alpha = min(1.0, 1.0 / innovation_trace_stat)
    rows.extend(
        [
            _oracle_row(
                "AKF_DENOMINATOR_STATE_TRACE",
                "printed state-trace statistic",
                state_trace_stat,
                "sqrt(20/29)",
                1e-12,
                abs(state_trace_stat - math.sqrt(20.0 / 29.0)) < 1e-12,
                "One literal reading of Yin Eq. (6).",
            ),
            _oracle_row(
                "AKF_DENOMINATOR_INNOVATION_TRACE",
                "measurement-space alternative statistic",
                innovation_trace_stat,
                "sqrt(20/18)",
                1e-12,
                abs(innovation_trace_stat - math.sqrt(20.0 / 18.0)) < 1e-12,
                "A dimensionally compatible completion gives a different statistic.",
            ),
            _oracle_row(
                "AKF_ALPHA_BRANCH_DIVERGENCE",
                "candidate denominators select different alpha",
                abs(state_alpha - innovation_alpha),
                ">0.05",
                0.0,
                abs(state_alpha - innovation_alpha) > 0.05,
                "The source omission is algorithmically material.",
            ),
        ]
    )

    standardized_by_r = 3.0 / math.sqrt(0.25)
    standardized_by_s = 3.0 / math.sqrt(4.0)
    rows.extend(
        [
            _oracle_row(
                "STANDARDIZER_R_DIAGONAL",
                "measurement-noise denominator",
                standardized_by_r,
                "6",
                1e-12,
                abs(standardized_by_r - 6.0) < 1e-12,
                "This candidate rejects the component under Yin thresholds.",
            ),
            _oracle_row(
                "STANDARDIZER_S_DIAGONAL",
                "innovation-covariance denominator",
                standardized_by_s,
                "1.5",
                1e-12,
                abs(standardized_by_s - 1.5) < 1e-12,
                "This cited-source candidate only downweights the same component.",
            ),
            _oracle_row(
                "STANDARDIZER_WEIGHT_DIVERGENCE",
                "R- and S-based standardizers yield different IGGIII decisions",
                abs(iggiii_weight(standardized_by_r) - iggiii_weight(standardized_by_s)),
                ">0",
                0.0,
                iggiii_weight(standardized_by_r) != iggiii_weight(standardized_by_s),
                "No numerical oracle can choose the missing source definition.",
            ),
            _oracle_row(
                "IGGIII_K0_CONTINUITY",
                "printed exponent-three weight equals one at k0",
                iggiii_weight(1.15),
                "1",
                1e-12,
                abs(iggiii_weight(1.15) - 1.0) < 1e-12,
                "Scalar Eq. (10) is executable at the lower boundary.",
            ),
            _oracle_row(
                "IGGIII_K1_ZERO",
                "printed exponent-three weight reaches zero at k1",
                iggiii_weight(4.45),
                "0",
                1e-12,
                abs(iggiii_weight(4.45)) < 1e-12,
                "The next printed inverse is undefined at this exact weight.",
            ),
        ]
    )

    covariance = np.array([[4.0, 1.2], [1.2, 1.0]])
    precision = np.linalg.inv(covariance)
    weights = np.diag([1.0, 0.3])
    left_weighted = weights @ precision
    root_weights = np.diag(np.sqrt(np.diag(weights)))
    symmetric_weighted = root_weights @ precision @ root_weights
    rows.extend(
        [
            _oracle_row(
                "IGGIII_LEFT_WEIGHT_NONSYMMETRY",
                "left multiplication of correlated precision is nonsymmetric",
                np.linalg.norm(left_weighted - left_weighted.T),
                ">0",
                0.0,
                np.linalg.norm(left_weighted - left_weighted.T) > 0.0,
                "The scalar per-component equation does not define a valid general matrix rule.",
            ),
            _oracle_row(
                "IGGIII_SYMMETRIC_SANDWICH_PSD",
                "square-root sandwich remains positive definite",
                float(np.min(np.linalg.eigvalsh(symmetric_weighted))),
                ">0",
                0.0,
                float(np.min(np.linalg.eigvalsh(symmetric_weighted))) > 0.0,
                "This is one defensible correlated completion, not uniquely Yin's.",
            ),
            _oracle_row(
                "IGGIII_MATRIX_COMPLETIONS_DIFFER",
                "left and symmetric completions differ",
                np.linalg.norm(left_weighted - symmetric_weighted),
                ">0",
                0.0,
                np.linalg.norm(left_weighted - symmetric_weighted) > 0.0,
                "Off-diagonal handling is algorithmically material.",
            ),
        ]
    )

    scalar_prior = 2.0
    scalar_r = 3.0
    epsilon = 1e-9
    scalar_gain = scalar_prior / (scalar_prior + scalar_r / epsilon)
    scalar_posterior = (1.0 - scalar_gain) * scalar_prior
    rows.append(
        _oracle_row(
            "ZERO_WEIGHT_SCALAR_LIMIT",
            "positive-weight limit approaches row omission",
            abs(scalar_posterior - scalar_prior),
            "<2e-9",
            2e-9,
            abs(scalar_posterior - scalar_prior) < 2e-9,
            "The limit is defined; direct inversion at weight zero is not.",
        )
    )

    state_prior = np.array([[2.0, 0.4], [0.4, 1.0]])
    identity = np.eye(2)
    diagonal_r = np.diag([0.5, 0.8])
    diagonal_effective = np.diag([0.5, 0.8 / epsilon])
    diagonal_gain = state_prior @ np.linalg.inv(state_prior + diagonal_effective)
    retained_design = np.array([[1.0, 0.0]])
    omitted_gain = (
        state_prior
        @ retained_design.T
        @ np.linalg.inv(retained_design @ state_prior @ retained_design.T + np.array([[0.5]]))
    )
    omitted_gain_full = np.column_stack([omitted_gain[:, 0], np.zeros(2)])
    rows.append(
        _oracle_row(
            "ZERO_WEIGHT_DIAGONAL_ROW_OMISSION",
            "diagonal infinite-variance limit equals omission",
            np.linalg.norm(diagonal_gain - omitted_gain_full),
            "<2e-9",
            2e-9,
            np.linalg.norm(diagonal_gain - omitted_gain_full) < 2e-9,
            "Equivalence holds only under the stated diagonal construction.",
        )
    )

    correlated_r = np.array([[1.0, 0.6], [0.6, 1.0]])
    inflation = np.diag([1.0, 1.0 / math.sqrt(epsilon)])
    correlated_effective = inflation @ correlated_r @ inflation
    correlated_gain = state_prior @ np.linalg.inv(state_prior + correlated_effective)
    correlated_omission_gain = (
        state_prior
        @ retained_design.T
        @ np.linalg.inv(retained_design @ state_prior @ retained_design.T + np.array([[1.0]]))
    )
    correlated_omission_full = np.column_stack(
        [correlated_omission_gain[:, 0], np.zeros(2)]
    )
    rows.append(
        _oracle_row(
            "ZERO_WEIGHT_CORRELATED_PATH_DEPENDENCE",
            "correlated inflation limit differs from direct row deletion",
            np.linalg.norm(correlated_gain - correlated_omission_full),
            ">1e-3",
            1e-3,
            np.linalg.norm(correlated_gain - correlated_omission_full) > 1e-3,
            "A zero-weight operation must be specified, not inferred from scalar notation.",
        )
    )

    adaptive_state = np.array([1.0, 0.0])
    robust_state = np.array([-1.0, 0.0])
    adaptive_covariance = identity
    robust_covariance = 4.0 * identity
    varpi = 0.85
    paper_covariance = varpi * adaptive_covariance + (1.0 - varpi) * robust_covariance
    independent_linear_covariance = (
        varpi**2 * adaptive_covariance + (1.0 - varpi) ** 2 * robust_covariance
    )
    difference = adaptive_state - robust_state
    mixture_covariance = (
        paper_covariance + varpi * (1.0 - varpi) * np.outer(difference, difference)
    )
    rows.extend(
        [
            _oracle_row(
                "RAEKF_PRINTED_FUSION_PSD",
                "printed convex covariance fusion is positive definite",
                float(np.min(np.linalg.eigvalsh(paper_covariance))),
                ">0",
                0.0,
                float(np.min(np.linalg.eigvalsh(paper_covariance))) > 0.0,
                "PSD does not establish the covariance's probabilistic interpretation.",
            ),
            _oracle_row(
                "RAEKF_INDEPENDENT_LINEAR_COVARIANCE_DIFFERS",
                "independent linear-combination covariance differs from Eq. (13)",
                np.linalg.norm(paper_covariance - independent_linear_covariance),
                ">0",
                0.0,
                np.linalg.norm(paper_covariance - independent_linear_covariance) > 0.0,
                "Cross-covariance assumptions are absent.",
            ),
            _oracle_row(
                "RAEKF_MIXTURE_COVARIANCE_DIFFERS",
                "mixture covariance with branch-mean spread differs from Eq. (13)",
                np.linalg.norm(paper_covariance - mixture_covariance),
                ">0",
                0.0,
                np.linalg.norm(paper_covariance - mixture_covariance) > 0.0,
                "Eq. (13) is executable but not a uniquely justified uncertainty law.",
            ),
        ]
    )

    predicted = np.array([0.5, -0.5])
    z_observation = np.array([1.0, 2.0])
    l_observation = np.array([1.2, 2.0])
    rows.append(
        _oracle_row(
            "L_Z_SYMBOL_NONIDENTITY",
            "different observation symbols can produce different innovations",
            np.linalg.norm((l_observation - predicted) - (z_observation - predicted)),
            ">0",
            0.0,
            np.linalg.norm((l_observation - predicted) - (z_observation - predicted)) > 0.0,
            "Only a source statement, not algebra, can authorize L_k=Z_k.",
        )
    )

    one_d_prior = 2.0
    one_d_r = 3.0
    one_d_x_minus = 1.0
    one_d_z = 4.0
    one_d_gain = one_d_prior / (one_d_prior + one_d_r)
    one_d_x_plus = one_d_x_minus + one_d_gain * (one_d_z - one_d_x_minus)
    one_d_p_plus = (1.0 - one_d_gain) * one_d_prior
    one_d_error = np.linalg.norm(
        np.array([one_d_gain - 0.4, one_d_x_plus - 2.2, one_d_p_plus - 1.2])
    )
    rows.append(
        _oracle_row(
            "EKF_1D_UPDATE_IDENTITY",
            "one-dimensional EKF gain, state, and covariance identity",
            one_d_error,
            "0",
            1e-12,
            one_d_error < 1e-12,
            "Standalone nominal EKF identity; no navigation data are used.",
        )
    )

    three_d_prior = np.diag([2.0, 3.0, 4.0])
    three_d_r = np.diag([0.5, 1.0, 2.0])
    three_d_x_minus = np.array([0.1, -0.2, 0.3])
    three_d_z = np.array([1.1, 1.8, -0.9])
    three_d_gain = three_d_prior @ np.linalg.inv(three_d_prior + three_d_r)
    three_d_x_plus = three_d_x_minus + three_d_gain @ (three_d_z - three_d_x_minus)
    three_d_p_plus = (np.eye(3) - three_d_gain) @ three_d_prior
    expected_gain = np.diag([0.8, 0.75, 2.0 / 3.0])
    expected_state = np.array([0.9, 1.3, -0.5])
    expected_covariance = np.diag([0.4, 0.75, 4.0 / 3.0])
    three_d_error = (
        np.linalg.norm(three_d_gain - expected_gain)
        + np.linalg.norm(three_d_x_plus - expected_state)
        + np.linalg.norm(three_d_p_plus - expected_covariance)
    )
    rows.append(
        _oracle_row(
            "EKF_3D_UPDATE_IDENTITY",
            "three-dimensional diagonal EKF update identity",
            three_d_error,
            "0",
            1e-12,
            three_d_error < 1e-12,
            "Verifies the nominal three-axis algebra independently of Yin policy choices.",
        )
    )

    alpha_one_gain = (three_d_prior / 1.0) @ np.linalg.inv(
        three_d_prior / 1.0 + three_d_r
    )
    alpha_one_state = three_d_x_minus + alpha_one_gain @ (three_d_z - three_d_x_minus)
    alpha_one_covariance = (1.0 / 1.0) * (np.eye(3) - alpha_one_gain) @ three_d_prior
    alpha_one_error = (
        np.linalg.norm(alpha_one_gain - three_d_gain)
        + np.linalg.norm(alpha_one_state - three_d_x_plus)
        + np.linalg.norm(alpha_one_covariance - three_d_p_plus)
    )
    rows.append(
        _oracle_row(
            "AKF_ALPHA_ONE_EQUALS_EKF",
            "Yin AKF equations reduce to EKF when alpha equals one",
            alpha_one_error,
            "0",
            1e-12,
            alpha_one_error < 1e-12,
            "This identity closes a printed special case, not the ambiguous alpha statistic.",
        )
    )

    nominal_r = np.diag([1.0, 2.0, 3.0])
    nominal_information = np.linalg.inv(nominal_r)
    inlier_weight = iggiii_weight(0.5)
    inlier_information_error = np.linalg.norm(
        inlier_weight * nominal_information - nominal_information
    )
    rows.append(
        _oracle_row(
            "IGGIII_INLIER_INFORMATION_NOMINAL",
            "declared PAPER_DERIVED conventional Eq.11 split preserves nominal information for an inlier",
            inlier_information_error,
            "0",
            1e-12,
            inlier_information_error < 1e-12,
            "Eq.10 Greek omega equals one PAPER_DIRECT; the author response says its weighting function enters Eq.11's Latin w multiplier, but mapping it to A_equivalent=omega*A_base remains an unselected PAPER_DERIVED candidate.",
        )
    )

    middle_weight = iggiii_weight(2.0)
    rows.append(
        _oracle_row(
            "IGGIII_MIDDLE_WEIGHT_FINITE_POSITIVE",
            "middle-band exponent-three scalar weight is finite and positive",
            middle_weight,
            "0<w<1",
            0.0,
            math.isfinite(middle_weight) and 0.0 < middle_weight < 1.0,
            "This does not define the missing general matrix construction.",
        )
    )
    printed_nonexecutable_singular_paths = (
        "PRINTED_ZERO_INFORMATION_THEN_REQUIRED_INVERSE",
    )
    executable_unselected_completions = (
        "ROW_OMISSION",
        "POSITIVE_INFINITE_VARIANCE_LIMIT",
    )
    rows.append(
        _oracle_row(
            "ZERO_WEIGHT_NO_UNIQUE_YIN_POLICY",
            "one printed singular path and at least two executable completions remain source-unselected",
            float(len(executable_unselected_completions)),
            ">=2_EXECUTABLE_COMPLETIONS_PLUS_1_NONEXECUTABLE_PRINTED_PATH",
            0.0,
            len(printed_nonexecutable_singular_paths) == 1
            and len(executable_unselected_completions) >= 2,
            "The printed zero-information inverse is non-executable; row omission and a positive infinite-variance limit are executable but unselected.",
        )
    )

    eq12_adaptive_state = np.array([1.0, 2.0])
    eq12_robust_state = np.array([-1.0, 4.0])
    expected_fused_state = np.array([0.7, 2.3])
    fused_state = varpi * eq12_adaptive_state + (1.0 - varpi) * eq12_robust_state
    state_fusion_error = np.linalg.norm(fused_state - expected_fused_state)
    rows.append(
        _oracle_row(
            "EQ12_STATE_WEIGHTED_FUSION_EXACT",
            "Eq.12 convex state fusion evaluates exactly",
            state_fusion_error,
            "0",
            1e-12,
            state_fusion_error < 1e-12,
            "The printed state-fusion equation is source-closed.",
        )
    )
    expected_fused_covariance = 1.45 * np.eye(2)
    covariance_fusion_error = np.linalg.norm(paper_covariance - expected_fused_covariance)
    rows.append(
        _oracle_row(
            "EQ13_COVARIANCE_WEIGHTED_FUSION_EXACT",
            "Eq.13 convex covariance fusion evaluates exactly",
            covariance_fusion_error,
            "0",
            1e-12,
            covariance_fusion_error < 1e-12,
            "Cross-covariance is an interpretation limit, not an ambiguity in executable Eq.13.",
        )
    )

    permutation = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
    permuted_prior = permutation @ three_d_prior @ permutation.T
    permuted_r = permutation @ three_d_r @ permutation.T
    permuted_x_minus = permutation @ three_d_x_minus
    permuted_z = permutation @ three_d_z
    permuted_gain = permuted_prior @ np.linalg.inv(permuted_prior + permuted_r)
    permuted_x_plus = permuted_x_minus + permuted_gain @ (permuted_z - permuted_x_minus)
    permuted_p_plus = (np.eye(3) - permuted_gain) @ permuted_prior
    permutation_error = (
        np.linalg.norm(permuted_x_plus - permutation @ three_d_x_plus)
        + np.linalg.norm(permuted_p_plus - permutation @ three_d_p_plus @ permutation.T)
    )
    rows.append(
        _oracle_row(
            "NED_PERMUTATION_EQUIVARIANCE",
            "diagonal three-axis update is equivariant under N/E/D permutation",
            permutation_error,
            "0",
            1e-12,
            permutation_error < 1e-12,
            "Axis ordering must be permuted consistently for state, covariance, and measurement.",
        )
    )
    pdop_unit_exponent = 0
    quality_factor_unit_exponent = 0
    axis_standard_deviation_unit_exponent = 1
    covariance_unit_exponent = (
        2 * pdop_unit_exponent
        + quality_factor_unit_exponent
        + 2 * axis_standard_deviation_unit_exponent
    )
    rows.append(
        _oracle_row(
            "DIAGONAL_R_UNIT_EXPONENT_M2",
            "computed unit exponent 2*PDOP(0)+Q(0)+2*r(1) equals square metres",
            float(covariance_unit_exponent),
            "2 (m^2)",
            0.0,
            covariance_unit_exponent == 2,
            "The diagonal improved-R entry retains covariance units m^2.",
        )
    )
    if len(rows) != ORACLE_COUNT or not REQUIRED_ORACLE_IDS.issubset(
        {row["oracle_id"] for row in rows}
    ):
        raise AssertionError("deterministic oracle registry is incomplete")
    return rows


def _read_oracle_csv(path: Path) -> list[dict[str, str]]:
    with path.open("rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _payload_roots(repo: Path) -> tuple[Path, Path]:
    base = Path("paper_rebuild/horizontal_literature/lc02_yin2023/y4a/stage_payload")
    return repo / "configs" / base, repo / "docs" / base


def payload_sources(repo: Path) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for root in _payload_roots(repo):
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"missing Y4A payload root: {root}")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"tracked Y4A payload symlink forbidden: {path}")
            if not path.is_file() and not path.is_dir():
                raise ValueError(f"tracked Y4A special entry forbidden: {path}")
            if not path.is_file():
                continue
            relative = str(path.relative_to(root))
            if relative in sources:
                raise ValueError(f"duplicate Y4A payload path: {relative}")
            sources[relative] = path
    expected = set(y0_y3._allowed_y4a_append_files())
    if set(sources) != expected:
        missing = sorted(expected.difference(sources))
        unexpected = sorted(set(sources).difference(expected))
        raise ValueError(f"Y4A payload mismatch; missing={missing}; unexpected={unexpected}")
    if len(sources) != Y4A_APPEND_FILE_COUNT:
        raise ValueError("Y4A payload count mismatch")
    return sources


def verify_source_cache(source_dir: Path) -> dict[str, dict[str, Any]]:
    if not source_dir.is_dir() or source_dir.is_symlink():
        raise ValueError("source cache is absent, a symlink, or not a directory")
    observed: dict[str, dict[str, Any]] = {}
    for name, expected in SOURCE_FILES.items():
        path = source_dir / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing regular source-cache file: {name}")
        identity: dict[str, Any] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if path.suffix.lower() == ".pdf":
            identity["pages"] = len(PdfReader(str(path)).pages)
        if identity != expected:
            raise ValueError(f"source-cache identity mismatch for {name}: {identity}")
        observed[name] = identity
    return observed


def parse_baseline(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        if len(digest) != 64 or relative in rows:
            raise ValueError("invalid Y0--Y3 baseline manifest")
        rows[relative] = digest
    if len(rows) != ORIGINAL_FILE_COUNT:
        raise ValueError("Y0--Y3 baseline must contain exactly 47 files")
    if set(rows) != set(y0_y3._required_stage_files()):
        raise ValueError("Y0--Y3 baseline relative paths differ from frozen registry")
    if sha256_bytes(raw.encode("utf-8")) != ORIGINAL_MANIFEST_SHA256:
        raise ValueError("Y0--Y3 baseline aggregate hash mismatch")
    return rows


def verify_original_files(stage: Path, baseline: dict[str, str]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative, expected_digest in sorted(baseline.items()):
        path = stage / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"frozen Y0--Y3 file is absent or not regular: {relative}")
        digest = sha256_file(path)
        if digest != expected_digest:
            raise ValueError(f"frozen Y0--Y3 hash changed: {relative}")
        observed[relative] = digest
    return observed


def _parse_structured_file(path: Path) -> None:
    if path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix in {".yaml", ".yml"}:
        if yaml.safe_load(path.read_text(encoding="utf-8")) is None:
            raise ValueError(f"empty YAML: {path}")
    elif path.suffix == ".csv":
        with path.open("rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not list(reader):
                raise ValueError(f"empty CSV: {path}")


def validate_payload(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        sources = payload_sources(repo)
    except ValueError as exc:
        return [str(exc)]
    for relative, path in sorted(sources.items()):
        if path.suffix.lower() in {".pdf", ".zip"}:
            errors.append(f"forbidden tracked payload type: {relative}")
        try:
            _parse_structured_file(path)
        except (ValueError, csv.Error, json.JSONDecodeError, yaml.YAMLError) as exc:
            errors.append(f"payload parse failure {relative}: {exc}")
    oracle_path = sources[f"{Y4A_ROOT}/05_MATHEMATICAL_ORACLES/Y4A_LINEAR_ORACLE_RESULTS.csv"]
    oracle_rows = _read_oracle_csv(oracle_path)
    if oracle_rows != linear_oracle_rows():
        errors.append("tracked oracle CSV differs from deterministic calculation")
    oracle_ids = {row.get("oracle_id") for row in oracle_rows}
    if len(oracle_rows) != ORACLE_COUNT or not REQUIRED_ORACLE_IDS.issubset(oracle_ids):
        errors.append("tracked oracle CSV omits required external identity checks")
    status_path = sources["11_REPORT/LC02_Y4A_STATUS.json"]
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("terminal_status") != TERMINAL_STATUS:
            errors.append("Y4A terminal status mismatch")
        for gate in (
            "formal_lc02_admission",
            "implementation_authorized",
            "production_solver_authorized",
            "C00_authorized",
            "representative_cases_authorized",
            "comparison_run_authorized",
        ):
            if status.get(gate) is not False:
                errors.append(f"Y4A gate is not false: {gate}")
        counters = status.get("execution_counters", {})
        if not counters or any(value != 0 for value in counters.values()):
            errors.append("Y4A execution counters absent or nonzero")
        expected_code_hash = sha256_file(Path(__file__))
        if status.get("audit_code_hash") != expected_code_hash:
            errors.append("Y4A audit-code hash mismatch")
        expected_levels = {
            "YIN2023_EKF": "FAITHFUL_ALGORITHM_REPRODUCTION",
            "YIN2023_AKF": "FAITHFUL_MODULE_REPRODUCTION",
            "YIN2023_RKF": "PAPER_DERIVED_POLICY_BASELINE",
            "YIN2023_RAEKF": "PAPER_DERIVED_POLICY_BASELINE",
        }
        if status.get("branch_reproduction_levels") != expected_levels:
            errors.append("Y4A branch reproduction levels differ from Outcome B")
        expected_gate_values = {
            "base_21_state_model_closed": True,
            "position_only_measurement_closed": True,
            "improved_R_closed": True,
            "AKF_statistic_update_unique": False,
            "L_k_versus_Z_k_closed": False,
            "standardized_residual_unique": False,
            "IGGIII_matrix_construction_unique": False,
            "zero_weight_policy_unique": False,
            "RAEKF_fusion_reset_unique": False,
            "no_trace_or_performance_based_completion": True,
        }
        if status.get("hard_gates") != expected_gate_values:
            errors.append("Y4A status hard-gate values differ from source decision")
        immutability = status.get("immutability", {})
        if immutability.get("original_Y0_Y3_file_count") != ORIGINAL_FILE_COUNT:
            errors.append("Y4A original-file count mismatch")
        if immutability.get("appended_file_count") != Y4A_APPEND_FILE_COUNT:
            errors.append("Y4A appended-file count mismatch")
        if immutability.get("final_stage_file_count") != FINAL_STAGE_FILE_COUNT:
            errors.append("Y4A final-stage count mismatch")
        if immutability.get("original_manifest_sha256") != ORIGINAL_MANIFEST_SHA256:
            errors.append("Y4A status original-manifest hash mismatch")
        if status.get("end_head_semantics") != "PRECOMMIT_ARTIFACT_BUILD_ANCHOR":
            errors.append("Y4A end-head semantics are not explicit")
        if status.get("oracle_status", {}).get("count") != ORACLE_COUNT:
            errors.append("Y4A status oracle count mismatch")
        scientific_access = status.get("scientific_access_counters", {})
        if not scientific_access or any(value != 0 for value in scientific_access.values()):
            errors.append("Y4A scientific-access counters absent or nonzero")
        if status.get("administrative_validation_inventory") != (
            ADMINISTRATIVE_VALIDATION_INVENTORY
        ):
            errors.append("Y4A administrative validation inventory differs")
        if status.get("authorized_frozen_Y0_Y3_input_contract_fact_reuse") != (
            AUTHORIZED_FROZEN_INPUT_CONTRACT_FACT_REUSE
        ):
            errors.append("Y4A authorized frozen input-contract fact reuse differs")
        if status.get("source_access_counts") != SOURCE_ACCESS_COUNTS:
            errors.append("Y4A source-access counts differ")
        if status.get("scientific_access_counter_semantics") != (
            "NEW_Y4A_SCIENTIFIC_OPENS_ONLY"
        ):
            errors.append("Y4A scientific-access counter scope differs")
        repair_history = status.get("uncommitted_draft_repair_history", {})
        if repair_history.get("initial_draft_32_file_aggregate_sha256") != (
            INITIAL_DRAFT_Y4A_MANIFEST_SHA256
        ):
            errors.append("Y4A status initial-draft manifest history differs")
        if repair_history.get("first_correction_32_file_aggregate_sha256") != (
            FIRST_CORRECTION_Y4A_MANIFEST_SHA256
        ):
            errors.append("Y4A status first-correction manifest history differs")
        if repair_history.get("second_correction_32_file_aggregate_sha256") != (
            SECOND_CORRECTION_Y4A_MANIFEST_SHA256
        ):
            errors.append("Y4A status second-correction manifest history differs")
        if repair_history.get("third_correction_32_file_aggregate_sha256") != (
            THIRD_CORRECTION_Y4A_MANIFEST_SHA256
        ):
            errors.append("Y4A status third-correction manifest history differs")
        validation = status.get("durable_validation", {})
        if validation != EXPECTED_DURABLE_VALIDATION:
            errors.append("durable validation command/result/count record differs")
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Y4A status validation failure: {exc}")
    rubric_path = sources[
        f"{Y4A_ROOT}/06_ADMISSION_DECISION/YIN2023_FORMAL_ADMISSION_RUBRIC.yaml"
    ]
    try:
        rubric = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
        if rubric.get("terminal_status") != TERMINAL_STATUS:
            errors.append("admission rubric terminal mismatch")
        gates = rubric.get("hard_gates", {})
        expected_gates = {
            "base_21_state_model_closed",
            "position_only_measurement_closed",
            "improved_R_closed",
            "AKF_statistic_update_unique",
            "L_k_versus_Z_k_closed",
            "standardized_residual_unique",
            "IGGIII_matrix_construction_unique",
            "zero_weight_policy_unique",
            "RAEKF_fusion_reset_unique",
            "no_trace_or_performance_based_completion",
        }
        if set(gates) != expected_gates:
            errors.append("admission rubric hard-gate names differ")
        expected_gate_values = {
            "base_21_state_model_closed": True,
            "position_only_measurement_closed": True,
            "improved_R_closed": True,
            "AKF_statistic_update_unique": False,
            "L_k_versus_Z_k_closed": False,
            "standardized_residual_unique": False,
            "IGGIII_matrix_construction_unique": False,
            "zero_weight_policy_unique": False,
            "RAEKF_fusion_reset_unique": False,
            "no_trace_or_performance_based_completion": True,
        }
        if {name: value.get("pass") for name, value in gates.items()} != expected_gate_values:
            errors.append("admission rubric hard-gate values differ")
        for gate in (
            "formal_lc02_admission",
            "implementation_authorized",
            "production_solver_authorized",
            "C00_authorized",
            "representative_cases_authorized",
            "comparison_run_authorized",
        ):
            if rubric.get(gate) is not False:
                errors.append(f"admission rubric gate is not false: {gate}")
    except yaml.YAMLError as exc:
        errors.append(f"admission rubric parse failure: {exc}")
    forbidden_path = sources[
        f"{Y4A_ROOT}/06_ADMISSION_DECISION/Y4A_FORBIDDEN_ACCESS_AUDIT.json"
    ]
    try:
        forbidden = json.loads(forbidden_path.read_text(encoding="utf-8"))
        for section in ("forbidden_access_counters", "execution_counters"):
            counters = forbidden.get(section, {})
            if not counters or any(value != 0 for value in counters.values()):
                errors.append(f"Y4A {section} absent or nonzero")
        if forbidden.get("forbidden_access_pass") is not True:
            errors.append("Y4A forbidden-access decision is not pass")
        if forbidden.get("administrative_validation_inventory") != (
            ADMINISTRATIVE_VALIDATION_INVENTORY
        ):
            errors.append("forbidden-access audit administrative inventory differs")
        fact_reuse = forbidden.get("authorized_frozen_Y0_Y3_input_contract_fact_reuse", {})
        if fact_reuse.get("facts") != AUTHORIZED_FROZEN_INPUT_CONTRACT_FACT_REUSE["facts"]:
            errors.append("forbidden-access audit frozen fact reuse differs")
        if fact_reuse.get("fact_count") != 4:
            errors.append("forbidden-access audit frozen fact count differs")
        allowed_sources = forbidden.get("allowed_scientific_source_access", {})
        for key, expected in SOURCE_ACCESS_COUNTS.items():
            if allowed_sources.get(key) != expected:
                errors.append(f"forbidden-access source count differs: {key}")
        if "attributable_cited_source_author_uploads_inspected" in allowed_sources:
            errors.append("forbidden-access audit retains ambiguous author-upload count")
        semantics = forbidden.get("access_semantics", {})
        if semantics.get("LC01_or_Canonical_scientific_execution_or_content_use") is not False:
            errors.append("forbidden-access audit scientific-use boundary differs")
        if semantics.get("scientific_access_counter_scope") != (
            "NEW_Y4A_SCIENTIFIC_OPENS_ONLY"
        ):
            errors.append("forbidden-access scientific counter scope differs")
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"forbidden-access audit validation failure: {exc}")
    oracle_summary_path = sources[
        f"{Y4A_ROOT}/05_MATHEMATICAL_ORACLES/Y4A_ORACLE_SUMMARY.json"
    ]
    try:
        oracle_summary = json.loads(oracle_summary_path.read_text(encoding="utf-8"))
        if (oracle_summary.get("oracle_count"), oracle_summary.get("passed_count")) != (
            ORACLE_COUNT,
            ORACLE_COUNT,
        ):
            errors.append("oracle summary count mismatch")
        if not REQUIRED_ORACLE_IDS.issubset(set(oracle_summary.get("required_identity_ids", []))):
            errors.append("oracle summary omits required identity IDs")
        if oracle_summary.get("source_uniqueness_proved") is not False:
            errors.append("oracles must not claim source uniqueness")
        if oracle_summary.get("equation_11_mapping_source_closed") is not False:
            errors.append("oracle summary must preserve unresolved Eq.11 mapping")
        if oracle_summary.get("inlier_information_oracle_mapping_provenance") != (
            "PAPER_DERIVED_POLICY_BASELINE_UNSELECTED"
        ):
            errors.append("inlier-information oracle provenance differs")
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"oracle-summary validation failure: {exc}")
    source_registry_path = sources[
        f"{Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y4A_SOURCE_REGISTRY.csv"
    ]
    source_registry_text = source_registry_path.read_text(encoding="utf-8")
    if "xueshushe.cn" in "\n".join(
        path.read_text(encoding="utf-8")
        for path in sources.values()
        if path.suffix.lower() in {".csv", ".md", ".json", ".yaml", ".yml"}
    ):
        errors.append("secondary Jiang2020 aggregator is forbidden from Y4A payload")
    with source_registry_path.open("rt", encoding="utf-8", newline="") as stream:
        source_reader = csv.DictReader(stream)
        source_rows = list(source_reader)
        source_fields = set(source_reader.fieldnames or [])
    required_source_fields = {
        "source_id",
        "title",
        "authors",
        "doi",
        "version",
        "pages",
        "sha256",
        "license",
        "access_status",
        "endpoint",
        "equation_relevance",
    }
    if not required_source_fields.issubset(source_fields):
        errors.append("source registry omits mandatory identity/access/equation fields")
    required_source_ids = {
        "YIN2023_VOR",
        "YIN2023_V2",
        "YIN2023_OFFICIAL_HTML",
        "YIN2023_OFFICIAL_HTML_JINA_CAPTURE",
        "YIN2023_VERSION_NOTES",
        "YIN2023_SUPPLEMENT_SEARCH",
        "YIN2023_PEER_REVIEW_RECORD",
        "YIN2023_AUTHOR_RESPONSE_DIRECT",
        "YIN2023_AUTHOR_RESPONSE_JINA_CAPTURE",
        "YIN2023_DATA_CODE_STATEMENT",
        "YIN_AUTHOR_INSTITUTION_REPOSITORY_SEARCH",
        "YANG_HE_XU_2001",
        "YANG_HE_XU_2001_AUTHOR_UPLOAD",
        "YANG_CHENG_SHUM_TAPLEY_1999",
        "YANG_CHENG_SHUM_TAPLEY_1999_AUTHOR_UPLOAD",
        "YANG_SONG_XU_2002",
        "YANG_SONG_XU_2002_AUTHOR_UPLOAD",
        "YANG_1994_DEPENDENT_OBSERVATIONS",
        "YIN_REF35_JIANG2020",
        "YIN_REF36_YANG2013",
        "YIN_REF37_JIANG2021",
        "JIANG2021_NCWU_METADATA",
        "YIN_REF38_KNIGHT2009",
        "KNIGHT2009_UNSW_METADATA",
        "KNIGHT2009_RESEARCHGATE_AUTHOR_UPLOAD",
        "YIN_REF39_NIU2022",
        "NIU_TCRTKINS_REPOSITORY",
        "NIU_TCRTKINS_FUSION_CPP",
        "SDUST_CN117647251A",
        "KFGINS_ACKNOWLEDGED_BASE",
        "KFGINS_INSMECH_FROZEN_Y0_Y3",
    }
    if not required_source_ids.issubset({row.get("source_id") for row in source_rows}):
        errors.append("source registry omits prompt-mandatory sources/endpoints")
    sources_by_id = {row.get("source_id"): row for row in source_rows}
    exact_source_expectations = {
        "YIN2023_OFFICIAL_HTML_JINA_CAPTURE": {
            "endpoint": "https://r.jina.ai/http://www.mdpi.com/2072-4292/15/17/4125",
            "bytes": "104971",
            "hash_scope": "JINA_UTF8_MARKDOWN_TRANSPORT_BYTES_NOT_PAPER_BINARY",
        },
        "YIN2023_AUTHOR_RESPONSE_JINA_CAPTURE": {
            "endpoint": (
                "https://r.jina.ai/http://susy.mdpi.com/user/review/displayFile/"
                "41299766/4MoqTeV7?file=author-coverletter%26report=31242108"
            ),
            "bytes": "18305",
            "hash_scope": "JINA_UTF8_MARKDOWN_TRANSPORT_BYTES_NOT_ORIGINAL_PDF",
        },
        "YIN_REF36_YANG2013": {
            "title": "Main Progress of Adaptively Robust Filter with Applications in Navigation",
            "pages": "7",
            "doi": "10.16547/j.cnki.10-1096.2013.01.006",
        },
        "YIN_REF35_JIANG2020": {
            "pages": "1",
            "endpoint": "https://doi.org/10.11947/j.AGCS.2020.20190429",
        },
        "YIN_REF37_JIANG2021": {"pages": "11"},
        "YIN_REF38_KNIGHT2009": {"doi": "10.1017/S0373463309990142"},
        "YANG_CHENG_SHUM_TAPLEY_1999": {"doi": "10.1007/s001900050252"},
        "YANG_HE_XU_2001": {"doi": "10.1007/s001900000157"},
        "YANG_SONG_XU_2002": {"doi": "10.1007/s00190-002-0256-7"},
        "YANG_1994_DEPENDENT_OBSERVATIONS": {"doi": "10.1007/BF03655325"},
    }
    for source_id, expectations in exact_source_expectations.items():
        row = sources_by_id.get(source_id, {})
        for field, expected in expectations.items():
            if row.get(field) != expected:
                errors.append(f"source registry exact field differs: {source_id}.{field}")
    if sources_by_id.get("YIN2023_SUPPLEMENT_SEARCH", {}).get("closure_effect") != (
        "NO_ATTRIBUTABLE_SUPPLEMENT_FOUND"
    ):
        errors.append("supplement search conclusion differs")
    if not sources_by_id.get("KFGINS_ACKNOWLEDGED_BASE", {}).get("endpoint", "").endswith(
        "/src/kf-gins/gi_engine.cpp"
    ):
        errors.append("KF-GINS gi_engine source endpoint differs")
    if not sources_by_id.get("KFGINS_INSMECH_FROZEN_Y0_Y3", {}).get(
        "endpoint", ""
    ).endswith("/src/kf-gins/insmech.cpp"):
        errors.append("KF-GINS insmech cross-reference endpoint differs")
    for identity in SOURCE_FILES.values():
        if identity["sha256"] not in source_registry_text:
            errors.append(f"source registry omits {identity['sha256']}")
    unresolved_path = sources[
        f"{Y4A_ROOT}/01_SYMBOL_RECONCILIATION/YIN2023_UNRESOLVED_SYMBOL_REGISTRY.csv"
    ]
    with unresolved_path.open("rt", encoding="utf-8", newline="") as stream:
        unresolved_reader = csv.DictReader(stream)
        unresolved_rows = list(unresolved_reader)
        unresolved_fields = set(unresolved_reader.fieldnames or [])
    required_symbol_fields = {
        "symbol",
        "paper_equation",
        "paper_wording",
        "dimension",
        "unit",
        "source_definition",
        "candidate_interpretations",
        "selected_interpretation",
        "selection_evidence",
        "remaining_ambiguity",
    }
    required_symbols = {
        "L_k",
        "Z_k",
        "V_hat_k",
        "bar_V_k",
        "Delta_X_tilde_k",
        "e_V_i",
        "bar_A_k",
        "bar_A_(Xhat_k)",
        "bar_A(tilde_V_i)",
        "w(tilde_V_i)",
        "R_i",
        "Omega",
        "alpha_k",
        "v/omega",
        "ω (omega)",
        "ϖ (varpi)",
        "c",
        "k",
        "k0",
        "k1",
        "V_k",
        "A_k",
        "A(e_V_i)",
    }
    if not required_symbol_fields.issubset(unresolved_fields):
        errors.append("symbol registry omits mandatory semantic columns")
    if required_symbols != {row.get("symbol") for row in unresolved_rows}:
        errors.append("symbol registry omits mandatory paper symbols")
    symbols_by_name = {row.get("symbol"): row for row in unresolved_rows}
    if symbols_by_name.get("ω (omega)", {}).get("paper_equation") != "Eq.10":
        errors.append("component omega is not bound to Eq.10")
    if symbols_by_name.get("ϖ (varpi)", {}).get("paper_equation") != "Eqs.12-14":
        errors.append("fusion varpi is not bound to Eqs.12-14")
    if "|Delta_X_tilde_k|" not in symbols_by_name.get("alpha_k", {}).get(
        "paper_wording", ""
    ):
        errors.append("Eq.7 absolute-value glyph is absent from symbol registry")
    if "|Delta_X_tilde_k|" not in symbols_by_name.get("ϖ (varpi)", {}).get(
        "source_definition", ""
    ):
        errors.append("Eq.14 absolute-value glyph is absent from symbol registry")
    if "V_hat_k" not in symbols_by_name.get("bar_V_k", {}).get(
        "remaining_ambiguity", ""
    ):
        errors.append("Eq.8 hat versus Eq.9 bar ambiguity is absent")
    if symbols_by_name.get("bar_A_(Xhat_k)", {}).get("selected_interpretation") != (
        "NONE_UNRESOLVED"
    ):
        errors.append("Eq.9 state-weight matrix must remain unresolved")
    if "self-referential" not in symbols_by_name.get("bar_A(tilde_V_i)", {}).get(
        "paper_wording", ""
    ):
        errors.append("Eq.11 self-reference is absent from symbol registry")
    latin_w = symbols_by_name.get("w(tilde_V_i)", {})
    if latin_w.get("paper_equation") != "Eq.11":
        errors.append("Eq.11 Latin w multiplier is absent from symbol registry")
    if "LATIN" not in latin_w.get("paper_wording", ""):
        errors.append("Eq.11 Latin w glyph identity is not explicit")
    if "Eq.10 weighting function enters Eq.11" not in latin_w.get(
        "selection_evidence", ""
    ):
        errors.append("author-response semantic relation for Eq.11 Latin w is absent")
    compatibility_mappings = {
        "V_k": "COMPATIBILITY_ALIAS_TO_bar_V_k_NOT_V_hat_k",
        "A_k": "COMPATIBILITY_ALIAS_TO_bar_A_k",
        "A(e_V_i)": "COMPATIBILITY_ALIAS_TO_bar_A(tilde_V_i)",
    }
    for symbol, mapping in compatibility_mappings.items():
        row = symbols_by_name.get(symbol, {})
        if row.get("selected_interpretation") != mapping:
            errors.append(f"compatibility symbol mapping differs: {symbol}")
        if row.get("provenance") != "PAPER_DERIVED_COMPATIBILITY_ERRATA":
            errors.append(f"compatibility symbol provenance differs: {symbol}")
    lk_path = sources[
        f"{Y4A_ROOT}/01_SYMBOL_RECONCILIATION/YIN2023_LK_ZK_DECISION.json"
    ]
    akf_path = sources[f"{Y4A_ROOT}/02_AKF_CLOSURE/YIN2023_AKF_CLOSURE_DECISION.json"]
    try:
        lk_decision = json.loads(lk_path.read_text(encoding="utf-8"))
        akf_decision = json.loads(akf_path.read_text(encoding="utf-8"))
        if set(lk_decision.get("allowed_decision_enum", [])) != ALLOWED_LZ_DECISIONS:
            errors.append("L/Z allowed decision enum differs from prompt")
        if lk_decision.get("decision") not in ALLOWED_LZ_DECISIONS:
            errors.append("L/Z decision is outside the allowed enum")
        if lk_decision.get("decision") != "UNRESOLVED":
            errors.append("L/Z decision must remain UNRESOLVED")
        if set(akf_decision.get("allowed_decision_enum", [])) != ALLOWED_AKF_DECISIONS:
            errors.append("AKF allowed decision enum differs from prompt")
        if akf_decision.get("decision") not in ALLOWED_AKF_DECISIONS:
            errors.append("AKF decision is outside the allowed enum")
        if akf_decision.get("decision") != "MULTIPLE_PLAUSIBLE_COMPLETIONS":
            errors.append("AKF decision must preserve multiple plausible completions")
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"decision-enum validation failure: {exc}")
    akf_contract_path = sources[
        f"{Y4A_ROOT}/02_AKF_CLOSURE/YIN2023_AKF_FINAL_CONTRACT.yaml"
    ]
    try:
        akf_contract = yaml.safe_load(akf_contract_path.read_text(encoding="utf-8"))
        paper_direct = akf_contract.get("paper_direct", {})
        if paper_direct.get("residual_for_statistic") != (
            "bar_V_k = H_k Xhat_k - Z_k"
        ):
            errors.append("AKF Eq.6 barred residual transcription differs")
        if paper_direct.get("statistic") != (
            "Delta_X_tilde_k = sqrt((bar_V_k^T bar_V_k)/tr(P_(bar_V_k)))"
        ):
            errors.append("AKF Eq.6 statistic transcription differs")
        if paper_direct.get("P_bar_V_k_definition_printed") != (
            "P_(bar_V_k) = Phi_k P_(Xhat_(k-1)) Phi^T + Q_k"
        ):
            errors.append("AKF Eq.6 covariance transcription differs")
        if paper_direct.get("right_Phi_index_as_printed") != "NONE_EXPLICIT":
            errors.append("AKF Eq.6 right-Phi index boundary differs")
        candidate_mapping = akf_contract.get("paper_derived_candidate_mapping_not_selected", {})
        if candidate_mapping.get("paper_direct") is not False or candidate_mapping.get(
            "selected"
        ) is not False:
            errors.append("AKF candidate covariance mapping is not fail-closed")
        adaptive_factor = paper_direct.get("adaptive_factor", {})
        if adaptive_factor.get("paper_condition_abs_Delta_X_tilde_le_k") != 1.0:
            errors.append("AKF Eq.7 absolute-value lower branch differs")
        if adaptive_factor.get("paper_condition_abs_Delta_X_tilde_gt_k") != (
            "k/|Delta_X_tilde_k|"
        ):
            errors.append("AKF Eq.7 absolute-value upper branch differs")
        if adaptive_factor.get("absolute_value_glyph_preserved") is not True:
            errors.append("AKF Eq.7 absolute-value glyph is not preserved")
    except yaml.YAMLError as exc:
        errors.append(f"AKF contract parse failure: {exc}")
    standardizer_contract_path = sources[
        f"{Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_STANDARDIZED_RESIDUAL_CONTRACT.yaml"
    ]
    try:
        standardizer = yaml.safe_load(standardizer_contract_path.read_text(encoding="utf-8"))
        paper_direct_standardizer = standardizer.get("paper_direct", {})
        if paper_direct_standardizer.get("innovation") != (
            "V_hat_k = L_k - H_k Xhat_(k/k-1)"
        ):
            errors.append("RKF Eq.8 hatted innovation transcription differs")
        if paper_direct_standardizer.get("equation_9_objective") != (
            "Omega = bar_V_k^T bar_A_k bar_V_k + alpha_k bar_V_k^T "
            "bar_A_(Xhat_k) bar_V_k = min"
        ):
            errors.append("RKF Eq.9 objective transcription differs")
        if paper_direct_standardizer.get("equation_9_uses_V_hat_k") is not False:
            errors.append("RKF Eq.9 must preserve hatted/barred mismatch")
        unresolved_standardizer = standardizer.get("unresolved", {})
        for key in ("V_hat_k_equals_bar_V_k", "bar_A_Xhat_k_definition"):
            if unresolved_standardizer.get(key, "MISSING") is not None:
                errors.append(f"RKF objective ambiguity must remain unresolved: {key}")
    except yaml.YAMLError as exc:
        errors.append(f"standardized-residual contract parse failure: {exc}")
    igg_contract_path = sources[
        f"{Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_IGGIII_EQUIVALENT_WEIGHT_CONTRACT.yaml"
    ]
    try:
        igg_contract = yaml.safe_load(igg_contract_path.read_text(encoding="utf-8"))
        scalar_weight = igg_contract.get("scalar_weight", {})
        if scalar_weight.get("paper_component_symbol") != (
            "ω (U+03C9 GREEK SMALL LETTER OMEGA)"
        ):
            errors.append("IGGIII Eq.10 component symbol is not exact omega")
        if scalar_weight.get("effective_zero_domain") != "|tilde_V_i|>=k1":
            errors.append("IGGIII effective zero domain differs")
        if "|tilde_V_i|" not in scalar_weight.get("paper_printed_middle", ""):
            errors.append("IGGIII printed middle absolute-value glyph is absent")
        eq11 = igg_contract.get("equation_11_paper_direct", {})
        if eq11.get("overloaded_symbol") != "bar_A(tilde_V_i)":
            errors.append("Eq.11 overloaded symbol differs")
        if eq11.get("lhs_and_low_middle_rhs_use_same_symbol") is not True:
            errors.append("Eq.11 self-reference is not preserved")
        if eq11.get("middle_multiplier_symbol") != (
            "w(tilde_V_i) (LATIN SMALL LETTER W)"
        ):
            errors.append("Eq.11 Latin w multiplier differs")
        if eq11.get("middle_branch") != (
            "bar_A(tilde_V_i) = bar_A(tilde_V_i) * w(tilde_V_i)"
        ):
            errors.append("Eq.11 exact middle branch differs")
        if eq11.get("distinct_from_equation_10_omega_glyph") is not True:
            errors.append("Eq.11 Latin w is not distinguished from Eq.10 omega")
        if eq11.get("prose_identity") != "bar_A(tilde_V_i) = R_i^-1":
            errors.append("Eq.11 prose identity differs")
        if eq11.get("unique_base_equivalent_split") is not False:
            errors.append("Eq.11 base/equivalent split must remain unresolved")
        derived_split = igg_contract.get("conventional_base_equivalent_split_candidate", {})
        if derived_split.get("provenance") != "PAPER_DERIVED_POLICY_BASELINE":
            errors.append("Eq.11 conventional split provenance differs")
        if derived_split.get("selected") is not False:
            errors.append("Eq.11 conventional split must remain unselected")
        author_response = igg_contract.get("author_response", {})
        if author_response.get("equation_10_weight_enters_equation_11") is not True:
            errors.append("author response does not preserve Eq.10-to-Eq.11 relation")
        if author_response.get("glyphs_equated_by_source") is not False:
            errors.append("Eq.10 omega and Eq.11 Latin w glyphs were silently equated")
    except yaml.YAMLError as exc:
        errors.append(f"IGGIII contract parse failure: {exc}")
    raekf_path = sources[
        f"{Y4A_ROOT}/04_RAEKF_CLOSURE/YIN2023_RAEKF_FINAL_CONTRACT.yaml"
    ]
    try:
        raekf = yaml.safe_load(raekf_path.read_text(encoding="utf-8"))
        fusion = raekf.get("fusion_paper_direct", {})
        if fusion.get("controlling_statistic") != "Delta_X_tilde_k":
            errors.append("RAEKF controlling-statistic symbol was altered")
        if fusion.get("paper_fusion_symbol") != "ϖ (U+03D6 GREEK PI SYMBOL; varpi)":
            errors.append("RAEKF paper fusion symbol is not exact varpi")
        if fusion.get("varpi_when_abs_Delta_X_tilde_le_c") != 0.85:
            errors.append("RAEKF absolute-value lower fusion branch differs")
        if fusion.get("varpi_when_abs_Delta_X_tilde_gt_c") != 0.15:
            errors.append("RAEKF absolute-value upper fusion branch differs")
        if fusion.get("absolute_value_glyph_preserved") is not True:
            errors.append("RAEKF Eq.14 absolute-value glyph is not preserved")
        if fusion.get("same_unmodified_prior_for_both_branches") is not True:
            errors.append("RAEKF same-prior source closure is absent")
        robust_branch = raekf.get("branches", {}).get("robust", {})
        for key in (
            "V_hat_k_versus_bar_V_k_closed",
            "equation_9_bar_A_Xhat_k_defined",
            "equation_11_scalar_equivalent_information_mapping_unique",
        ):
            if robust_branch.get(key) is not False:
                errors.append(f"RAEKF robust-branch ambiguity differs: {key}")
        unresolved_fusion = raekf.get("fusion_execution_unresolved", {})
        if unresolved_fusion.get("fusion_occurs_before_error_feedback", "MISSING") is not None:
            errors.append("RAEKF feedback order must remain unresolved")
        if unresolved_fusion.get("P_rk_uniquely_executable") is not False:
            errors.append("RAEKF robust covariance must remain fail-closed")
    except yaml.YAMLError as exc:
        errors.append(f"RAEKF contract parse failure: {exc}")
    oracle_by_id = {row["oracle_id"]: row for row in oracle_rows}
    zero_policy_oracle = oracle_by_id.get("ZERO_WEIGHT_NO_UNIQUE_YIN_POLICY", {})
    if zero_policy_oracle.get("observed") != "2":
        errors.append("zero-policy oracle must observe two executable unselected completions")
    if zero_policy_oracle.get("expected") != (
        ">=2_EXECUTABLE_COMPLETIONS_PLUS_1_NONEXECUTABLE_PRINTED_PATH"
    ):
        errors.append("zero-policy oracle singular/executable semantics differ")
    unit_oracle = oracle_by_id.get("DIAGONAL_R_UNIT_EXPONENT_M2", {})
    if unit_oracle.get("observed") != "2" or unit_oracle.get("passed") != "true":
        errors.append("computed diagonal-R unit exponent oracle differs")
    inlier_oracle = oracle_by_id.get("IGGIII_INLIER_INFORMATION_NOMINAL", {})
    if "PAPER_DERIVED" not in inlier_oracle.get("claim", ""):
        errors.append("inlier-information oracle omits derived Eq.11 provenance")
    if "unselected PAPER_DERIVED candidate" not in inlier_oracle.get("meaning", ""):
        errors.append("inlier-information oracle overclaims Eq.11 source closure")
    if not all(
        literal in inlier_oracle.get("meaning", "")
        for literal in ("Greek omega", "Latin w", "author response")
    ):
        errors.append("inlier-information oracle omits Eq.10/Eq.11 glyph provenance")
    forecast_path = sources[
        f"{Y4A_ROOT}/06_ADMISSION_DECISION/LC02_C00_MECHANISM_ACTIVATION_FORECAST.md"
    ]
    forecast_text = forecast_path.read_text(encoding="utf-8")
    for literal in (
        "1,510",
        "Q=1",
        "1.13",
        "1.74",
        "per-axis covariance variation",
        "separately frozen real",
        "clearly labelled and separately frozen semisynthetic",
        "No case may be designed or selected from final error or trace",
        "No C00 run occurred",
    ):
        if literal not in forecast_text:
            errors.append(f"C00 forecast omits frozen literal: {literal}")
    baseline_path = sources[
        f"{Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y0_Y3_IMMUTABILITY_BASELINE.sha256"
    ]
    try:
        parse_baseline(baseline_path)
    except ValueError as exc:
        errors.append(f"baseline validation failure: {exc}")
    return errors


def _stage_entry_errors(stage: Path, expected_files: set[str]) -> list[str]:
    if not stage.is_dir() or stage.is_symlink():
        return ["stage is absent, a symlink, or not a directory"]
    entries = list(stage.rglob("*"))
    errors = [
        f"symlink forbidden: {path.relative_to(stage)}"
        for path in entries
        if path.is_symlink()
    ]
    errors.extend(
        f"special filesystem entry forbidden: {path.relative_to(stage)}"
        for path in entries
        if not path.is_symlink() and not path.is_file() and not path.is_dir()
    )
    files = {
        str(path.relative_to(stage))
        for path in entries
        if path.is_file() and not path.is_symlink()
    }
    errors.extend(f"missing {relative}" for relative in sorted(expected_files - files))
    errors.extend(f"unexpected {relative}" for relative in sorted(files - expected_files))
    if len(files) != len(expected_files):
        errors.append(f"stage file count {len(files)} != {len(expected_files)}")
    allowed_dirs: set[str] = set()
    for relative in expected_files:
        parent = Path(relative).parent
        while parent != Path("."):
            allowed_dirs.add(str(parent))
            parent = parent.parent
    dirs = {
        str(path.relative_to(stage))
        for path in entries
        if path.is_dir() and not path.is_symlink()
    }
    errors.extend(f"unexpected directory {relative}" for relative in sorted(dirs - allowed_dirs))
    for path in entries:
        if path.is_file() and path.suffix.lower() in {".pdf", ".zip"}:
            errors.append(f"forbidden PDF/ZIP: {path.relative_to(stage)}")
    return errors


def validate_augmented_stage(stage: Path, repo: Path) -> list[str]:
    errors = validate_payload(repo)
    expected = set(y0_y3._required_stage_files()) | set(y0_y3._allowed_y4a_append_files())
    errors.extend(_stage_entry_errors(stage, expected))
    errors.extend(y0_y3.validate_stage(stage))
    if errors:
        return errors
    sources = payload_sources(repo)
    baseline = parse_baseline(
        sources[f"{Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y0_Y3_IMMUTABILITY_BASELINE.sha256"]
    )
    try:
        verify_original_files(stage, baseline)
    except ValueError as exc:
        errors.append(str(exc))
    for relative, source in sorted(sources.items()):
        destination = stage / relative
        if sha256_file(source) != sha256_file(destination):
            errors.append(f"published payload parity mismatch: {relative}")
        try:
            _parse_structured_file(destination)
        except (ValueError, csv.Error, json.JSONDecodeError, yaml.YAMLError) as exc:
            errors.append(f"stage parse failure {relative}: {exc}")
    return errors


def _exclusive_write(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_directories(root: Path, relatives: Iterable[str]) -> None:
    directories = sorted(
        {Path(relative).parent for relative in relatives}, key=lambda item: (len(item.parts), str(item))
    )
    for relative in directories:
        current = root
        for component in relative.parts:
            candidate = current / component
            if candidate.exists() or candidate.is_symlink():
                if candidate.is_symlink() or not candidate.is_dir():
                    raise ValueError(f"publication directory is unsafe: {candidate}")
            else:
                os.mkdir(candidate, 0o755)
                _fsync_directory(current)
            current = candidate


def _build_scratch_payload(scratch: Path, sources: dict[str, Path]) -> None:
    _ensure_directories(scratch, sources)
    for relative, source in sorted(sources.items()):
        _exclusive_write(scratch / relative, source.read_bytes())
    for directory in sorted(
        {scratch / Path(relative).parent for relative in sources},
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        _fsync_directory(directory)
    expected = set(sources)
    errors = _stage_entry_errors(scratch, expected)
    if errors:
        raise ValueError("scratch payload invalid: " + "; ".join(errors))
    for relative, source in sources.items():
        if sha256_file(scratch / relative) != sha256_file(source):
            raise ValueError(f"scratch payload hash mismatch: {relative}")


def _publish_scratch(stage: Path, scratch: Path, relatives: Iterable[str]) -> None:
    ordered = sorted(relatives)
    _ensure_directories(stage, ordered)
    for relative in ordered:
        destination = stage / relative
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"append-only destination already exists: {relative}")
    for relative in ordered:
        _exclusive_write(stage / relative, (scratch / relative).read_bytes())
    for directory in sorted(
        {stage / Path(relative).parent for relative in ordered},
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        _fsync_directory(directory)
    _fsync_directory(stage)


def _verify_exact_stage_target(stage: Path, repo: Path) -> None:
    expected_stage = default_stage_root(repo)
    if Path(os.path.abspath(stage)) != Path(os.path.abspath(expected_stage)):
        raise ValueError("stage is not the exact locally resolved LC02 audit target")
    if not stage.is_dir() or stage.is_symlink():
        raise ValueError("exact LC02 stage is absent, a symlink, or not a directory")
    clean_root = expected_stage.parents[2]
    for protected in (clean_root, clean_root / "stages", expected_stage.parent, expected_stage):
        if protected.is_symlink() or not protected.is_dir():
            raise ValueError(f"protected publication path is unsafe: {protected}")
    if stage.resolve(strict=True) != expected_stage.resolve(strict=True):
        raise ValueError("resolved stage differs from exact locally configured target")


def _normalized_manifest_sha256(root: Path, relatives: Iterable[str]) -> str:
    manifest = "".join(
        f"{sha256_file(root / relative)}  {relative}\n" for relative in sorted(relatives)
    )
    return sha256_bytes(manifest.encode("utf-8"))


def _atomic_replace_regular(path: Path, data: bytes) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"guarded repair destination is not a regular file: {path}")
    temporary = path.with_name(f".{path.name}.lc02_y4a_repair_tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError(f"guarded repair temporary path already exists: {temporary}")
    try:
        _exclusive_write(temporary, data)
        _fsync_directory(path.parent)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists() and temporary.is_file() and not temporary.is_symlink():
            temporary.unlink()


def repair_uncommitted_y4a_draft(
    stage: Path, source_dir: Path, repo: Path
) -> dict[str, Any]:
    """Guardedly apply the consolidated correction to the exact current 32 files."""

    git_state = authorized_git_state(repo)
    _verify_exact_stage_target(stage, repo)
    verify_source_cache(source_dir)
    payload_errors = validate_payload(repo)
    if payload_errors:
        raise ValueError("corrected tracked payload invalid: " + "; ".join(payload_errors))
    sources = payload_sources(repo)
    baseline = parse_baseline(
        sources[f"{Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y0_Y3_IMMUTABILITY_BASELINE.sha256"]
    )
    expected_stage_files = set(y0_y3._required_stage_files()) | set(sources)
    structure_errors = _stage_entry_errors(stage, expected_stage_files)
    if structure_errors:
        raise ValueError("pre-repair stage mismatch: " + "; ".join(structure_errors))
    pre_original_hashes = verify_original_files(stage, baseline)
    pre_y4a_manifest = _normalized_manifest_sha256(stage, sources)
    if pre_y4a_manifest != PRE_CORRECTION_Y4A_MANIFEST_SHA256:
        raise ValueError("stage is not the exact known pre-correction 32-file Y4A draft")
    with tempfile.TemporaryDirectory(prefix="lc02-y4a-repair-", dir="/tmp") as temporary:
        scratch = Path(temporary)
        _build_scratch_payload(scratch, sources)
        for relative in sorted(sources):
            destination = stage / relative
            _atomic_replace_regular(destination, (scratch / relative).read_bytes())
    post_original_hashes = verify_original_files(stage, baseline)
    if pre_original_hashes != post_original_hashes:
        raise ValueError("frozen original 47 changed during Y4A draft repair")
    errors = validate_augmented_stage(stage, repo)
    if errors:
        raise ValueError("repaired stage validation failed: " + "; ".join(errors))
    return {
        "operation": "AUTHORIZED_FINAL_POST_REVIEW_CORRECTION_NOT_FIRST_WRITE_PUBLICATION",
        "git_state": git_state,
        "terminal_status": TERMINAL_STATUS,
        "original_file_count": len(pre_original_hashes),
        "original_manifest_sha256": ORIGINAL_MANIFEST_SHA256,
        "corrected_allowlist_file_count": len(sources),
        "pre_correction_y4a_manifest_sha256": pre_y4a_manifest,
        "post_correction_y4a_manifest_sha256": _normalized_manifest_sha256(stage, sources),
        "manifest_history": {
            "initial_draft": INITIAL_DRAFT_Y4A_MANIFEST_SHA256,
            "first_correction": FIRST_CORRECTION_Y4A_MANIFEST_SHA256,
            "second_correction": SECOND_CORRECTION_Y4A_MANIFEST_SHA256,
            "third_correction": THIRD_CORRECTION_Y4A_MANIFEST_SHA256,
            "final_post_review_correction": _normalized_manifest_sha256(stage, sources),
        },
        "final_stage_file_count": FINAL_STAGE_FILE_COUNT,
        "formal_lc02_admission": False,
        "implementation_authorized": False,
        "production_solver_authorized": False,
        "C00_authorized": False,
        "representative_cases_authorized": False,
        "comparison_run_authorized": False,
        "validation_errors": errors,
    }


def publish_y4a(stage: Path, source_dir: Path, repo: Path) -> dict[str, Any]:
    if git_head(repo) != START_HEAD:
        raise ValueError("Y4A must publish from the exact authorized start HEAD")
    _verify_exact_stage_target(stage, repo)
    verify_source_cache(source_dir)
    payload_errors = validate_payload(repo)
    if payload_errors:
        raise ValueError("; ".join(payload_errors))
    sources = payload_sources(repo)
    baseline = parse_baseline(
        sources[f"{Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y0_Y3_IMMUTABILITY_BASELINE.sha256"]
    )
    base_structure_errors = y0_y3._stage_structure_errors(stage)
    if base_structure_errors:
        raise ValueError("pre-publication base-stage mismatch: " + "; ".join(base_structure_errors))
    pre_hashes = verify_original_files(stage, baseline)
    for relative in sources:
        target = stage / relative
        if target.exists() or target.is_symlink():
            raise ValueError(f"Y4A/new report must be absent before publication: {relative}")
    with tempfile.TemporaryDirectory(prefix="lc02-y4a-payload-", dir="/tmp") as temporary:
        scratch = Path(temporary)
        _build_scratch_payload(scratch, sources)
        _publish_scratch(stage, scratch, sources)
    post_hashes = verify_original_files(stage, baseline)
    if pre_hashes != post_hashes:
        raise ValueError("frozen Y0--Y3 manifest changed during append-only publication")
    errors = validate_augmented_stage(stage, repo)
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "terminal_status": TERMINAL_STATUS,
        "method_id": METHOD_ID,
        "formal_lc02_admission": False,
        "implementation_authorized": False,
        "production_solver_authorized": False,
        "C00_authorized": False,
        "representative_cases_authorized": False,
        "comparison_run_authorized": False,
        "original_file_count": len(pre_hashes),
        "original_manifest_sha256": ORIGINAL_MANIFEST_SHA256,
        "appended_file_count": len(sources),
        "final_stage_file_count": FINAL_STAGE_FILE_COUNT,
        "source_identities_verified": sorted(SOURCE_FILES),
        "validation_errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    repo = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=repo / ".legsa_runtime/lc02_y4a_sources",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--repair-uncommitted-draft", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    stage = args.stage_root or default_stage_root(repo)
    if args.validate_only:
        errors = validate_augmented_stage(stage, repo)
        print(
            json.dumps(
                {"stage_root": str(stage), "validation_errors": errors},
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if errors else 0
    if args.repair_uncommitted_draft:
        result = repair_uncommitted_y4a_draft(stage, args.source_dir, repo)
    else:
        result = publish_y4a(stage, args.source_dir, repo)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
