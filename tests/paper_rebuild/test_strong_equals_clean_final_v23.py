from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_strong_update_order_matches_exact_and_basic_branch_is_unchanged() -> None:
    source = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    exact_branch = "if (options_.clean_final_v23_parity_mode) {\n    apply_yaw();\n    apply_receiver_velocity();"
    legacy_branch = "} else {\n    // 旧 CLEAN1/R1C replay 保留原 position→velocity→yaw 语义。\n    apply_receiver_velocity();\n    apply_yaw();"
    assert exact_branch in source
    assert legacy_branch in source
    assert "if (options_.enable_basic_dual_yaw_baseline)" in source
    assert source.index("applyBasicDualYawUpdate(policy_gnss);") < source.index(exact_branch)
    assert "++update_count_;\n    return;" in source


def test_clean_parity_mode_preserves_old_initial_writer_and_accepts_only_new_15col_profile() -> None:
    runtime = (ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").read_text(encoding="utf-8")
    loader = (ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp").read_text(encoding="utf-8")
    options = (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp").read_text(encoding="utf-8")
    assert "if (!options.clean_final_v23_parity_mode) {\n    appendState(engine, states, covariances);" in runtime
    assert "options.clean1_formal_mode && !options.clean_final_v23_parity_mode" in runtime
    assert "clean_final_v23_parity_mode != clean1r2r1_final_v23_identity" in loader
    assert "bool clean_final_v23_parity_mode = false;" in options


def test_active_manifest_records_parity_mode_and_update_order() -> None:
    writer = (ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp").read_text(encoding="utf-8")
    assert r'\"clean_final_v23_parity_mode\"' in writer
    assert r'\"measurement_update_order\"' in writer
    assert "position_then_yaw_then_receiver_velocity_then_feedback" in writer


def test_clean_parity_mode_writes_exact_evaluator_contract_without_correction() -> None:
    runtime = (ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp").read_text(encoding="utf-8")
    writer = (ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp").read_text(encoding="utf-8")
    assert "if (options.clean_final_v23_parity_mode)" in runtime
    assert '"KF_GINS_Navresult.nav"' in writer
    assert '"KF_GINS_STD.txt"' in writer
    assert '"KF_GINS_IMU_ERR.txt"' in writer
    assert "performs no correction, substitution, or epoch" in writer
