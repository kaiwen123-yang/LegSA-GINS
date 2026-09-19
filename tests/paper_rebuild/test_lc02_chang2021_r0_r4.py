from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature.lc02_chang2021_audit import (
    AUTHORIZED_COMMIT_SUBJECT,
    CANONICAL_HASHES,
    EXPECTED_BRANCH_LEVELS,
    EXPECTED_CONFIG_ARTIFACTS,
    EXPECTED_DOC_ARTIFACTS,
    EXPECTED_EXPERIMENT_SEMANTICS,
    EXPECTED_FIGURE_SEMANTICS,
    EXPECTED_GATE_RESULTS,
    EXPECTED_ARTIFACTS,
    EXPECTED_HEAD,
    EXPECTED_POSTCOMMIT_PATHS,
    PAPER_BYTES,
    PAPER_PAGES,
    PAPER_SHA256,
    PREVIOUS_ARTIFACTS,
    STAGE08_FILE_COUNT,
    STAGE08_MANIFEST_SHA256,
    STAGE08_RELATIVE,
    STAGE09_RELATIVE,
    STAGE09_REPAIR_PREIMAGE_SHA256,
    STAGE09_REPAIR_MODE,
    TERMINAL_STATUS,
    audit_by2_inputs,
    collect_tracked_payload,
    load_local_paths,
    normalized_tree_manifest,
    payload_aggregate_sha256,
    publish_stage,
    read_stage_payload,
    repo_root,
    sha256_file,
    validate_payload,
    validate_postcommit_scope,
    validate_stage,
    verify_task_head,
    verify_paper,
)


ROOT = repo_root()
SUFFIX = Path("paper_rebuild/horizontal_literature/lc02_chang2021")
CONFIG = ROOT / "configs" / SUFFIX
DOCS = ROOT / "docs" / SUFFIX
LOCAL_PATHS = ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"


def _json(relative: str) -> dict:
    return json.loads((CONFIG / relative).read_text(encoding="utf-8"))


def _yaml(relative: str) -> dict:
    return yaml.safe_load((CONFIG / relative).read_text(encoding="utf-8"))


