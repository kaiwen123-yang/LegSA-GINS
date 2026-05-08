"""中文说明：N4H4D1 config/init parity 单元测试。"""

from legsa_gins.evaluation.legsa_v23_config_init_parity import compare_config_init


def test_config_init_detects_deg_rad_and_height_issue():
    report = compare_config_init(
        {
            "initpos_deg_m_input": [31.0, 121.0, 10.0],
            "initpos_rad_m_internal": [31.0, 121.0, 0.1],
            "initvel_mps": [0.0, 0.0, 0.0],
            "initatt_deg_input": [0.0, 0.0, 10.0],
            "initatt_rad_internal": [0.0, 0.0, 10.0],
            "initatt_deg_internal_backconverted": [0.0, 0.0, 572.9],
            "initposstd_m": [1.0, 1.0, 1.0],
            "initattstd_deg": [1.0, 1.0, 1.0],
            "antlever_m": [0.0, 0.0, 0.0],
            "imunoise_internal_units": [0.0, 0.0, 0.0],
            "starttime": 1.0,
            "endtime": 0.0,
        },
        {"external_config_status": "evidence_missing"},
    )
    assert report["config_units_issue"] is True
    assert report["height_rad_conversion_issue"] is True
    assert report["initatt_yaw_mismatch"] is True
    assert report["start_end_mismatch"] is True

