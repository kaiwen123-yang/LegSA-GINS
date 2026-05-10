from pathlib import Path

from legsa_gins.source_aware.measurement_source_types import RAW_DOPPLER_VELOCITY, RECEIVER_POSITION, SourceMetadata
from legsa_gins.source_aware.source_aware_n6b_policy import (
    InnovationCovarianceInput,
    N6BPolicyConfig,
    combine_n6b_source_weight,
    compute_innovation_covariance_metrics,
    compute_lsim_n6b,
    compute_oim_n6b,
)


def test_oim_uses_innovation_covariance_s_hph_plus_r():
    # 中文说明：N6B OIM 必须用 S=HPH^T+R 计算 NIS。
    evidence = InnovationCovarianceInput(
        source_id=RECEIVER_POSITION,
        residual=(1.0, 0.0),
        hph=((3.0, 0.0), (0.0, 3.0)),
        r=((1.0, 0.0), (0.0, 1.0)),
    )
    metrics = compute_innovation_covariance_metrics(evidence)
    assert metrics["used_innovation_covariance"] is True
    assert metrics["nis"] == 0.25
    assert metrics["dof"] == 2
    assert metrics["innovation_cov_trace"] == 8.0


def test_deadband_gives_scale_one_and_high_innovation_increases():
    low = InnovationCovarianceInput(RECEIVER_POSITION, (1.0, 0.0), ((3.0, 0.0), (0.0, 3.0)), ((1.0, 0.0), (0.0, 1.0)))
    high = InnovationCovarianceInput(RECEIVER_POSITION, (10.0, 0.0), ((0.1, 0.0), (0.0, 0.1)), ((0.1, 0.0), (0.0, 0.1)))
    assert compute_oim_n6b(low)["oim_R_scale"] == 1.0
    assert compute_oim_n6b(high)["oim_R_scale"] > 1.0


def test_source_cap_limits_scale():
    evidence = InnovationCovarianceInput(RAW_DOPPLER_VELOCITY, (100.0, 0.0, 0.0), ((0.1, 0.0, 0.0), (0.0, 0.1, 0.0), (0.0, 0.0, 0.1)), ((0.1, 0.0, 0.0), (0.0, 0.1, 0.0), (0.0, 0.0, 0.1)))
    result = compute_oim_n6b(evidence, N6BPolicyConfig(raw_doppler_cap=3.0))
    assert result["oim_R_scale"] == 3.0


def test_lsim_valid_metadata_scale_one_and_combined_never_shrinks():
    metadata = SourceMetadata(source_id=RECEIVER_POSITION, std_n=0.5, std_e=0.5, std_d=0.8, time_diff=0.0)
    lsim = compute_lsim_n6b(metadata)
    assert lsim["lsim_R_scale"] == 1.0
    result = combine_n6b_source_weight(
        metadata,
        InnovationCovarianceInput(RECEIVER_POSITION, (0.0, 0.0), ((1.0, 0.0), (0.0, 1.0)), ((1.0, 0.0), (0.0, 1.0))),
    )
    assert result.combined_R_scale >= 1.0
    assert result.paper_performance_claim is False


def test_no_hardcoded_spike_time_in_n6b_policy():
    text = Path("src/legsa_gins/source_aware/source_aware_n6b_policy.py").read_text(encoding="utf-8")
    assert "96.4067945" not in text
    assert "97.0067945" not in text
