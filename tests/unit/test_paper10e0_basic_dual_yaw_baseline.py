"""中文说明：PAPER10E0 Basic Dual-Yaw EKF 基线的最小边界审计。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GI_ENGINE = ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp"
OPTIONS = ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp"
LOADER = ROOT / "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp"
MANIFEST = ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_basic_dual_yaw_options_and_manifest_contract() -> None:
    """中文说明：确认 Basic 基线有显式开关和报告字段，避免混成 Full 模块。"""

    options = _text(OPTIONS)
    manifest = _text(MANIFEST)
    for token in [
        "enable_basic_dual_yaw_baseline",
        "enable_dual_yaw_update",
        "basic_dual_yaw_fixed_std_deg",
        "disable_source_aware",
        "disable_go2",
        "disable_qm",
        "disable_raw_doppler",
        "disable_fgo_feedback",
    ]:
        assert token in options
        assert token in manifest


def test_basic_loader_forces_complex_modules_off() -> None:
    """中文说明：即使配置误写启用项，Basic 模式也必须强制关闭复杂模块。"""

    loader = _text(LOADER)
    basic_block = loader.split("if (options.enable_basic_dual_yaw_baseline)", 1)[1]
    for token in [
        "options.enable_receiver_velocity_update = false",
        "options.raw_doppler_config.enable_raw_doppler = false",
        "options.go2_attitude_prior_config.enable_go2_attitude_weak_prior = false",
        "options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic = false",
        "options.source_aware_policy_config.enable_source_aware_weighting = false",
        "options.quality_state_manager_config.enable_multi_state_qm = false",
        "options.fgo_feedback_config.enable_fgo_feedback = false",
        "options.qa_fallback_config.enable_qa_fallback = false",
        "options.yaw_scheme_C_enabled = false",
    ]:
        assert token in basic_block
    assert 'options.algorithm_id = "Basic_Dual_Yaw_EKF"' in basic_block


def test_basic_yaw_update_is_plain_ekf_update() -> None:
    """中文说明：Basic yaw 只做 1D yaw EKFUpdate，不含 gate/downweight/source-aware。"""

    engine = _text(GI_ENGINE)
    block = engine.split("void GIEngine::applyBasicDualYawUpdate", 1)[1].split(
        "void GIEngine::applyRawDopplerUpdateForTime", 1
    )[0]
    assert "wrapYawResidual(yaw_pred - yaw_obs)" in block
    assert "H(0, PHI_ID + 2) = -1.0" in block
    assert "yaw_std * yaw_std" in block
    assert "EKFUpdate(dz, H, R)" in block
    for forbidden in [
        "yaw_res_hard",
        "yaw_res_soft",
        "yaw_downweight_scale",
        "applySourceAwareWeighting",
        "rejected",
        "DOWNWEIGHT",
        "HOLD",
        "fallback",
    ]:
        assert forbidden not in block


def test_basic_gnss_update_returns_before_full_modules() -> None:
    """中文说明：Basic 模式在 position+yaw 后返回，不进入 Raw Doppler/Go2/FGO。"""

    engine = _text(GI_ENGINE)
    block = engine.split("if (options_.enable_basic_dual_yaw_baseline)", 1)[1].split(
        "const bool qa_reject_yaw", 1
    )[0]
    assert "applyBasicDualYawUpdate(policy_gnss)" in block
    assert "++update_count_" in block
    assert "return" in block
    for forbidden in [
        "applyRawDopplerUpdateForTime",
        "applyGo2VelocityDiagnosticPriorForTime",
        "applyGo2AttitudeWeakPriorForTime",
        "applyFgoFeedbackForTime",
    ]:
        assert forbidden not in block


def test_basic_runtime_cannot_route_to_qa_fallback_identity() -> None:
    """中文说明：Basic 模式下即使 algorithm_id 误写，也不能重新激活 QA fallback 路由。"""

    runtime = _text(ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp")
    qa_route = runtime.split("if (!options.enable_basic_dual_yaw_baseline &&", 1)[1].split(
        "if (options.imu_path.empty()", 1
    )[0]
    assert "options.algorithm_id == quality_aware::kLegsaQaFallbackEkf" in qa_route
    assert "options.enable_basic_dual_yaw_baseline" in runtime
