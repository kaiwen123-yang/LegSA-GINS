"""中文说明：time-domain audit 测试不声明硬件同步。"""

from legsa_gins.time_alignment.time_domain_audit import TimeDomainType, infer_time_domain


def test_unix_and_gps_tow_classified_separately():
    unix = infer_time_domain([1.7e9, 1.7e9 + 1.0, 1.7e9 + 2.0])
    tow = infer_time_domain([1000.0, 1001.0, 1002.0])

    assert unix["time_domain"] == TimeDomainType.UNIX_EPOCH_LIKE
    assert tow["time_domain"] == TimeDomainType.GPS_TOW_LIKE

