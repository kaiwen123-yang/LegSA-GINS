from legsa_gins.da_repro.dd_los_provider import build_dd_los_summary
from legsa_gins.da_repro.satpos_los_provider import build_satpos_los_summary


def test_dd_los_blocks_without_los_provider():
    common = {"common_rawx_available": True, "sample_rows": [{"rcv_tow": 1.0, "common_satellite_count": 4}]}
    los = build_satpos_los_summary({"obs_generated": True, "nav_generated": True}, common)
    dd = build_dd_los_summary(common, los)
    assert dd["dd_carrier_candidate_available"] is True
    assert dd["dd_design_matrix_available"] is False
    assert "los_provider_not_available" in dd["blocker_reasons"]
