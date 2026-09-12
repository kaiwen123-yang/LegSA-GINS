from __future__ import annotations

import csv
import json
import hashlib
import os
import subprocess
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature import lc02_y0_y3_audit as audit


REPO = Path(__file__).resolve().parents[2]
DOC_PAYLOAD = REPO / "docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload"
CFG_PAYLOAD = REPO / "configs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload"
LOCAL_PATHS = REPO / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
EXPECTED_TOP = {
    "00_ACTIVE_METHOD_REGISTRY",
    "01_PRIOR_IMPLEMENTATION_AUDIT",
    "02_PAPER_REVIEW",
    "03_SOURCE_PROVENANCE",
    "04_METHOD_CONTRACTS",
    "05_BY2_INPUT_AUDIT",
    "06_NON_DUPLICATION_AUDIT",
    "11_REPORT",
}
EXPECTED_AUGMENTED_TOP = EXPECTED_TOP | {"07_Y4A_REPRODUCIBILITY_CLOSURE"}


def _stage() -> Path:
    if not LOCAL_PATHS.is_file():
        pytest.skip("ignored CLEAN3R4 local path aliases are unavailable")
    values = audit.load_local_paths(LOCAL_PATHS)
    stage = Path(values["clean_root"]) / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/08_LC02_YIN2023_RAEKF"
    if not stage.is_dir():
        pytest.skip("external LC02 audit stage has not been generated")
    return stage


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _yaml(name: str) -> dict:
    return yaml.safe_load((CFG_PAYLOAD / "04_METHOD_CONTRACTS" / name).read_text(encoding="utf-8"))


def test_active_registry_preserves_lc01_and_freezes_lc02_alias() -> None:
    rows = _rows(DOC_PAYLOAD / "00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY.csv")
    by_id = {row["method_id"]: row for row in rows}
    assert by_id["LC01_PAVLASEK2021_TWO_RECEIVER_IEKF"]["status"] == "COMPLETED_VALID_EXTERNAL_SOLUTION_LEVEL_METHOD"
    assert by_id["LC01_PAVLASEK2021_TWO_RECEIVER_IEKF"]["legacy_id"] == "EXT05A_PAVLASEK_TWO_RECEIVER_IEKF"
    assert by_id["LC02_YIN2023_RAEKF"]["legacy_id"] == "EXT06_YIN2023_RAEKF_LC"
    assert by_id["LC02_YIN2023_RAEKF"]["status"] == "Y0_Y3_AUDIT_FINALIZED_CONTRACT_READY_FORMAL_ADMISSION_FALSE"
    assert by_id["LC02_YIN2023_RAEKF"]["reproduction_level"] == "PAPER_DERIVED_POLICY_BASELINE"
    assert by_id["LC02_YIN2023_RAEKF"]["intended_formal_primary"] == "true"
    assert by_id["LC02_YIN2023_RAEKF"]["formal_primary_admitted"] == "false"
    boundary = (DOC_PAYLOAD / "00_ACTIVE_METHOD_REGISTRY/ACTIVE_EXTERNAL_METHOD_BOUNDARY.md").read_text()
    assert "EXT06_HAO2018_TWO_ANTENNA_LC_EKF" in boundary
    assert "forbidden and obsolete" in boundary


def test_horizontal18_is_inactive_but_lc01_method_identity_is_active() -> None:
    rows = _rows(DOC_PAYLOAD / "00_ACTIVE_METHOD_REGISTRY/INACTIVE_OR_LEGACY_RESULT_REGISTRY.csv")
    by_id = {row["asset_or_result_id"]: row for row in rows}
    assert by_id["HORIZONTAL18_V2_INTERNAL_METHOD_RANKING"]["comparison_evidence_status"] == "INACTIVE"
    assert "method-identity mismatch" in by_id["HORIZONTAL18_V2_INTERNAL_METHOD_RANKING"]["reason"]
    assert by_id["LC01_PAVLASEK2021_METHOD_AND_C00"]["method_identity_status"] == "ACTIVE"


