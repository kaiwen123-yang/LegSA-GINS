from legsa_gins.source_aware.measurement_source_types import ObservationInnovation
from legsa_gins.source_aware.oim_metric import compute_oim


def test_oim_high_innovation_increases_r_scale():
    # 中文说明：高 innovation 必须提高 R scale。
    out = compute_oim(ObservationInnovation(source_id="raw_doppler_velocity", residual=(5.0, 0.0, 0.0), r_trace=0.03))
    assert out["oim_R_scale"] > 1.0
    assert "oim_raw_doppler_innovation_suspicious" in out["reason_codes"]
