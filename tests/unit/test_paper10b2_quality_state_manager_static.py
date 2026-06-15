from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_paper10b2_qm_states_actions_and_sources_declared():
    header = read(
        "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/"
        "quality_state_manager.hpp"
    )
    for token in [
        "kNormal",
        "kDownweight",
        "kReject",
        "kHold",
        "kRecovery",
        "kFallback",
        "kUseOriginalR",
        "kInflateR",
        "kRejectObservation",
        "kHoldSource",
        "kRecoveryHysteresis",
        "kFallbackPartialSourceFusion",
    ]:
        assert token in header

    measurement_header = read(
        "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/"
        "measurement_source.hpp"
    )
    for source in [
        "kReceiverPosition",
        "kReceiverVelocity",
        "kDualAntennaYaw",
        "kRawDopplerVelocity",
        "kGo2AttitudeRollPitch",
        "kGo2HorizontalVelocity",
    ]:
        assert source in measurement_header


def test_paper10b2_qm_default_off_and_modes_are_configured():
    options = read("cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp")
    header = read(
        "cpp/legsa_v23_port_core/include/legsa_v23_port_core/source_aware/"
        "quality_state_manager.hpp"
    )
    manager = read(
        "cpp/legsa_v23_port_core/src/source_aware/quality_state_manager.cpp"
    )
    loader = read("cpp/legsa_v23_port_core/src/config/port_config_loader.cpp")

    assert "enable_multi_state_qm = false" in manager
    assert 'multi_state_qm_mode = "QM00_OFF"' in header
    assert "QualityStateManagerConfig quality_state_manager_config" in options
    for mode in [
        "QM00_OFF",
        "QM01_STATE_TRACE_ONLY",
        "QM02_DOWNWEIGHT_REJECT",
        "QM03_HOLD_RECOVERY",
        "QM04_FULL",
    ]:
        assert mode in manager
    for key in [
        "qm_downweight_threshold",
        "qm_reject_threshold",
        "qm_hold_enter_count",
        "qm_hold_length",
        "qm_recovery_count",
        "qm_fallback_enter_count",
        "qm_fallback_exit_count",
        "qm_fallback_max_duration",
        "qm_timestamp_gap_hold_sec",
        "qm_go2_motion_state_influence",
        "qm_readiness_influence",
    ]:
        assert key in loader


def test_paper10b2_qm_forbidden_inputs_not_used_by_manager():
    manager = read(
        "cpp/legsa_v23_port_core/src/source_aware/quality_state_manager.cpp"
    )
    lower = manager.lower()
    assert "trace_used_online = false" in lower
    assert "final_v23_output_solver_input = false" in lower
    assert "legsa_output_solver_input = false" in lower
    assert "no_per_case_tuning = true" in lower
    assert "rmse" not in lower