def test_prior_yin_asset_audit_is_complete_and_nonreusable() -> None:
    rows = _rows(DOC_PAYLOAD / "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_ASSET_INVENTORY.csv")
    allowed = {
        "ACTIVE_REUSABLE_IMPLEMENTATION",
        "LEGACY_STATIC_CODE_RECOVERABLE_ONLY",
        "LEGACY_RUNTIME_NOT_ACTIVE_EVIDENCE",
        "PAPER_DERIVED_SIMPLIFICATION_NOT_FULL_REPRODUCTION",
        "UNRELATED_NAME_COLLISION",
        "NO_PRIOR_ASSET",
    }
    assert rows and all(row["classification"] in allowed for row in rows)
    assert any(row["asset_id"] == "QA11G_ALIAS" for row in rows)
    decision = json.loads((DOC_PAYLOAD / "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_REUSABILITY_DECISION.json").read_text())
    assert decision["active_reusable_implementation"] is False
    assert decision["performance_claims_imported"] is False
    provenance = (DOC_PAYLOAD / "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_CODE_PROVENANCE.md").read_text()
    for token in ["k0=1.0", "k1=4.0", "exact_reproduction=false", "source_aware_trace_enabled=true", "PDOP^2 Q r^2"]:
        assert token in provenance


def test_paper_identity_license_and_complete_review() -> None:
    card = (DOC_PAYLOAD / "02_PAPER_REVIEW/LC02_FULL_METHOD_CARD.md").read_text()
    for token in [audit.PAPER_SHA256, "24 pages", "21,097,265 bytes", "CC BY 4.0", "Equations (1)–(14)", "Figures 1–20", "Tables 1–10", "Figure 3"]:
        assert token in card
    equations = _rows(DOC_PAYLOAD / "02_PAPER_REVIEW/LC02_EQUATION_REGISTRY.csv")
    assert {str(i) for i in range(1, 15)}.issubset({row["equation_id"] for row in equations})
    figures = _rows(DOC_PAYLOAD / "02_PAPER_REVIEW/LC02_FIGURE_AND_FLOW_REGISTRY.csv")
    assert {str(i) for i in range(1, 21)} == {row["figure"] for row in figures}


def test_state_dimension_order_full_F_G_and_sign_regressions() -> None:
    contract = _yaml("LC02_STATE_AND_DYNAMICS_CONTRACT.yaml")
    assert contract["state"]["dimension"] == 21
    assert [block["name"] for block in contract["state"]["order"]] == [
        "delta_r_ins_n", "delta_v_ins_n", "phi_n", "gyro_bias_b", "accel_bias_b", "gyro_scale_b", "accel_scale_b"
    ]
    continuous = contract["continuous_model"]
    assert continuous["f_dimension"] == [21, 21]
    assert continuous["g_dimension"] == [21, 18]
    blocks = continuous["f_blocks"]
    assert blocks["F_rr"][0] == ["-v_D/rmh", "0", "v_N/rmh"]
    assert blocks["F_rr"][1][2] == "v_E/rnh"
    assert blocks["F_phiv"] == [["0", "1/rnh", "0"], ["-1/rmh", "0", "0"], ["0", "-tan(L)/rnh", "0"]]
    assert blocks["F_vr"][2][2].endswith("+2*g/(sqrt(R_M*R_N)+h)")
    assert blocks["all_unlisted_3x3_blocks"] == "ZERO"
    assert continuous["noise_vector_order"] == ["accel_VRW", "gyro_ARW", "gyro_bias_drive", "accel_bias_drive", "gyro_scale_drive", "accel_scale_drive"]
    assert "(I + [phi^n x])" in contract["attitude_error"]["convention"]
    assert contract["by2_imu_frame_instantiation"]["conversion_order"][0].startswith("proper FLU_to_FRD")
    assert contract["by2_imu_frame_instantiation"]["quaternion_or_RPY_used"] is False
    current = contract["current_repository_comparison"]
    assert current["path"] == "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp"
    assert current["sha256"] == "4d2e329a1f6a11ed232941c3150a5569791f7ac5fceb0362e91e5dd856dc6a50"
    assert current["omitted_F_blocks"] == ["F_rr", "F_vr", "F_vv", "F_phi_r", "F_phi_v"]
    assert current["correlation_time_policy"] == "max(configured corr_time, 1.0 s)"
    assert current["nonpositive_dt_fallback_s"] == 0.01
    port = REPO / current["path"]
    assert hashlib.sha256(port.read_bytes()).hexdigest() == current["sha256"]


