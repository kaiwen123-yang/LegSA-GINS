from legsa_gins.raw_gnss.raw_doppler_readiness import decide_readiness

# 中文说明：测试 readiness blocker，不允许用 PVT velocity 冒充 raw Doppler。

def test_nav_pvt_only_blocks_activation():
    decision = decide_readiness(
        {"rawx_found": False, "nav_pvt_found": True},
        {"ephemeris_available": True},
        {"rtklib_provider_available": True},
        {"satellite_state_provider_status": "available", "doppler_velocity_factor_generated": True},
    )
    assert decision.activation_allowed is False
    assert "rawx_missing" in decision.blocker_reasons


def test_rawx_without_provider_blocks_activation():
    decision = decide_readiness(
        {"rawx_found": True},
        {"ephemeris_available": True},
        {"rtklib_provider_available": True},
        {"satellite_state_provider_status": "provider_missing_sat_state_export"},
    )
    assert decision.activation_allowed is False
    assert decision.recommended_next_stage == "N5B_rtklib_satellite_state_export_provider"
