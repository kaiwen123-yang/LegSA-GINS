from pathlib import Path

import yaml

from legsa_gins.paper_rebuild.horizontal_literature.contracts import (
    load_compatibility,
    load_phase1_contract,
    required_manifest_fields,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/paper_rebuild/horizontal_literature"


def test_phase1_contract_is_exactly_ext01_c00_and_physical_transform():
    contract = load_phase1_contract(CONFIG)
    assert contract.methods == ("EXT01_CLAMBDA",)
    assert contract.cases == ("C00",)
    assert contract.baseline_length_m == 0.350
    assert contract.trace_mode == "disabled"
    assert load_compatibility(CONFIG / "CASE_METHOD_COMPATIBILITY_V1.csv")[0]["evaluation_status"] == "NOT_EVALUATED"


def test_literature_identity_hashes_and_no_code_reuse_are_locked():
    doc = yaml.safe_load((CONFIG / "EXTERNAL_METHOD_CONTRACTS_V1.yaml").read_text())
    assert doc["literature"]["P01"]["sha256"] == "e9e19c60d1f651994c878678f530d288a82eb707e26770ce48b449774317aec4"
    assert doc["literature"]["P23"]["sha256"] == "734e256229dada2bb1c10a3f290527681a2d2bfa14b3540dd00473e927848546"
    assert doc["literature"]["P25"]["sha256"] == "11a514002e93bf659ee0245de55030a2d2d614768838dced64de8621670b407a"
    assert doc["literature"]["UBX_ZED_F9T_R02"]["sha256"] == "3d6539cd5ab3efe1254c54e4dba25d17421bfe48ac96e633e602d8d214c13668"
    assert doc["source_policy"] == {
        "papers_are_theory_and_specification_only": True,
        "paper_pdfs_copied_into_repository": False,
        "third_party_code_copied": False,
        "external_runtime_dependency": True,
    }
    assert doc["external_dependency"]["commit"] == (
        "180043ee24b6d2b168f98b64be15f69d50046b1a"
    )
    assert doc["external_dependency"]["license"] == "BSD-2-Clause"
    assert doc["external_dependency"]["upstream_source_patch"] == "none"
    fields = required_manifest_fields(CONFIG)
    assert {"raw_source_hashes", "trace_used_online", "old_runtime_input_count",
            "paired_epoch_count", "failure_row_count"} <= fields
    runtime_files = set(doc["runtime_topology"]["files"].values())
    intermediate_files = set(doc["runtime_topology"]["intermediate_files"].values())
    assert len(runtime_files) == 18
    assert len(intermediate_files) == 6
    assert runtime_files.isdisjoint(intermediate_files)
    assert "01_SHARED_RAW_BACKEND/STOCHASTIC_MODEL_CONTRACT.yaml" in runtime_files
    assert "11_REPORT/PHASE1_STATUS.json" in runtime_files
    assert not any("seal" in value.lower() for value in runtime_files)


def test_phase1r_contract_locks_validation_without_trace_tuning():
    contract = yaml.safe_load((CONFIG / "PHASE1R_VALIDATION_CONTRACT_V1.yaml").read_text())
    assert contract["immutable_parent"]["freeze_commit"] == (
        "2dd8fbaba986b07349a33d56d4b7618a1fada4d0"
    )
    assert contract["parallel_execution"]["default_workers"] == 16
    assert contract["parallel_execution"]["semantic_worker_determinism_required"] is True
    assert contract["half_cycle_contract"]["production_adjustment_cycles"] == 0.0
    assert contract["half_cycle_contract"]["sub_half_cyc_role"] == (
        "OBSERVED_CORRECTION_STATE_NOT_INVALIDITY"
    )
    assert contract["strict_search"]["ambiguity_acceptance_test_defined"] is False
    assert contract["diagnostic_only_sources"]["trace"]["allowed_before_native_hash_freeze"] is False
    assert len(contract["required_outputs"]) == 11


def test_phase1r_r2_contract_preserves_r1_and_locks_svd_gls_repair():
    contract = yaml.safe_load((CONFIG / "PHASE1R_VALIDATION_CONTRACT_V2.yaml").read_text())
    assert contract["attempt_id"] == "C00_VALIDATED_R2"
    assert contract["immutable_parents"]["phase1r_r1_terminal"] == (
        "BLOCKED_PHASE1R_SEARCH_OBJECTIVE_CROSSCHECK_FAILED"
    )
    assert contract["immutable_parents"]["mutation_allowed"] is False
    assert contract["immutable_parents"]["original_result_artifact_count"] == 3
    assert contract["immutable_parents"]["original_result_tree_digest"] == (
        "19fc1402a10bc0b658c8db065316b47aa0b56e5782a698198b3beda0bd7b4b52"
    )
    assert contract["immutable_parents"]["phase1r_r1_artifact_count"] == 1548
    assert contract["immutable_parents"]["phase1r_r1_tree_digest"] == (
        "a511104a67ed17f24da6bac073c3e718708aa7921407308b8908da8a4f651526"
    )
    assert contract["numerical_repair"]["observation_whitening"] == "CHOLESKY_QYY"
    assert contract["numerical_repair"]["least_squares"] == "RANK_CHECKED_SVD"
    assert contract["numerical_repair"]["trace_selected"] is False
    assert len(contract["required_outputs"]) == 11
    assert all("C00_VALIDATED_R2" in path or "PHASE1R_R2" in path
               for path in contract["required_outputs"])


def test_phase2_ext02_contract_is_additive_trace_closed_and_exactly_bounded():
    contract = yaml.safe_load(
        (CONFIG / "PHASE2_EXT02_CWLS_CONTRACT_V1.yaml").read_text(encoding="utf-8")
    )
    assert contract["schema_version"] == "horizontal_literature.phase2_ext02_cwls.v1"
    assert contract["method_id"] == "EXT02_CWLS" and contract["case_id"] == "C00"
    assert contract["formal_reproduction_level"] == "FAITHFUL_ALGORITHM_REPRODUCTION"
    assert contract["paper_source"]["doi"] == "10.1109/TIM.2022.3193412"
    algorithm = contract["algorithm"]
    assert algorithm["K_policy"] == "ALL_UNIQUE_CANDIDATES"
    assert algorithm["delta_Delta"] == 0.05
    assert algorithm["sphere_refinement"] == {"tolerance": 1.0e-10, "max_iterations": 20}
    assert algorithm["objective_oracle"]["original_epoch_indices"] == list(range(0, 1509, 150))
    assert algorithm["objective_oracle"]["integer_rounding_implementation"] == (
        "ORACLE_LOCAL_CEIL_X_MINUS_0P5"
    )
    assert algorithm["objective_oracle"]["production_import_allowlist"] == [
        "solve_unit_sphere_quadratic"
    ]
    assert algorithm["acceptance"][
        "search_complete_requires_every_unique_candidate_converged_finite"
    ] is True
    observation = contract["observation_contract"]
    assert observation["required_paired_epoch_count"] == 1509
    assert observation["HPPOSECEF_solver_input"] is False
    assert observation["phase_bias_calibration"] == "NONE"
    assert contract["data_flags"]["trace_open_count_before_native_freeze"] == 0
    assert contract["parallel_execution"]["default_workers"] == 16
    assert contract["parallel_execution"]["maximum_workers"] == 20
    assert contract["parallel_execution"]["atomic_writer_policy"] == (
        "NO_REPLACE_FAIL_ON_ANY_TARGET_COLLISION"
    )
    assert contract["parallel_execution"]["resource_admission"][
        "projected_RSS_exclusive_limit_fraction_of_available_RAM"
    ] == 0.70
    assert {
        "INSUFFICIENT_PR_CP_VALID", "INSUFFICIENT_INTEGER_COMPATIBLE_PHASE",
        "INSUFFICIENT_ELEVATION_ELIGIBLE", "NORMAL_MATRIX_RANK_DEFICIENT",
    } <= set(contract["failure_codes"])
    assert contract["git_provenance"] == {
        "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
        "authorized_dirty_runtime_delta_allowed": True,
        "complete_runtime_source_identity": "SOURCE_HASHES_PLUS_SOURCE_FINGERPRINT",
        "reject_dirty_git": False,
    }
    native = contract["runtime_topology"]["native_files"]
    assert len(native) == 10
    assert native["native_freeze"] == "EXT02_C00_NATIVE_FREEZE.json"
    assert "objective_oracle_diagnostics" in native and "tracking_diagnostics" in native

    schema = yaml.safe_load((CONFIG / "STANDARD_HEADING_STREAM_SCHEMA_V1.yaml").read_text())
    assert schema["fields"]["method_id"]["enum"] == ["EXT01_CLAMBDA", "EXT02_CWLS"]
    assert "accepted_wrapped_solution" in schema["fields"]["solution_state"]["enum"]