def test_measurement_scope_lever_arm_and_sign_contracts() -> None:
    decision = json.loads((CFG_PAYLOAD / "04_METHOD_CONTRACTS/LC02_MEASUREMENT_SCOPE_DECISION.json").read_text())
    assert decision["decision"] == "POSITION_ONLY_PAPER_FAITHFUL"
    assert decision["online_gnss_velocity"] is False
    model = _yaml("LC02_MEASUREMENT_MODEL_CONTRACT.yaml")
    assert model["H"]["dimension"] == [3, 21]
    assert model["H"]["attitude_block_dimension"] == [3, 3]
    assert model["H"]["attitude_block_sign"] == "positive"
    lever = _yaml("LC02_FRAME_AND_LEVER_ARM_CONTRACT.yaml")
    assert lever["lever_arm"]["direction"]["value"] == "INS_IMU_origin_to_GNSS_antenna_phase_center"
    assert lever["lever_arm"]["direction"]["provenance_class"] == "CITED_SOURCE"
    assert lever["lever_arm"]["expressed_in"]["value"] == "body_FRD"
    assert lever["lever_arm"]["attitude_jacobian"]["provenance_class"] == "PAPER_DIRECT"
    assert lever["generic_cited_endpoints"]["gnss_measured_physical_point"]["provenance_class"] == "CITED_SOURCE"
    assert lever["by2_physical_instantiation"]["gnss_measured_physical_point"]["provenance_class"] == "BY2_PHYSICAL_INSTANTIATION"
    assert lever["by2_physical_instantiation"]["status"] == "ROUGH_BY2_PHYSICAL_INSTANTIATION"
    assert lever["by2_physical_instantiation"]["numerical_value_authorized_now"] is False


def test_improved_R_Q_and_units_are_complete() -> None:
    improved = _yaml("LC02_IMPROVED_R_CONTRACT.yaml")
    assert improved["paper_selected_exponents"] == {"a": 2, "b": 1}
    assert improved["paper_selected_formula"] == "R_k = PDOP^2 Q r_k^2"
    assert improved["r"]["derived_matrix_provenance_class"] == "PAPER_DERIVED"
    assert improved["by2_selected_covariance"]["off_diagonal_use_online"] is False
    q_rows = _rows(DOC_PAYLOAD / "04_METHOD_CONTRACTS/LC02_MEASUREMENT_FACTOR_Q_REGISTRY.csv")
    assert [int(row["Q"]) for row in q_rows] == [1, 2, 3, 4, 5, 6]
    assert q_rows[0]["solution_description"] == "Fixed integer"
    units = _yaml("LC02_PDOP_STD_UNIT_CONTRACT.yaml")
    assert units["PDOP"]["units"] == "dimensionless"
    assert units["STD"]["covariance_units"] == "m2"
    assert units["STD"]["std_units"] == "m"
    assert units["velocity_covariance_used_online"] is False


def test_four_branch_separation_and_exact_reproduction_levels() -> None:
    rows = _rows(DOC_PAYLOAD / "04_METHOD_CONTRACTS/LC02_BRANCH_IDENTITY_REGISTRY.csv")
    levels = {row["branch_id"]: row["reproduction_level"] for row in rows}
    assert levels == {
        "YIN2023_EKF": "FAITHFUL_ALGORITHM_REPRODUCTION",
        "YIN2023_AKF": "FAITHFUL_MODULE_REPRODUCTION",
        "YIN2023_RKF": "PAPER_DERIVED_POLICY_BASELINE",
        "YIN2023_RAEKF": "PAPER_DERIVED_POLICY_BASELINE",
    }
    assert _yaml("LC02_AKF_CONTRACT.yaml")["threshold_k"] == 1.0
    rkf = _yaml("LC02_RKF_CONTRACT.yaml")
    assert rkf["thresholds"] == {"k0": 1.15, "k1": 4.45}
    assert rkf["innovation_observation_symbol"]["status"] == "CURRENTLY_UNKNOWN"
    assert rkf["innovation_observation_symbol"]["permitted_policy"] == "set L_k=Z_k"
    assert rkf["innovation_observation_symbol"]["permitted_policy_provenance"] == "PAPER_DERIVED"
    assert rkf["standardized_innovation"]["status"] == "CURRENTLY_UNKNOWN"
    assert rkf["zero_weight_behavior"]["paper_equation_executable"] is False
    raekf = _yaml("LC02_RAEKF_CONTRACT.yaml")
    assert raekf["omega"] == {"when_abs_stat_le_c": 0.85, "when_abs_stat_gt_c": 0.15}
    assert raekf["covariance_fusion"] == "P_k = omega*P_ak + (1-omega)*P_rk"
    inherited = " ".join(raekf["inherited_robust_limitations"])
    for token in ["L_k versus Z_k", "V_tilde_i standardizer", "zero-weight/rejection path"]:
        assert token in inherited
    assert all(token in raekf["overall_limitation"] for token in ["L_k versus Z_k", "V_tilde_i standardizer", "zero-weight/rejection path"])
    closures = {row["branch_id"]: row["closure"] for row in rows}
    assert all(token in closures["YIN2023_RKF"] for token in ["L_k versus Z_k", "standardizer", "zero-weight/rejection path"])
    assert all(token in closures["YIN2023_RAEKF"] for token in ["L_k/Z_k", "standardizer", "zero-weight/rejection"])


