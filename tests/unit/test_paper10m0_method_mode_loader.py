"""中文说明：PAPER10M0 method-mode loader targeted tests。"""

from pathlib import Path

from scripts.paper10m0_method_mode_loader import (
    METHOD_MODE_IDS,
    load_all,
    resolve_effective_feature_flags,
    validate_mode_safety,
)


def test_paper10m0_loads_all_frozen_configs():
    root = Path(__file__).resolve().parents[2]
    loaded = load_all(root)
    assert set(loaded["method_modes"]) == set(METHOD_MODE_IDS)
    assert len(loaded["contracts"]) >= 7
    assert len(loaded["config_sha256"]) == 64


def test_paper10m0_forbidden_flags_remain_disabled():
    root = Path(__file__).resolve().parents[2]
    loaded = load_all(root)
    provider_status = {
        "raw_doppler": True,
        "go2_roll_pitch": True,
        "go2_horizontal_velocity": True,
        "go2_joint_factor": True,
        "multi_state_qm": True,
    }
    for frozen in loaded["method_modes"].values():
        effective = resolve_effective_feature_flags(frozen.data, provider_status)
        assert validate_mode_safety(frozen.data, effective) == []
        assert effective["enable_trace_online"] is False
        assert effective["enable_final_v23_output_input"] is False
        assert effective["enable_legsa_output_input"] is False
        assert effective["enable_benchmark_methods"] is False
        assert effective["enable_qa_fallback"] is False


def test_paper10m0_provider_gates_optional_features():
    root = Path(__file__).resolve().parents[2]
    full_mode = load_all(root)["method_modes"]["legsa_full_candidate_with_qm"].data
    no_provider = resolve_effective_feature_flags(full_mode, {})
    with_provider = resolve_effective_feature_flags(
        full_mode,
        {
            "raw_doppler": True,
            "go2_roll_pitch": True,
            "go2_horizontal_velocity": True,
            "go2_joint_factor": True,
            "multi_state_qm": True,
        },
    )
    assert no_provider["enable_raw_doppler"] is False
    assert no_provider["enable_go2_roll_pitch_prior"] is False
    assert with_provider["enable_raw_doppler"] is True
    assert with_provider["enable_go2_roll_pitch_prior"] is True
    assert with_provider["enable_multi_state_qm"] is True
