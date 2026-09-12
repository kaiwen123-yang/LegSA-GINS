from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature import lc02_y0_y3_audit as y0_y3
from legsa_gins.paper_rebuild.horizontal_literature import (
    lc02_y4a_reproducibility_closure as audit,
)


REPO = Path(__file__).resolve().parents[2]
LOCAL_PATHS = REPO / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
SOURCE_CACHE = REPO / ".legsa_runtime/lc02_y4a_sources"
SOURCE_CACHE_SKIP_REASON = (
    "ignored Y4A source cache unavailable; registry and payload checks remain mandatory"
)
CANONICAL_HASHES = {
    "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py":
        "00a54aac97ec54715c47dda9350635aa3ea3e969e5deb152e52e33614a6a6480",
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py":
        "d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16",
}


def _stage() -> Path:
    if not LOCAL_PATHS.is_file():
        pytest.skip("ignored CLEAN3R4 local aliases unavailable")
    stage = audit.default_stage_root(REPO)
    if not stage.is_dir():
        pytest.skip("external LC02 stage unavailable")
    return stage


def _sources() -> dict[str, Path]:
    return audit.payload_sources(REPO)


def _json(relative: str) -> dict:
    return json.loads(_sources()[relative].read_text(encoding="utf-8"))


def _yaml(relative: str) -> dict:
    return yaml.safe_load(_sources()[relative].read_text(encoding="utf-8"))