def test_covariance_fusion_formula_resolved_with_nonterminal_source_limitation() -> None:
    decision = json.loads((CFG_PAYLOAD / "04_METHOD_CONTRACTS/LC02_COVARIANCE_FUSION_DECISION.json").read_text())
    assert decision["decision"] == "EQ13_FUSION_RESOLVED_P_RK_NOT_SOURCE_CLOSED"
    assert decision["audit_terminal_status"] == audit.TERMINAL_STATUS
    assert decision["eq13_fusion_formula_resolved"] is True
    assert decision["not_source_closed_input"] == "P_rk"
    assert decision["faithful_raekf_claim_allowed"] is False
    assert decision["audit_closure_pass"] is True
    limitations = " ".join(decision["limitations"])
    for token in ["L_k", "Z_k", "V_tilde_i", "zero weight", "rejection"]:
        assert token in limitations
    gate = _yaml("LC02_FUTURE_EXECUTION_GATE.yaml")
    next_step = gate["next_required_scientific_step"]
    for token in ["L_k-versus-Z_k", "V_tilde_i standardizer", "zero-weight/rejection"]:
        assert token in next_step
    assert gate["formal_lc02_admission"] is False


def test_official_partial_source_classification() -> None:
    text = (DOC_PAYLOAD / "03_SOURCE_PROVENANCE/LC02_OFFICIAL_CODE_SEARCH.md").read_text()
    assert "OFFICIAL_PARTIAL_CODE_ONLY" in text
    assert "yin_specific_implementation=NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND" in text
    assert "yin_adaptive_robust_modules=NOT_FOUND" in text
    assert "08f9fce66028c65727b3f3c53f34f7dfd5a3c1c3" in text


def test_lc01_lc02_are_distinct_without_performance_decision() -> None:
    decision = json.loads((DOC_PAYLOAD / "06_NON_DUPLICATION_AUDIT/LC01_VS_LC02_METHOD_IDENTITY_DECISION.json").read_text())
    assert decision["decision"] == "DISTINCT_COMPLEMENTARY_METHOD"
    assert decision["performance_numbers_used"] is False
    assert decision["lc01_online_receiver_count"] == 2
    assert decision["lc02_online_receiver_count"] == 1
    assert decision["lc01_direct_rigid_relative_vector"] is True
    assert decision["lc02_direct_rigid_relative_vector"] is False


def test_nav_cov_official_layout_regression() -> None:
    payload = bytearray(64)
    struct.pack_into("<I", payload, 0, 460_873_800)
    payload[4] = 0
    payload[5] = 1
    payload[6] = 1
    struct.pack_into("<6f", payload, 16, 4e-4, 1e-5, -2e-5, 9e-4, 3e-5, 16e-4)
    decoded = audit.decode_nav_cov(bytes(payload), 123.0)
    assert decoded["itow_ms"] == 460_873_800
    assert decoded["pos_cov_valid"] is True
    np.testing.assert_allclose(decoded["covariance"], [[4e-4, 1e-5, -2e-5], [1e-5, 9e-4, 3e-5], [-2e-5, 3e-5, 16e-4]], rtol=1e-6)


