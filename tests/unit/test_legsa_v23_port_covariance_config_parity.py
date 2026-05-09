"""中文说明：测试 R3B covariance/config mismatch 分类。"""

from legsa_gins.evaluation.legsa_v23_port_covariance_config_parity import compare_port_config_to_external_policy


BASE_CONFIG = {
    "initpos": "[30,120,10]",
    "initvel": "[0,0,0]",
    "initatt": "[0,0,5]",
    "initposstd": "[10,10,10]",
    "initvelstd": "[1,1,1]",
    "initattstd": "[2,2,2]",
    "arw": "[1,1,1]",
    "vrw": "[0.1,0.1,0.1]",
    "gbstd": "[10,10,10]",
    "abstd": "[80,80,80]",
    "gsstd": "[1,1,1]",
    "asstd": "[1,1,1]",
    "corrtime": "1.0",
    "antlever": "[0,0,-0.25]",
    "clean_input_provenance_label": "clean_status_yaw_no_synthetic_noise",
}


def test_detects_r_too_small():
    config = dict(BASE_CONFIG)
    config["initposstd"] = "[0,0,0]"
    report = compare_port_config_to_external_policy(config)
    assert report["measurement_R_too_small_suspect"] is True
    assert report["config_matches_external_clean_policy"] is False


def test_detects_p_mismatch_and_scheme_c_mismatch():
    config = dict(BASE_CONFIG)
    config["initvelstd"] = "[200,200,200]"
    config["yaw_res_hard_deg"] = "30"
    report = compare_port_config_to_external_policy(config)
    assert report["covariance_P_too_large_suspect"] is True
    assert report["scheme_C_mismatch"] is True


def test_detects_clean_provenance_missing():
    config = dict(BASE_CONFIG)
    config["clean_input_provenance_label"] = "unknown"
    report = compare_port_config_to_external_policy(config)
    assert report["clean_provenance_missing"] is True