def _csv(relative: str) -> list[dict[str, str]]:
    with _sources()[relative].open("rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_exact_outcome_b_payload_set_and_counts() -> None:
    sources = _sources()
    assert set(sources) == set(y0_y3._allowed_y4a_append_files())
    assert len(sources) == audit.Y4A_APPEND_FILE_COUNT == 32
    assert len(y0_y3._allowed_y4a_pass_append_files()) == 30
    assert audit.FINAL_STAGE_FILE_COUNT == 79
    assert audit.validate_payload(REPO) == []
    assert not any(path.is_symlink() for path in sources.values())
    assert not any(path.suffix.lower() in {".pdf", ".zip"} for path in sources.values())

    source_registry = _csv(
        f"{audit.Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y4A_SOURCE_REGISTRY.csv"
    )
    source_fields = set(source_registry[0])
    assert {
        "source_id", "title", "authors", "doi", "version", "pages", "bytes",
        "sha256", "license", "access_status", "endpoint", "equation_relevance",
        "repository_tree_oid",
    }.issubset(source_fields)
    required_sources = {
        "YIN2023_VOR", "YIN2023_V2", "YIN2023_OFFICIAL_HTML",
        "YIN2023_OFFICIAL_HTML_JINA_CAPTURE", "YIN2023_VERSION_NOTES",
        "YIN2023_SUPPLEMENT_SEARCH", "YIN2023_PEER_REVIEW_RECORD",
        "YIN2023_AUTHOR_RESPONSE_DIRECT", "YIN2023_AUTHOR_RESPONSE_JINA_CAPTURE",
        "YIN2023_DATA_CODE_STATEMENT", "YIN_AUTHOR_INSTITUTION_REPOSITORY_SEARCH",
        "YANG_HE_XU_2001", "YANG_HE_XU_2001_AUTHOR_UPLOAD",
        "YANG_CHENG_SHUM_TAPLEY_1999", "YANG_CHENG_SHUM_TAPLEY_1999_AUTHOR_UPLOAD",
        "YANG_SONG_XU_2002", "YANG_SONG_XU_2002_AUTHOR_UPLOAD",
        "YANG_1994_DEPENDENT_OBSERVATIONS", "YIN_REF35_JIANG2020",
        "YIN_REF36_YANG2013", "YIN_REF37_JIANG2021", "JIANG2021_NCWU_METADATA",
        "YIN_REF38_KNIGHT2009", "KNIGHT2009_UNSW_METADATA",
        "KNIGHT2009_RESEARCHGATE_AUTHOR_UPLOAD",
        "YIN_REF39_NIU2022", "NIU_TCRTKINS_REPOSITORY",
        "NIU_TCRTKINS_FUSION_CPP", "SDUST_CN117647251A",
        "KFGINS_ACKNOWLEDGED_BASE", "KFGINS_INSMECH_FROZEN_Y0_Y3",
    }
    assert required_sources.issubset({row["source_id"] for row in source_registry})

    symbol_rows = _csv(
        f"{audit.Y4A_ROOT}/01_SYMBOL_RECONCILIATION/"
        "YIN2023_UNRESOLVED_SYMBOL_REGISTRY.csv"
    )
    assert {
        "symbol", "paper_equation", "paper_wording", "dimension", "unit",
        "source_definition", "candidate_interpretations", "selected_interpretation",
        "selection_evidence", "remaining_ambiguity",
    }.issubset(symbol_rows[0])
    assert {
        "L_k", "Z_k", "V_hat_k", "bar_V_k", "Delta_X_tilde_k", "e_V_i",
        "bar_A_k", "bar_A_(Xhat_k)", "bar_A(tilde_V_i)", "w(tilde_V_i)",
        "R_i", "Omega",
        "alpha_k", "v/omega", "ω (omega)", "ϖ (varpi)", "c", "k", "k0", "k1",
        "V_k", "A_k", "A(e_V_i)",
    } == {row["symbol"] for row in symbol_rows}
    symbols = {row["symbol"]: row for row in symbol_rows}
    assert symbols["w(tilde_V_i)"]["paper_equation"] == "Eq.11"
    assert "LATIN" in symbols["w(tilde_V_i)"]["paper_wording"]
    assert "Eq.10 weighting function enters Eq.11" in (
        symbols["w(tilde_V_i)"]["selection_evidence"]
    )
    assert symbols["V_k"]["selected_interpretation"] == (
        "COMPATIBILITY_ALIAS_TO_bar_V_k_NOT_V_hat_k"
    )
    assert symbols["A_k"]["selected_interpretation"] == (
        "COMPATIBILITY_ALIAS_TO_bar_A_k"
    )
    assert symbols["A(e_V_i)"]["selected_interpretation"] == (
        "COMPATIBILITY_ALIAS_TO_bar_A(tilde_V_i)"
    )
    for name in ("V_k", "A_k", "A(e_V_i)"):
        assert symbols[name]["provenance"] == "PAPER_DERIVED_COMPATIBILITY_ERRATA"
    joined_payload = "\n".join(path.read_text(encoding="utf-8") for path in sources.values())
    assert "xueshushe.cn" not in joined_payload


def test_source_cache_and_registry_identities_are_exact() -> None:
    rows = _csv(
        f"{audit.Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y4A_SOURCE_REGISTRY.csv"
    )
    by_id = {row["source_id"]: row for row in rows}
    assert by_id["YIN2023_VOR"]["sha256"] == audit.SOURCE_FILES["yin2023_vor_28p.pdf"]["sha256"]
    assert by_id["YIN2023_V2"]["sha256"] == audit.SOURCE_FILES["yin2023_v2_24p.pdf"]["sha256"]
    assert by_id["YIN2023_AUTHOR_RESPONSE_JINA_CAPTURE"]["hash_scope"] == (
        "JINA_UTF8_MARKDOWN_TRANSPORT_BYTES_NOT_ORIGINAL_PDF"
    )
    assert by_id["YIN2023_AUTHOR_RESPONSE_JINA_CAPTURE"]["sha256"] == (
        audit.SOURCE_FILES["yin2023_peer_review_author_response_jina.md"]["sha256"]
    )
    assert by_id["YIN2023_AUTHOR_RESPONSE_JINA_CAPTURE"]["endpoint"] == (
        "https://r.jina.ai/http://susy.mdpi.com/user/review/displayFile/41299766/"
        "4MoqTeV7?file=author-coverletter%26report=31242108"
    )
    assert by_id["YIN2023_OFFICIAL_HTML_JINA_CAPTURE"]["sha256"] == (
        audit.SOURCE_FILES["yin2023_official_article_jina.md"]["sha256"]
    )
    assert by_id["YIN2023_OFFICIAL_HTML_JINA_CAPTURE"]["bytes"] == "104971"
    assert by_id["YIN2023_SUPPLEMENT_SEARCH"]["closure_effect"] == (
        "NO_ATTRIBUTABLE_SUPPLEMENT_FOUND"
    )
    assert by_id["YANG_HE_XU_2001"]["doi"] == "10.1007/s001900000157"
    assert by_id["YANG_SONG_XU_2002"]["doi"] == "10.1007/s00190-002-0256-7"
    assert by_id["YANG_CHENG_SHUM_TAPLEY_1999"]["doi"] == "10.1007/s001900050252"
    assert by_id["YANG_1994_DEPENDENT_OBSERVATIONS"]["doi"] == "10.1007/BF03655325"
    assert by_id["YIN_REF36_YANG2013"]["title"] == (
        "Main Progress of Adaptively Robust Filter with Applications in Navigation"
    )
    assert by_id["YIN_REF36_YANG2013"]["pages"] == "7"
    assert by_id["YIN_REF37_JIANG2021"]["pages"] == "11"
    assert "EXCLUSIVE_LICENCE_TO_SPRINGER" in by_id["YIN_REF37_JIANG2021"]["license"]
    assert by_id["YIN_REF35_JIANG2020"]["pages"] == "1"
    assert by_id["YIN_REF35_JIANG2020"]["endpoint"] == (
        "https://doi.org/10.11947/j.AGCS.2020.20190429"
    )
    assert by_id["YIN_REF38_KNIGHT2009"]["endpoint"].startswith("https://www.cambridge.org/")
    assert by_id["KNIGHT2009_UNSW_METADATA"]["endpoint"].startswith("https://research.unsw.edu.au/")
    assert by_id["KNIGHT2009_RESEARCHGATE_AUTHOR_UPLOAD"]["license"] == (
        "REUSE_LICENSE_UNSTATED"
    )
    assert by_id["YIN_REF39_NIU2022"]["provenance_class"] == "CITED_SOURCE_CANDIDATE"
    assert by_id["NIU_TCRTKINS_FUSION_CPP"]["bytes"] == "37929"
    assert by_id["NIU_TCRTKINS_REPOSITORY"]["version"] == (
        "commit 13e8fa1a988f673c43af70746de1bcbeb1ec2ea3"
    )
    assert by_id["NIU_TCRTKINS_REPOSITORY"]["sha256"] == "NOT_APPLICABLE"
    assert by_id["NIU_TCRTKINS_REPOSITORY"]["repository_tree_oid"] == (
        "00159f613872e6e9286ddfb5bead2c11b8d6c82f"
    )
    assert by_id["SDUST_CN117647251A"]["relationship"] == "POST_PUBLICATION_RELATED_NOT_EXACT"
    assert by_id["SDUST_CN117647251A"]["sha256"] == audit.SOURCE_FILES["CN117647251A.pdf"]["sha256"]
    assert by_id["KFGINS_ACKNOWLEDGED_BASE"]["endpoint"].endswith(
        "/src/kf-gins/gi_engine.cpp"
    )
    assert by_id["KFGINS_INSMECH_FROZEN_Y0_Y3"]["endpoint"].endswith(
        "/src/kf-gins/insmech.cpp"
    )
    standardizer_sources = {
        row["source"] for row in _csv(
            f"{audit.Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_STANDARDIZED_RESIDUAL_SOURCE_MAP.csv"
        )
    }
    assert {
        "Knight 2009", "Yang-Cheng-Shum-Tapley 1999", "Yang-He-Xu 2001",
        "Yang-Song-Xu 2002", "Yang 1994", "Niu 2022", "TCRTKINS Fusion.cpp",
    }.issubset(standardizer_sources)
    zero_sources = {
        row["source"] for row in _csv(
            f"{audit.Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_ZERO_WEIGHT_POLICY_SOURCE_MAP.csv"
        )
    }
    assert {"Yang-Cheng-Shum-Tapley 1999", "Yang-Song-Xu 2002", "Niu 2022"}.issubset(
        zero_sources
    )

    if not SOURCE_CACHE.is_dir():
        pytest.skip(SOURCE_CACHE_SKIP_REASON)
    observed = audit.verify_source_cache(SOURCE_CACHE)
    assert observed == audit.SOURCE_FILES
    assert observed["yin2023_vor_28p.pdf"]["pages"] == 28
    assert observed["yin2023_v2_24p.pdf"]["pages"] == 24
    assert observed["niu2022_rs14102449.pdf"]["pages"] == 34
    assert observed["CN117647251A.pdf"]["pages"] == 21
    assert observed["yin2023_peer_review_author_response_jina.md"]["bytes"] == 18305
    assert observed["yin2023_official_article_jina.md"]["bytes"] == 104971


def test_original_47_file_manifest_is_exact_and_immutable() -> None:
    baseline_path = _sources()[
        f"{audit.Y4A_ROOT}/00_SOURCE_REGISTRY/YIN2023_Y0_Y3_IMMUTABILITY_BASELINE.sha256"
    ]
    assert audit.sha256_file(baseline_path) == audit.ORIGINAL_MANIFEST_SHA256
    baseline = audit.parse_baseline(baseline_path)
    assert len(baseline) == audit.ORIGINAL_FILE_COUNT == 47
    assert set(baseline) == set(y0_y3._required_stage_files())
    stage = _stage()
    assert audit.verify_original_files(stage, baseline) == baseline


def test_L_Z_and_AKF_remain_fail_closed() -> None:
    assert audit.ALLOWED_LZ_DECISIONS == frozenset({
        "SOURCE_CLOSED_TYPOGRAPHICAL_ALIAS",
        "DISTINCT_SYMBOLS_WITH_CLOSED_RELATION",
        "UNRESOLVED",
    })
    assert audit.ALLOWED_AKF_DECISIONS == frozenset({
        "PAPER_DIRECT_CLOSED",
        "CITED_STANDARD_COMPLETION_CLOSED",
        "MULTIPLE_PLAUSIBLE_COMPLETIONS",
        "UNRESOLVED",
    })
    lk = _json(f"{audit.Y4A_ROOT}/01_SYMBOL_RECONCILIATION/YIN2023_LK_ZK_DECISION.json")
    assert set(lk["allowed_decision_enum"]) == set(audit.ALLOWED_LZ_DECISIONS)
    assert lk["decision"] == "UNRESOLVED"
    assert lk["L_k_equals_Z_k"] is None
    assert lk["permitted_policy_provenance"] == "PAPER_DERIVED_POLICY_BASELINE"
    assert lk["hard_gate_pass"] is False

    akf = _yaml(f"{audit.Y4A_ROOT}/02_AKF_CLOSURE/YIN2023_AKF_FINAL_CONTRACT.yaml")
    assert akf["paper_direct"]["threshold_k"] == 1.0
    assert akf["semantic_checks"]["dimensionally_coherent"] is False
    assert akf["source_reconciliation"]["patent_competing_description"] == "COVARIANCE_OF_MEASUREMENT_VECTOR"
    assert akf["paper_direct"]["statistic"] == (
        "Delta_X_tilde_k = sqrt((bar_V_k^T bar_V_k)/tr(P_(bar_V_k)))"
    )
    assert akf["paper_direct"]["residual_for_statistic"] == (
        "bar_V_k = H_k Xhat_k - Z_k"
    )
    assert akf["paper_direct"]["P_bar_V_k_definition_printed"] == (
        "P_(bar_V_k) = Phi_k P_(Xhat_(k-1)) Phi^T + Q_k"
    )
    assert akf["paper_direct"]["right_Phi_index_as_printed"] == "NONE_EXPLICIT"
    assert akf["paper_derived_candidate_mapping_not_selected"]["paper_direct"] is False
    assert akf["paper_derived_candidate_mapping_not_selected"]["selected"] is False
    assert akf["paper_direct"]["statistic_residual_state_symbol"] == "Xhat_k"
    assert akf["paper_direct"]["statistic_residual_state_stage"] is None
    factor = akf["paper_direct"]["adaptive_factor"]
    assert factor["paper_condition_abs_Delta_X_tilde_le_k"] == 1.0
    assert factor["paper_condition_abs_Delta_X_tilde_gt_k"] == "k/|Delta_X_tilde_k|"
    assert factor["absolute_value_glyph_preserved"] is True
    assert akf["semantic_checks"]["same_prior_with_RKF_defined_by_yin_2023"] is True
    assert akf["closure"]["AKF_statistic_update_unique"] is False
    assert akf["closure"]["reproduction_level"] == "FAITHFUL_MODULE_REPRODUCTION"
    decision = _json(f"{audit.Y4A_ROOT}/02_AKF_CLOSURE/YIN2023_AKF_CLOSURE_DECISION.json")
    assert set(decision["allowed_decision_enum"]) == set(audit.ALLOWED_AKF_DECISIONS)
    assert decision["decision"] == "MULTIPLE_PLAUSIBLE_COMPLETIONS"


def test_standardizer_iggiii_and_zero_policy_are_not_silently_completed() -> None:
    standardizer = _yaml(
        f"{audit.Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_STANDARDIZED_RESIDUAL_CONTRACT.yaml"
    )
    unresolved = standardizer["unresolved"]
    assert unresolved and all(value is None for value in unresolved.values())
    assert standardizer["cited_candidate_niu2022"]["formula"] == "s_i/sqrt(S_ii), S=H P^- H^T+R"
    assert standardizer["author_response"]["L_k_equated_to_Z_k"] is False
    assert standardizer["author_response"]["standardizer_equation_supplied"] is False
    assert standardizer["paper_direct"]["equation_9_objective"] == (
        "Omega = bar_V_k^T bar_A_k bar_V_k + alpha_k bar_V_k^T "
        "bar_A_(Xhat_k) bar_V_k = min"
    )
    assert standardizer["paper_direct"]["equation_9_uses_V_hat_k"] is False
    assert unresolved["V_hat_k_equals_bar_V_k"] is None
    assert unresolved["bar_A_Xhat_k_definition"] is None
    assert standardizer["closure"]["standardized_residual_unique"] is False

    igg = _yaml(
        f"{audit.Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_IGGIII_EQUIVALENT_WEIGHT_CONTRACT.yaml"
    )
    assert igg["thresholds"] == {"k0": 1.15, "k1": 4.45}
    assert igg["scalar_weight"]["paper_component_symbol"] == (
        "ω (U+03C9 GREEK SMALL LETTER OMEGA)"
    )
    assert ")^3" in igg["scalar_weight"]["paper_printed_middle"]
    assert "|tilde_V_i|" in igg["scalar_weight"]["paper_printed_middle"]
    assert igg["scalar_weight"]["effective_zero_domain"] == "|tilde_V_i|>=k1"
    assert igg["author_response"]["general_matrix_assembly_supplied"] is False
    assert igg["author_response"]["distinct_base_and_equivalent_symbols_supplied"] is False
    eq11 = igg["equation_11_paper_direct"]
    assert eq11["overloaded_symbol"] == "bar_A(tilde_V_i)"
    assert eq11["lhs_and_low_middle_rhs_use_same_symbol"] is True
    assert eq11["middle_multiplier_symbol"] == (
        "w(tilde_V_i) (LATIN SMALL LETTER W)"
    )
    assert eq11["middle_branch"] == (
        "bar_A(tilde_V_i) = bar_A(tilde_V_i) * w(tilde_V_i)"
    )
    assert eq11["distinct_from_equation_10_omega_glyph"] is True
    assert eq11["prose_identity"] == "bar_A(tilde_V_i) = R_i^-1"
    assert eq11["unique_base_equivalent_split"] is False
    assert igg["author_response"]["equation_10_weight_enters_equation_11"] is True
    assert igg["author_response"]["glyphs_equated_by_source"] is False
    derived_split = igg["conventional_base_equivalent_split_candidate"]
    assert derived_split["provenance"] == "PAPER_DERIVED_POLICY_BASELINE"
    assert derived_split["selected"] is False
    assert igg["closure"]["scalar_IGGIII_unique"] is True
    assert igg["closure"]["IGGIII_matrix_construction_unique"] is False

    zero = _yaml(
        f"{audit.Y4A_ROOT}/03_RKF_CLOSURE/YIN2023_ZERO_WEIGHT_POLICY_CONTRACT.yaml"
    )
    assert zero["paper_path"]["scalar_weight"] == 0.0
    assert zero["paper_path"]["printed_high_condition"] == "|tilde_V_i|>4.45"
    assert zero["paper_path"]["effective_zero_condition"] == "|tilde_V_i|>=4.45"
    assert zero["paper_path"]["directly_executable"] is False
    assert zero["cited_candidate_niu_tcrtkins"]["uniquely_closes_yin"] is False
    assert zero["limit_results"]["correlated_case_path_independent"] is False
    assert zero["closure"]["zero_weight_policy_unique"] is False


def test_raekf_eq13_is_closed_but_full_chain_is_not() -> None:
    contract = _yaml(f"{audit.Y4A_ROOT}/04_RAEKF_CLOSURE/YIN2023_RAEKF_FINAL_CONTRACT.yaml")
    assert contract["fusion_paper_direct"]["controlling_statistic"] == "Delta_X_tilde_k"
    assert contract["fusion_paper_direct"]["paper_fusion_symbol"] == (
        "ϖ (U+03D6 GREEK PI SYMBOL; varpi)"
    )
    assert contract["fusion_paper_direct"]["explicitly_distinct_from_IGGIII_omega_U_03C9"] is True
    assert contract["fusion_paper_direct"]["varpi_when_abs_Delta_X_tilde_le_c"] == 0.85
    assert contract["fusion_paper_direct"]["varpi_when_abs_Delta_X_tilde_gt_c"] == 0.15
    assert contract["fusion_paper_direct"]["absolute_value_glyph_preserved"] is True
    assert contract["fusion_paper_direct"]["equation_13_formula_resolved"] is True
    assert contract["fusion_paper_direct"]["same_unmodified_prior_for_both_branches"] is True
    assert contract["fusion_paper_direct"]["branch_results_computed_separately_before_fusion"] is True
    assert contract["fusion_execution_unresolved"]["fusion_occurs_before_error_feedback"] is None
    assert contract["fusion_execution_unresolved"]["P_rk_uniquely_executable"] is False
    robust = contract["branches"]["robust"]
    assert robust["V_hat_k_versus_bar_V_k_closed"] is False
    assert robust["equation_9_bar_A_Xhat_k_defined"] is False
    assert robust["equation_11_scalar_equivalent_information_mapping_unique"] is False
    assert contract["post_publication_patent_boundary"]["usable_to_backfill_yin_2023"] is False
    assert contract["closure"]["RAEKF_fusion_reset_unique"] is False
    assert contract["closure"]["formal_lc02_admission"] is False
    assert contract["closure"]["production_solver_authorized"] is False
    feedback = _json(
        f"{audit.Y4A_ROOT}/04_RAEKF_CLOSURE/YIN2023_RAEKF_FEEDBACK_RESET_DECISION.json"
    )
    assert feedback["same_prior_for_both_branches_closed_in_yin_2023"] is True
    assert feedback["separate_branch_results_before_fusion_closed"] is True
    assert feedback["cross_covariance_role"] == (
        "EQ13_PROBABILISTIC_INTERPRETATION_LIMITATION_NOT_EXECUTABLE_EQ13_AMBIGUITY"
    )


def test_deterministic_oracles_recompute_byte_semantics() -> None:
    path = _sources()[f"{audit.Y4A_ROOT}/05_MATHEMATICAL_ORACLES/Y4A_LINEAR_ORACLE_RESULTS.csv"]
    assert audit._read_oracle_csv(path) == audit.linear_oracle_rows()
    rows = audit.linear_oracle_rows()
    assert len(rows) == audit.ORACLE_COUNT == 28
    assert all(row["passed"] == "true" for row in rows)
    ids = {row["oracle_id"] for row in rows}
    assert audit.REQUIRED_ORACLE_IDS.issubset(ids)
    assert next(row for row in rows if row["oracle_id"] == "STANDARDIZER_WEIGHT_DIVERGENCE")["observed"] == "0.547684953298"
    assert next(row for row in rows if row["oracle_id"] == "ZERO_WEIGHT_CORRELATED_PATH_DEPENDENCE")["observed"] == "0.0927096604992"
    zero_policy = next(row for row in rows if row["oracle_id"] == "ZERO_WEIGHT_NO_UNIQUE_YIN_POLICY")
    assert zero_policy["observed"] == "2"
    assert zero_policy["expected"] == (
        ">=2_EXECUTABLE_COMPLETIONS_PLUS_1_NONEXECUTABLE_PRINTED_PATH"
    )
    unit = next(row for row in rows if row["oracle_id"] == "DIAGONAL_R_UNIT_EXPONENT_M2")
    assert unit["claim"] == (
        "computed unit exponent 2*PDOP(0)+Q(0)+2*r(1) equals square metres"
    )
    assert unit["observed"] == "2"
    inlier = next(row for row in rows if row["oracle_id"] == "IGGIII_INLIER_INFORMATION_NOMINAL")
    assert "PAPER_DERIVED" in inlier["claim"]
    assert "unselected PAPER_DERIVED candidate" in inlier["meaning"]
    assert "Greek omega" in inlier["meaning"]
    assert "Latin w" in inlier["meaning"]
    assert "author response" in inlier["meaning"]
    summary = _json(f"{audit.Y4A_ROOT}/05_MATHEMATICAL_ORACLES/Y4A_ORACLE_SUMMARY.json")
    assert summary["source_uniqueness_proved"] is False
    assert summary["oracle_count"] == summary["passed_count"] == 28
    assert audit.REQUIRED_ORACLE_IDS.issubset(set(summary["required_identity_ids"]))
    assert summary["BY2_open_count"] == 0


def test_outcome_b_rubric_levels_and_gates_are_literal() -> None:
    rubric = _yaml(
        f"{audit.Y4A_ROOT}/06_ADMISSION_DECISION/YIN2023_FORMAL_ADMISSION_RUBRIC.yaml"
    )
    expected = {
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
    assert {key: value["pass"] for key, value in rubric["hard_gates"].items()} == expected
    assert rubric["terminal_status"] == audit.TERMINAL_STATUS
    assert rubric["branch_reproduction_levels"] == {
        "YIN2023_EKF": "FAITHFUL_ALGORITHM_REPRODUCTION",
        "YIN2023_AKF": "FAITHFUL_MODULE_REPRODUCTION",
        "YIN2023_RKF": "PAPER_DERIVED_POLICY_BASELINE",
        "YIN2023_RAEKF": "PAPER_DERIVED_POLICY_BASELINE",
    }
    assert rubric["formal_lc02_admission"] is False
    assert rubric["implementation_authorized"] is False
    assert rubric["production_solver_authorized"] is False
    assert rubric["C00_authorized"] is False
    assert rubric["representative_cases_authorized"] is False
    assert rubric["comparison_run_authorized"] is False
    forecast = _sources()[
        f"{audit.Y4A_ROOT}/06_ADMISSION_DECISION/LC02_C00_MECHANISM_ACTIVATION_FORECAST.md"
    ].read_text(encoding="utf-8")
    for literal in ("1,510", "Q=1", "1.13", "1.74", "No C00 run occurred"):
        assert literal in forecast
    assert "per-axis covariance variation" in forecast
    assert "separately frozen real quality-degradation case" in forecast
    assert "clearly labelled and separately frozen semisynthetic" in forecast
    assert "No case may be designed or selected from final error or trace" in forecast
    assert "exactly four user-accepted frozen Y0–Y3 input-contract facts" in forecast


def test_forbidden_access_and_execution_counters_are_zero() -> None:
    audit_json = _json(
        f"{audit.Y4A_ROOT}/06_ADMISSION_DECISION/Y4A_FORBIDDEN_ACCESS_AUDIT.json"
    )
    assert all(value == 0 for value in audit_json["forbidden_access_counters"].values())
    assert all(value == 0 for value in audit_json["execution_counters"].values())
    assert audit_json["administrative_validation_inventory"] == (
        audit.ADMINISTRATIVE_VALIDATION_INVENTORY
    )
    assert audit_json["allowed_scientific_source_access"][
        "public_author_upload_full_text_inspected_count"
    ] == 4
    assert audit_json["allowed_scientific_source_access"][
        "request_only_author_upload_metadata_inspected_count"
    ] == 1
    assert "attributable_cited_source_author_uploads_inspected" not in (
        audit_json["allowed_scientific_source_access"]
    )
    fact_reuse = audit_json["authorized_frozen_Y0_Y3_input_contract_fact_reuse"]
    assert fact_reuse["fact_count"] == 4
    assert fact_reuse["facts"] == audit.AUTHORIZED_FROZEN_INPUT_CONTRACT_FACT_REUSE["facts"]
    assert fact_reuse["new_Y0_Y3_scientific_content_open_count"] == 0
    assert fact_reuse["old_performance_runtime_trace_reuse_count"] == 0
    assert audit_json["access_semantics"]["frozen_47_original_files_were_content_read_for_integrity_hashing"] is True
    assert audit_json["access_semantics"]["frozen_36_original_structured_files_were_parsed_for_format_validation"] is True
    assert audit_json["access_semantics"]["augmented_58_structured_files_were_parsed_by_validator"] is True
    assert audit_json["access_semantics"]["canonical_2_files_were_read_for_sha256_only"] is True
    assert audit_json["access_semantics"]["LC01_or_Canonical_scientific_execution_or_content_use"] is False
    assert audit_json["access_semantics"]["scientific_access_counter_scope"] == (
        "NEW_Y4A_SCIENTIFIC_OPENS_ONLY"
    )
    assert audit_json["online_provenance"]["trace_used_online"] is False
    assert audit_json["online_provenance"]["old_runtime_input_count"] == 0
    assert audit_json["forbidden_access_pass"] is True
    for relative, expected in CANONICAL_HASHES.items():
        path = REPO / relative
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        assert audit_json["canonical_untracked_files"][relative] == expected


def test_status_code_hash_terminal_and_false_authorizations() -> None:
    status = _json("11_REPORT/LC02_Y4A_STATUS.json")
    assert status["terminal_status"] == audit.TERMINAL_STATUS
    assert status["start_head"] == audit.START_HEAD == status["end_head"]
    assert status["end_head_semantics"] == "PRECOMMIT_ARTIFACT_BUILD_ANCHOR"
    assert status["audit_code_hash"] == audit.sha256_file(Path(audit.__file__))
    assert status["formal_lc02_admission"] is False
    assert status["implementation_authorized"] is False
    assert status["production_solver_authorized"] is False
    assert status["C00_authorized"] is False
    assert status["representative_cases_authorized"] is False
    assert status["comparison_run_authorized"] is False
    assert all(value == 0 for value in status["scientific_access_counters"].values())
    assert all(value == 0 for value in status["execution_counters"].values())
    assert status["administrative_validation_inventory"] == (
        audit.ADMINISTRATIVE_VALIDATION_INVENTORY
    )
    assert status["authorized_frozen_Y0_Y3_input_contract_fact_reuse"] == (
        audit.AUTHORIZED_FROZEN_INPUT_CONTRACT_FACT_REUSE
    )
    assert status["source_access_counts"] == audit.SOURCE_ACCESS_COUNTS
    assert status["scientific_access_counter_semantics"] == (
        "NEW_Y4A_SCIENTIFIC_OPENS_ONLY"
    )
    assert status["immutability"]["original_manifest_sha256"] == audit.ORIGINAL_MANIFEST_SHA256
    assert status["durable_validation"] == audit.EXPECTED_DURABLE_VALIDATION
    history = status["uncommitted_draft_repair_history"]
    assert history["initial_draft_32_file_aggregate_sha256"] == (
        audit.INITIAL_DRAFT_Y4A_MANIFEST_SHA256
    )
    assert history["first_correction_32_file_aggregate_sha256"] == (
        audit.FIRST_CORRECTION_Y4A_MANIFEST_SHA256
    )
    assert history["second_correction_32_file_aggregate_sha256"] == (
        audit.SECOND_CORRECTION_Y4A_MANIFEST_SHA256
    )
    assert history["third_correction_32_file_aggregate_sha256"] == (
        audit.THIRD_CORRECTION_Y4A_MANIFEST_SHA256
    )


def test_scratch_payload_exclusive_write_and_special_entry_guards(tmp_path: Path) -> None:
    sources = _sources()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    audit._build_scratch_payload(scratch, sources)
    assert audit._stage_entry_errors(scratch, set(sources)) == []
    with pytest.raises(FileExistsError):
        audit._exclusive_write(scratch / next(iter(sources)), b"replacement forbidden")

    if hasattr(os, "mkfifo"):
        fifo = scratch / "unexpected.fifo"
        os.mkfifo(fifo)
        errors = audit._stage_entry_errors(scratch, set(sources))
        assert any("special filesystem entry forbidden: unexpected.fifo" in item for item in errors)
        fifo.unlink()

    link = scratch / "unexpected.link"
    link.symlink_to(scratch / next(iter(sources)))
    assert any("symlink forbidden: unexpected.link" in item for item in audit._stage_entry_errors(scratch, set(sources)))


def test_augmented_stage_exact_union_parity_and_no_special_outputs() -> None:
    stage = _stage()
    expected = set(y0_y3._required_stage_files()) | set(y0_y3._allowed_y4a_append_files())
    actual = {
        str(path.relative_to(stage))
        for path in stage.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if actual == set(y0_y3._required_stage_files()):
        pytest.skip("Y4A append-only publication not yet performed")
    assert actual == expected
    assert len(actual) == 79
    assert audit.validate_augmented_stage(stage, REPO) == []
    assert y0_y3.validate_stage(stage) == []
    for relative, source in _sources().items():
        assert audit.sha256_file(source) == audit.sha256_file(stage / relative)
    entries = list(stage.rglob("*"))
    assert not any(path.is_symlink() for path in entries)
    assert not any(not path.is_file() and not path.is_dir() for path in entries)
    assert not any(path.suffix.lower() in {".pdf", ".zip"} for path in entries if path.is_file())


def test_old_replacement_is_ineligible_after_y4a_append() -> None:
    stage = _stage()
    actual = {str(path.relative_to(stage)) for path in stage.rglob("*") if path.is_file()}
    if actual == set(y0_y3._required_stage_files()):
        pytest.skip("Y4A append-only publication not yet performed")
    clean_root = Path(y0_y3.load_local_paths(LOCAL_PATHS)["clean_root"])
    with pytest.raises(ValueError, match="not the exact known 47-file audit layout"):
        y0_y3._prepare_exact_stage_target(stage, clean_root, replace_existing_audit_stage=True)


def test_exact_no_arg_validate_only_cli() -> None:
    stage = _stage()
    actual = {str(path.relative_to(stage)) for path in stage.rglob("*") if path.is_file()}
    if actual == set(y0_y3._required_stage_files()):
        pytest.skip("Y4A append-only publication not yet performed")
    completed = subprocess.run(
        [sys.executable, "scripts/paper_rebuild/audit_lc02_yin2023_y4a.py", "--validate-only"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["validation_errors"] == []


def test_tracked_scope_has_no_absolute_raw_root_or_production_filter() -> None:
    tracked = [
        REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/lc02_y4a_reproducibility_closure.py",
        REPO / "scripts/paper_rebuild/audit_lc02_yin2023_y4a.py",
        REPO / "tests/paper_rebuild/test_lc02_yin2023_y4a.py",
        *_sources().values(),
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in tracked)
    assert "/mnt" + "/g/" not in joined
    assert "/home" + "/kaiwen/" not in joined
    assert "RAW" + "_ROOT" not in joined
    source = (REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/lc02_y4a_reproducibility_closure.py").read_text()
    assert "by2_algorithm_runner" not in source
    assert "run_filter" not in source
    assert "run_solver" not in source
    assert "EVAL_NAV" not in source


def test_git_head_is_precommit_or_exact_authorized_one_commit_descendant() -> None:
    assert audit.AUTHORIZED_COMMIT_SUBJECT == "Close Yin 2023 RAEKF reproduction semantics"
    assert audit.authorized_git_state(REPO) in {
        "PRECOMMIT_START_HEAD", "AUTHORIZED_ONE_COMMIT_DESCENDANT"
    }
