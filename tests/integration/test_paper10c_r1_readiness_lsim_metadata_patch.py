from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_paper10c_r1_readiness_lsim_metadata_patch_contract():
    types = _text("cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/go2_weak_prior_types.hpp")
    source_policy = _text("cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp")
    engine = _text("cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp")
    loader = _text("cpp/legsa_v23_port_core/src/factors/go2_weak_prior_loader.cpp")
    trace = _text("cpp/legsa_v23_port_core/src/source_aware/source_aware_trace.cpp")

    assert "enable_go2_readiness_lsim_metadata = false" in types
    assert "Go2ReadinessLsimMetadataMeasurement" in types
    assert "loadReadinessLsimMetadataCsv" in loader
    assert "trace_solver_input = false" in loader
    assert "final_v23_output_solver_input = false" in loader
    assert "go2_position_truth_claim = false" in loader
    assert "go2_yaw_truth_claim = false" in loader
    assert "enrichGo2ReadinessMetadata" in engine
    assert "enrichGo2ReadinessMetadata(metadata_copy, metadata_copy.time)" in engine
    assert "GO2_STANCE_STABLE" in source_policy
    assert "GO2_IN_PLACE_TURN" in source_policy
    assert "GO2_IMPACT_OR_ROUGH" in source_policy
    assert "GO2_READINESS_LOW" in source_policy
    assert "GO2_MOTION_UNKNOWN" in source_policy
    assert "go2_readiness_metadata_available,go2_motion_state" in trace
