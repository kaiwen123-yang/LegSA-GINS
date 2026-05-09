import math

from legsa_gins.evaluation.legsa_v23_covariance_unit_parity import (
    acc_bias_mgal_to_mps2,
    arw_deg_sqrt_hr_to_rad_sqrt_s,
    audit_covariance_unit_parity,
    corr_time_hr_to_sec,
    gyro_bias_deg_h_to_rad_s,
    scale_ppm_to_unit,
    vrw_mps_sqrt_hr_to_mps_sqrt_s,
)


# 中文说明：KF-GINS-style 单位换算必须保持显式，不能在审计中脑补。
def test_unit_conversions():
    assert math.isclose(gyro_bias_deg_h_to_rad_s(1.0), math.pi / 180.0 / 3600.0)
    assert math.isclose(acc_bias_mgal_to_mps2(1.0), 1e-5)
    assert math.isclose(scale_ppm_to_unit(1.0), 1e-6)
    assert math.isclose(arw_deg_sqrt_hr_to_rad_sqrt_s(1.0), math.pi / 180.0 / 60.0)
    assert math.isclose(vrw_mps_sqrt_hr_to_mps_sqrt_s(1.0), 1 / 60.0)
    assert math.isclose(corr_time_hr_to_sec(1.0), 3600.0)


# 中文说明：corr time 缺证据时保留 evidence_missing，并标记 covariance unit 可疑。
def test_detects_missing_corr_time_as_unit_suspect():
    report = audit_covariance_unit_parity(
        {
            "initbgstd_internal": 1e-2,
            "initbastd_internal": 1e-2,
            "initsgstd_internal": 1e-2,
            "initsastd_internal": 1e-2,
            "gyr_arw_internal": 1e-8,
            "acc_vrw_internal": 1e-6,
            "gyrbias_std_internal": 1e-12,
            "accbias_std_internal": 1e-10,
            "gyrscale_std_internal": 1e-14,
            "accscale_std_internal": 1e-14,
            "corr_time_internal": "evidence_missing",
        }
    )
    assert report["process_noise_units_ok"] is True
    assert report["corr_time_units_ok"] is False
    assert report["covariance_unit_mismatch_suspect"] is True
