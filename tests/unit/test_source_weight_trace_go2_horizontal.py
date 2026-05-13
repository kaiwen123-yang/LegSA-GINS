"""N7C source-aware trace summary unit test.

中文说明：确认 Go2 horizontal velocity 作为独立 source 出现在 trace 汇总中。
"""

from legsa_gins.source_aware.measurement_source_types import GO2_HORIZONTAL_VELOCITY, OBSERVATION_SOURCE_IDS
from legsa_gins.source_aware.source_weight_trace import summarize_source_weight_trace


def test_go2_horizontal_velocity_source_is_summarized():
    assert GO2_HORIZONTAL_VELOCITY in OBSERVATION_SOURCE_IDS
    summary = summarize_source_weight_trace(
        [
            {
                "source_id": GO2_HORIZONTAL_VELOCITY,
                "policy_version": "n6b_conservative_innovation_covariance",
                "combined_R_scale": "1.5",
                "rejected": "0",
                "used_innovation_covariance": "1",
            }
        ]
    )
    stats = summary["stats_by_source"][GO2_HORIZONTAL_VELOCITY]
    assert stats["update_count"] == 1
    assert stats["R_scale_max"] == 1.5
