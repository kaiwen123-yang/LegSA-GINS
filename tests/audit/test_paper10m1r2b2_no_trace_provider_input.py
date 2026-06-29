from legsa_gins.degradation.yaw_provider_lineage import FIXED_LINEAGE


def test_fixed_lineage_declares_trace_not_provider_input() -> None:
    assert FIXED_LINEAGE["trace_used_for_generation"] is False
    assert FIXED_LINEAGE["final_v23_output_used_for_generation"] is False
    assert FIXED_LINEAGE["legsa_output_used_for_generation"] is False

