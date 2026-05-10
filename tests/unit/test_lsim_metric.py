from legsa_gins.source_aware.lsim_metric import compute_lsim
from legsa_gins.source_aware.measurement_source_types import RAW_DOPPLER_VELOCITY, RECEIVER_POSITION, SourceMetadata


def test_lsim_good_source_scale_is_one():
    # 中文说明：健康来源保持 baseline R，不做 R shrink。
    out = compute_lsim(SourceMetadata(source_id=RECEIVER_POSITION, std_n=0.5, std_e=0.5, std_d=0.8))
    assert out["lsim_R_scale"] == 1.0
    assert out["source_blocked"] is False


def test_lsim_invalid_source_blocks_or_inflates():
    # 中文说明：invalid source 只能保守放大或拒绝。
    out = compute_lsim(SourceMetadata(source_id=RAW_DOPPLER_VELOCITY, valid=False, provider_status="available"))
    assert out["lsim_R_scale"] > 1.0
    assert out["source_blocked"] is True