def _csv(relative: str) -> list[dict[str, str]]:
    with (CONFIG / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_start_head_and_canonical_files_are_preserved() -> None:
    head = verify_task_head(ROOT)
    assert head["task_start_head"] == EXPECTED_HEAD
    assert head["mode"] in {
        "UNCOMMITTED_ARTIFACT_BUILD_AT_TASK_START_HEAD",
        "AUTHORIZED_EXACT_ONE_COMMIT_DESCENDANT",
    }
    if head["mode"] == "AUTHORIZED_EXACT_ONE_COMMIT_DESCENDANT":
        assert head["parent"] == EXPECTED_HEAD
        assert head["subject"] == AUTHORIZED_COMMIT_SUBJECT
    for relative, expected in CANONICAL_HASHES.items():
        assert sha256_file(ROOT / relative) == expected


def test_postcommit_scope_is_exactly_thirty_seven_artifacts_plus_three_support_files() -> None:
    assert len(EXPECTED_CONFIG_ARTIFACTS) == 26
    assert len(EXPECTED_DOC_ARTIFACTS) == 11
    assert len(EXPECTED_POSTCOMMIT_PATHS) == 40
    assert validate_postcommit_scope(EXPECTED_POSTCOMMIT_PATHS) == (
        EXPECTED_POSTCOMMIT_PATHS
    )
    with pytest.raises(ValueError, match="changed-path set mismatch"):
        validate_postcommit_scope(EXPECTED_POSTCOMMIT_PATHS - {next(iter(EXPECTED_POSTCOMMIT_PATHS))})
    with pytest.raises(ValueError, match="changed-path set mismatch"):
        validate_postcommit_scope({*EXPECTED_POSTCOMMIT_PATHS, "unexpected.txt"})


def test_tracked_payload_is_exact_and_structurally_valid() -> None:
    payload = collect_tracked_payload(ROOT)
    assert set(payload) == EXPECTED_ARTIFACTS
    result = validate_payload(payload)
    assert result == {
        "artifact_count": 37,
        "structured_artifact_count": 26,
        "terminal_status": TERMINAL_STATUS,
    }


def test_paper_identity_and_full_review_registry() -> None:
    equations = _csv("02_FULL_PAPER_REVIEW/LC02_CHANG_EQUATION_REGISTRY.csv")
    figures = _csv("02_FULL_PAPER_REVIEW/LC02_CHANG_FIGURE_REGISTRY.csv")
    assert [int(row["equation"]) for row in equations] == list(range(1, 31))
    assert {
        int(row["figure"]): (
            int(row["paper_page"]),
            row["category"],
            row["current_evidence_role"],
        )
        for row in figures
    } == EXPECTED_FIGURE_SEMANTICS
    assert all(row["provenance"] == "PAPER_DIRECT" for row in figures)
    assert all(
        row["visual_review"] == "VISUALLY_INSPECTED_RENDERED_PAGE"
        for row in figures
    )
    experiments = _csv("02_FULL_PAPER_REVIEW/LC02_CHANG_EXPERIMENT_REGISTRY.csv")
    assert {
        row["artifact_id"]: (
            row["artifact_type"],
            row["data_mode"],
            row["current_evidence_role"],
        )
        for row in experiments
    } == EXPECTED_EXPERIMENT_SEMANTICS
    assert all(row["provenance"] == "PAPER_DIRECT" for row in experiments)
    assert all(row["review_status"] == "FULLY_VISUALLY_REVIEWED" for row in experiments)
    card = (DOCS / "02_FULL_PAPER_REVIEW/LC02_CHANG_FULL_METHOD_CARD.md").read_text(
        encoding="utf-8"
    )
    assert str(PAPER_PAGES) in card
    assert str(PAPER_BYTES) in card.replace(",", "")
    assert PAPER_SHA256 in card
    assert "Eqs. 1–30" in card and "Figs. 6–14" in card and "Tables 1–7" in card


def test_external_paper_binary_when_available() -> None:
    explicit = os.environ.get("LEGSA_GINS_LC02_CHANG2021_PAPER")
    if not explicit:
        pytest.skip("LEGSA_GINS_LC02_CHANG2021_PAPER is unset")
    path = Path(explicit)
    if not path.is_file():
        pytest.fail("LEGSA_GINS_LC02_CHANG2021_PAPER is not a regular file")
    assert verify_paper(path) == {
        "sha256": PAPER_SHA256,
        "bytes": PAPER_BYTES,
        "pages": PAPER_PAGES,
        "encrypted": False,
    }


def test_official_code_search_and_source_roles_are_bounded() -> None:
    registry = _csv("01_SOURCE_REGISTRY/LC02_CHANG_SOURCE_REGISTRY.csv")
    assert {row["source_id"] for row in registry} >= {
        "CHANG2021_VOR",
        "ZHAO2015_DISSERTATION",
        "YANG2018_THESIS",
        "GAO2011",
        "UBLOX_F9_LAP_SPEC",
    }
    search = (
        DOCS / "01_SOURCE_REGISTRY/LC02_CHANG_OFFICIAL_CODE_SEARCH.md"
    ).read_text(encoding="utf-8")
    assert "NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND" in search
    assert "Generic CKF/fuzzy repositories" in search


def test_state_and_measurement_orders_dimensions_and_sign() -> None:
    state = _yaml("04_METHOD_CONTRACTS/CHANG2021_STATE_AND_DYNAMICS_CONTRACT.yaml")
    measurement = _yaml("04_METHOD_CONTRACTS/CHANG2021_MEASUREMENT_CONTRACT.yaml")
    assert state["state"]["dimension"] == 15
    assert [row["dimension"] for row in state["state"]["printed_order"]] == [3] * 5
    assert measurement["paper_measurement"]["dimension"] == 6
    assert measurement["paper_measurement"]["H_shape"] == [6, 15]
    assert "INS_g - delta_v_GNSS_g" in measurement["paper_measurement"]["residual"]


def test_ckf_identity_exact_enum_selects_A() -> None:
    decision = _json("04_METHOD_CONTRACTS/CHANG2021_CKF_CORE_IDENTITY_DECISION.json")
    assert decision["allowed_decisions"] == {
        "A": "literal printed linear error-state recursion",
        "B": "full cubature transform defined by a cited source with the paper printing a reduced special case",
        "C": "equation-complete nominal INS plus cubature error-state filter",
        "D": "unresolved",
    }
    assert decision["decision"] == "A"
    assert decision["gate_result"] == "PASS"
    contract = _yaml("04_METHOD_CONTRACTS/CHANG2021_CKF_FINAL_CONTRACT.yaml")
    assert contract["cubature_points"]["used_by_selected_identity"] is False


def test_eq12_non_square_inverse_fails_closed() -> None:
    decision = _json("04_METHOD_CONTRACTS/CHANG2021_EQ12_GENERALIZED_INVERSE_DECISION.json")
    assert decision["printed_H_shape"] == [6, 15]
    assert decision["ordinary_inverse_exists"] is False
    assert decision["decision"] == "UNRESOLVED_NON_SQUARE_INVERSE_AND_STATE_LIFT"
    assert decision["gate_result"] == "FAIL"
    proof = (DOCS / "03_CITED_SOURCE_CLOSURE/CHANG2021_EQ12_SOURCE_PROOF.md").read_text(
        encoding="utf-8"
    )
    assert "rank(H)=6" in proof
    assert "Moore–Penrose" in proof
    assert "null-space" in proof


def test_beta_and_ai_mapping_are_not_invented() -> None:
    mapping = _yaml("04_METHOD_CONTRACTS/CHANG2021_BETA_TO_15_STATE_MAPPING.yaml")
    decision = _json("04_METHOD_CONTRACTS/CHANG2021_AI_VECTOR_DECISION.json")
    assert mapping["paper_beta"]["dimension"] == [6, 6]
    assert mapping["paper_lambda"]["count"] == 15
    assert mapping["mapping"]["selected"] is None
    assert mapping["mapping"]["gate"] == "FAIL"
    policies = " ".join(mapping["mapping"]["candidate_policies_not_selected"])
    assert "Moore-Penrose inverse H^T" in policies
    assert "only the velocity/position subspace" in policies
    assert "nullspace terms can populate or cross-couple unobserved" in policies
    assert decision["decision"] == "UNRESOLVED"


def test_eq14_rho_N_memberships_and_rules_are_exact_but_aggregation_is_open() -> None:
    noise = _yaml("04_METHOD_CONTRACTS/CHANG2021_NOISE_AND_INITIALIZATION_CONTRACT.yaml")
    assert noise["paper_direct"]["innovation_history"]["rho"] == 0.95
    assert noise["paper_direct"]["moving_average_window_N"] == 40
    memberships = _csv("04_METHOD_CONTRACTS/CHANG2021_MEMBERSHIP_FUNCTIONS.csv")
    assert len(memberships) == 6
    assert {(row["input"], row["label"]) for row in memberships} == {
        ("L_k1", "small"),
        ("L_k1", "medium"),
        ("L_k1", "large"),
        ("L_k2", "small"),
        ("L_k2", "medium"),
        ("L_k2", "large"),
    }
    l2_medium = next(
        row for row in memberships if (row["input"], row["label"]) == ("L_k2", "medium")
    )
    assert l2_medium["interval"] == "(-inf,5];(5,15];(15,25);[25,inf)"
    assert l2_medium["piecewise_membership"] == "0;(L-5)/10;(25-L)/10;0"
    assert l2_medium["boundary_values"] == "mu(5)=0;mu(15)=1;mu(25)=0"
    assert (15.0 - 5.0) / 10.0 == 1.0
    assert (25.0 - 15.0) / 10.0 == 1.0
    rules = _csv("04_METHOD_CONTRACTS/CHANG2021_FUZZY_RULES.csv")
    assert [row["consequent"] for row in rules] == [
        "beta_k1=-0.28 L_k1+13",
        "beta_k1=-0.17 L_k1+6",
        "beta_k1=1",
        "beta_k2=-0.28 L_k2+18",
        "beta_k2=-0.15 L_k2+13",
        "beta_k2=1",
    ]
    ts = _json("04_METHOD_CONTRACTS/CHANG2021_TS_AGGREGATION_DECISION.json")
    assert ts["decision"] == "UNRESOLVED" and ts["gate_result"] == "FAIL"


def test_by2_contract_freezes_exact_solution_and_imu_identities() -> None:
    contract = _yaml("04_METHOD_CONTRACTS/CHANG2021_BY2_INPUT_CONTRACT.yaml")
    gnss = contract["selected_sources"]["gnss"]
    imu = contract["selected_sources"]["imu"]
    assert (gnss["pvt_count"], gnss["nav_cov_count"], gnss["exact_same_itow_join_count"]) == (
        1510,
        1510,
        1510,
    )
    assert gnss["itow_step_ms"] == 200
    assert gnss["position_cov_psd_count"] == gnss["velocity_cov_psd_count"] == 1510
    assert imu["authenticated_record_count"] == 63277
    assert imu["duration_ns"] == 305197970657
    assert imu["full_sha256"] == (
        "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
    )
    assert imu["authenticated_prefix_sha256"] == (
        "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
    )


def test_live_by2_minimum_field_audit_matches_frozen_contract() -> None:
    if not LOCAL_PATHS.exists():
        pytest.skip("ignored CLEAN3R4 local path aliases are absent")
    result = audit_by2_inputs(LOCAL_PATHS)
    assert result["navigation_filter_run"] is False
    assert result["gnss1"]["pvt_count"] == 1510
    assert result["gnss1"]["nav_cov_count"] == 1510
    assert result["gnss1"]["exact_itow_join_count"] == 1510
    assert result["gnss1"]["position_cov_psd_count"] == 1510
    assert result["gnss1"]["velocity_cov_psd_count"] == 1510
    assert result["go2"]["authenticated_record_count"] == 63277
    assert result["go2"]["duration_ns"] == 305197970657
    assert result["cross_stream"]["pvt_epochs_within_go2_authenticated_coverage"] == 1471
    assert result["access_counters"]["gnss1_nonselected_payloads_semantically_decoded"] == 0
    assert result["access_counters"]["go2_forbidden_fields_semantically_parsed"] == 0


def test_access_disclosures_are_literal_and_forbidden_runs_are_zero() -> None:
    status = _json("11_REPORT/LC02_CHANG_R0_R4_STATUS.json")
    access = status["access_audit"]
    assert access["tracked_active_report_performance_lines_accidentally_rendered"] is True
    assert access["accidentally_rendered_values_used_for_source_math_input_or_decision"] is False
    assert access["serialized_nonselected_data_cells_materialized_by_initial_DictReader"] is True
    assert access["forbidden_message_payload_decode_count"] == 0
    assert access["forbidden_field_semantics_used_count"] == 0
    assert access["external_runtime_tree_open_count"] == 0
    assert access["other_method_execution_count"] == 0
    assert all(value == 0 for value in status["execution_counters"].values())


def test_non_duplication_is_structural_and_not_performance_based() -> None:
    decision = _json(
        "05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_METHOD_IDENTITY.json"
    )
    assert decision["decision"] == "DISTINCT_COMPLEMENTARY_METHOD"
    assert decision["performance_numbers_used"] is False
    rows = _csv("05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_INFORMATION_STRUCTURE.csv")
    state = next(row for row in rows if row["dimension"] == "error_state_dimension")
    receivers = next(row for row in rows if row["dimension"] == "online_GNSS_receivers")
    assert (state["LC01_PAVLASEK2021_TWO_RECEIVER_IEKF"], state["LC02_CHANG2021_FSTCKF"]) == (
        "9",
        "15",
    )
    assert (receivers["LC01_PAVLASEK2021_TWO_RECEIVER_IEKF"], receivers["LC02_CHANG2021_FSTCKF"]) == (
        "2",
        "1",
    )


def test_outcome_b_has_no_implementation_or_synthetic_payload() -> None:
    status = _json("11_REPORT/LC02_CHANG_R0_R4_STATUS.json")
    assert status["terminal_status"] == TERMINAL_STATUS
    assert status["conditional_outcome"] == "OUTCOME_B_NO_GO"
    assert status["executed_stages"] == ["R0", "R1", "R2"]
    assert status["r3_executed"] is False
    assert status["r4_executed"] is False
    assert status["implementation_executed"] is False
    assert status["synthetic_validation_executed"] is False
    for name in (
        "formal_lc02_admission",
        "implementation_authorized",
        "production_solver_authorized",
        "c00_authorized",
        "representative_cases_authorized",
        "comparison_run_authorized",
    ):
        assert status[name] is False
    assert not (CONFIG / "06_IMPLEMENTATION").exists()
    assert not (CONFIG / "07_SYNTHETIC_VALIDATION").exists()
    assert not (DOCS / "06_IMPLEMENTATION").exists()
    assert not (DOCS / "07_SYNTHETIC_VALIDATION").exists()


def test_exact_scientific_result_branch_levels_and_twelve_gate_map() -> None:
    status = _json("11_REPORT/LC02_CHANG_R0_R4_STATUS.json")
    assert status["terminal_status"] == TERMINAL_STATUS
    assert status["branch_reproduction_levels"] == EXPECTED_BRANCH_LEVELS
    assert status["gate_summary"] == {
        "gate_count": 12,
        "pass_count": 5,
        "fail_count": 7,
        "all_pass_required": True,
    }
    assert status["task_start_head"] == EXPECTED_HEAD
    assert status["artifact_build_head"] == EXPECTED_HEAD
    assert status["postcommit_task_end_head"] is None
    assert status["authorized_commit_subject"] == AUTHORIZED_COMMIT_SUBJECT
    repair = status["external_stage_repair_history"]
    assert repair["repair_mode"] == STAGE09_REPAIR_MODE
    assert repair["aggregate_atomic_exchange"] is False
    assert repair["initial_atomic_exchange_attempt"] == (
        "UNSUPPORTED_ON_DRVFS_EINVAL_NO_STAGE_CHANGE"
    )
    assert repair["final_review_correction_transaction"] == {
        "preimage_aggregate_sha256": STAGE09_REPAIR_PREIMAGE_SHA256,
        "repair_mode": STAGE09_REPAIR_MODE,
        "postimage_aggregate": (
            "EXTERNALLY_COMPUTED_AND_REPORTED_TO_AVOID_SELF_REFERENTIAL_PAYLOAD_HASH"
        ),
    }
    rubric = _yaml("04_METHOD_CONTRACTS/CHANG2021_FORMAL_ADMISSION_RUBRIC.yaml")
    assert len(rubric["gates"]) == 12
    assert {row["gate"]: row["result"] for row in rubric["gates"]} == (
        EXPECTED_GATE_RESULTS
    )
    assert rubric["decision"] == TERMINAL_STATUS


def test_publisher_is_exact_non_overwriting_and_rejects_special_entries(tmp_path: Path) -> None:
    payload = collect_tracked_payload(ROOT)
    stage = tmp_path / "stage09"
    assert publish_stage(payload, stage)["artifact_count"] == 37
    with pytest.raises(FileExistsError):
        publish_stage(payload, stage)
    if hasattr(os, "mkfifo"):
        fifo = stage / "unexpected_fifo"
        os.mkfifo(fifo)
        with pytest.raises(ValueError, match="special entry"):
            validate_stage(stage)


def test_external_stage_when_present_has_exact_parity() -> None:
    if not LOCAL_PATHS.exists():
        pytest.skip("ignored CLEAN3R4 local path aliases are absent")
    aliases = load_local_paths(LOCAL_PATHS)
    stage = aliases["clean_root"] / STAGE09_RELATIVE
    if not stage.exists():
        pytest.skip("non-overwriting external Chang audit stage not published yet")
    current = read_stage_payload(stage)
    current_aggregate = payload_aggregate_sha256(current)
    if (
        set(current) == PREVIOUS_ARTIFACTS
        and current_aggregate == STAGE09_REPAIR_PREIMAGE_SHA256
    ):
        pytest.skip("exact reviewed stage09 preimage awaits guarded two-rename repair")
    assert validate_stage(stage)["artifact_count"] == 37
    tracked = collect_tracked_payload(ROOT)
    for relative, raw in tracked.items():
        assert (stage / relative).read_bytes() == raw


def test_frozen_yin_stage08_manifest_is_unchanged() -> None:
    if not LOCAL_PATHS.exists():
        pytest.skip("ignored CLEAN3R4 local path aliases are absent")
    aliases = load_local_paths(LOCAL_PATHS)
    count, digest = normalized_tree_manifest(aliases["clean_root"] / STAGE08_RELATIVE)
    assert count == STAGE08_FILE_COUNT
    assert digest == STAGE08_MANIFEST_SHA256


def test_tracked_payload_contains_no_raw_root_literal_or_archives() -> None:
    payload = collect_tracked_payload(ROOT)
    assert all(b"/home/" not in raw and b"/mnt/" not in raw for raw in payload.values())
    assert all(not relative.lower().endswith((".pdf", ".zip")) for relative in payload)