def test_generated_by2_input_audit_and_forbidden_counters() -> None:
    stage = _stage()
    time = json.loads((stage / "05_BY2_INPUT_AUDIT/LC02_TIME_AND_RATE_AUDIT.json").read_text())
    assert time["gnss1"]["pvt_count"] == 1510
    assert time["gnss1"]["cov_count"] == 1510
    assert time["gnss1"]["exact_itow_join_count"] == 1510
    assert time["gnss1"]["raw_source_sha256"] == "5d2ac46d28c14470cd8b2c910d8cba12492bed0e72517e98496188851f5bc027"
    assert time["gnss1"]["status_candidate_source_sha256"] == "9761d2d7055356857bd7b26a251fdd60fdf6c2b18a882dac74bc35d164e42e08"
    cross = time["gnss1"]["outer_time_and_go2_overlap"]
    assert cross["pvt_epochs_within_go2_coverage"] == 1471
    assert cross["pvt_outer_first_unix_s"] == pytest.approx(1772784055.9433324)
    assert cross["pvt_outer_last_unix_s"] == pytest.approx(1772784357.7319257)
    assert cross["first_overlap_after_go2_start_s"] == pytest.approx(11.056254, abs=1e-6)
    assert cross["last_overlap_before_go2_end_s"] == pytest.approx(0.152543, abs=1e-6)
    assert time["go2_imu"]["authenticated_prefix_sha256"] == audit.GO2_COMPLETE_PREFIX_SHA256
    assert time["go2_imu"]["source_sha256"] == audit.GO2_FULL_SHA256
    assert time["go2_imu"]["complete_records"] == 63277
    assert time["go2_imu"]["first_sec"] == 1772784044
    assert time["go2_imu"]["first_nsec"] == 887078145
    assert time["go2_imu"]["first_time_ns"] == 1772784044887078145
    assert time["go2_imu"]["last_sec"] == 1772784350
    assert time["go2_imu"]["last_nsec"] == 85048802
    assert time["go2_imu"]["last_time_ns"] == 1772784350085048802
    assert time["go2_imu"]["duration_ns"] == 305197970657
    assert time["go2_imu"]["float_times_are_descriptive_only"] is True
    assert time["go2_imu"]["forbidden_fields_materialized_count"] == 0
    assert time["trace_open_count"] == 0
    assert time["reference_open_count"] == 0
    pdop = json.loads((stage / "05_BY2_INPUT_AUDIT/LC02_PDOP_AVAILABILITY.json").read_text())
    q = json.loads((stage / "05_BY2_INPUT_AUDIT/LC02_Q_INPUT_AVAILABILITY.json").read_text())
    std = json.loads((stage / "05_BY2_INPUT_AUDIT/LC02_STD_AVAILABILITY.json").read_text())
    assert pdop["available"] is q["available"] is std["available"] is True
    assert q["selected_Q"] == 1 and q["valid_count"] == 1510
    assert std["psd_count"] == 1510 and std["velocity_covariance_used_online"] is False
    fields = _rows(stage / "05_BY2_INPUT_AUDIT/LC02_BY2_FIELD_ROLE_REGISTRY.csv")
    velocity = next(row for row in fields if row["field"] == "GNSS1 velocity")
    assert velocity["valid_count"] == "NOT_EVALUATED_NOT_DECODED"
    rawx = next(row for row in fields if row["field"].startswith("GNSS1 RAWX"))
    assert "SERIALIZED_ROWS_READ" in rawx["decision"]
    assert "NOT_RETAINED_BEYOND_ROW" in rawx["decision"]


def test_exact_stage_layout_no_solver_or_C00_outputs_and_gates_false() -> None:
    stage = _stage()
    assert len(audit._required_stage_files()) == 47
    actual_files = {str(path.relative_to(stage)) for path in stage.rglob("*") if path.is_file()}
    base_files = set(audit._required_stage_files())
    assert base_files.issubset(actual_files)
    if actual_files == base_files:
        assert {item.name for item in stage.iterdir()} == EXPECTED_TOP
    else:
        assert actual_files == base_files | set(audit._allowed_y4a_append_files())
        assert {item.name for item in stage.iterdir()} == EXPECTED_AUGMENTED_TOP
    assert not any(path.is_symlink() or path.suffix.lower() == ".zip" for path in stage.rglob("*"))
    assert audit.validate_stage(stage) == []
    status = json.loads((stage / "11_REPORT/LC02_Y0_Y3_STATUS.json").read_text())
    assert status["terminal_status"] == audit.TERMINAL_STATUS
    assert status["terminal_status"] == "PASS_LC02_YIN2023_Y0_Y3_METHOD_NON_DUPLICATION_AND_BY2_CONTRACT_READY"
    assert status["audit_closure_pass_is_formal_raekf_admission"] is False
    assert status["formal_lc02_admission"] is False
    assert status["implementation_authorized"] is False
    assert status["C00_authorized"] is False
    assert status["representative_cases_authorized"] is False
    provenance = status["audit_provenance"]
    assert provenance["data_mode"] == "REAL_BY2_INPUT_AUDIT"
    assert provenance["synthetic_data_used"] is False
    assert provenance["semisynthetic_data_used"] is False
    assert provenance["trace_used_online"] is False
    assert provenance["receiver_imu_as_body_imu"] is False
    assert provenance["final_v23_output_solver_input"] is False
    assert provenance["LegSA_output_solver_input"] is False
    assert provenance["old_runtime_input_count"] == 0
    assert len(provenance["code_commit"]) == 40
    assert len(provenance["config_hash"]) == 64
    assert all(value == 0 for value in status["execution_counters"].values())
    names = [path.name.lower() for path in stage.rglob("*") if path.is_file()]
    assert not any(name in {"nav.csv", "eval_nav.csv"} or "solver_output" in name or "c00_output" in name for name in names)


