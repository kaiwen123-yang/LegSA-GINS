from legsa_gins.source_aware.measurement_source_types import ObservationInnovation, SourceMetadata
from legsa_gins.source_aware.source_weight_policy import combine_source_weight


def test_combined_policy_never_shrinks_r():
    # 中文说明：N6A 默认不允许把 R 缩小到 baseline 以下。
    result = combine_source_weight(
        SourceMetadata(source_id="receiver_velocity", std_n=0.1, std_e=0.1, std_d=0.1),
        ObservationInnovation(source_id="receiver_velocity", residual=(0.0, 0.0, 0.0), r_trace=1.0),
    )
    assert result.combined_R_scale >= 1.0


def test_combined_policy_uses_lsim_or_oim_scale():
    # 中文说明：LSIM/OIM 任一异常都应进入 combined R scale。
    result = combine_source_weight(
        SourceMetadata(source_id="receiver_velocity", std_n=1.0, std_e=1.0, std_d=1.0),
        ObservationInnovation(source_id="receiver_velocity", residual=(4.0, 0.0, 0.0), r_trace=0.1),
    )
    assert result.combined_R_scale > 1.0