def test_existing_stage_replacement_is_explicit_and_exact() -> None:
    stage = _stage()
    clean_root = Path(audit.load_local_paths(LOCAL_PATHS)["clean_root"])
    with pytest.raises(ValueError, match="explicit --replace-existing-audit-stage"):
        audit._prepare_exact_stage_target(stage, clean_root, replace_existing_audit_stage=False)
    actual_files = {str(path.relative_to(stage)) for path in stage.rglob("*") if path.is_file()}
    if actual_files == set(audit._required_stage_files()):
        audit._prepare_exact_stage_target(stage, clean_root, replace_existing_audit_stage=True)
    else:
        with pytest.raises(ValueError, match="not the exact known 47-file audit layout"):
            audit._prepare_exact_stage_target(stage, clean_root, replace_existing_audit_stage=True)


def test_stage_structure_rejects_fifo_special_entry(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo is unavailable on this platform")
    fifo = tmp_path / "unexpected.fifo"
    os.mkfifo(fifo)
    errors = audit._stage_structure_errors(tmp_path)
    assert "special filesystem entry forbidden: unexpected.fifo" in errors


def test_exact_validate_only_cli_invocation() -> None:
    _stage()
    completed = subprocess.run(
        [sys.executable, "scripts/paper_rebuild/audit_lc02_yin2023_y0_y3.py", "--validate-only"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["validation_errors"] == []


def test_preexisting_canonical_files_are_preserved_byte_exact() -> None:
    expected = {
        REPO / "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py": "00a54aac97ec54715c47dda9350635aa3ea3e969e5deb152e52e33614a6a6480",
        REPO / "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py": "d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16",
    }
    for path, digest in expected.items():
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_all_json_yaml_csv_payloads_parse_and_provenance_labels_are_known() -> None:
    for root in (DOC_PAYLOAD, CFG_PAYLOAD):
        for path in root.rglob("*"):
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            elif path.suffix == ".csv":
                rows = _rows(path)
                assert rows
                if "provenance_class" in rows[0]:
                    assert all(row["provenance_class"] in audit.PROVENANCE_CLASSES for row in rows)


def test_tracked_lc02_scope_contains_audit_only_and_no_hardcoded_raw_root() -> None:
    allowed = [
        REPO / "configs/paper_rebuild/horizontal_literature/lc02_yin2023",
        REPO / "docs/paper_rebuild/horizontal_literature/lc02_yin2023",
        REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/lc02_y0_y3_audit.py",
        REPO / "scripts/paper_rebuild/audit_lc02_yin2023_y0_y3.py",
    ]
    texts: list[str] = []
    for entry in allowed:
        paths = entry.rglob("*") if entry.is_dir() else [entry]
        for path in paths:
            if path.is_file() and path.suffix in {".py", ".md", ".csv", ".json", ".yaml"}:
                texts.append(path.read_text(encoding="utf-8"))
    combined = "\n".join(texts)
    raw_root_sentinel = "/mnt/g/" + "LegSA-GINS-project/" + "data/raw"
    assert raw_root_sentinel not in combined
    module_text = (REPO / "src/legsa_gins/paper_rebuild/horizontal_literature/lc02_y0_y3_audit.py").read_text()
    for forbidden in ["EKFPredict(", "stateFeedback(", "run_canonical", "evaluate_nav", "open_trace"]:
        assert forbidden not in module_text
