from legsa_gins.raw_gnss.raw_doppler_ablation_decision import make_n5c_decision


def test_decision_activation_failed():
    # 中文说明：update_count 为 0 时必须回到激活修复，不能声称 raw Doppler 已生效。
    report = make_n5c_decision({}, {}, {"update_alignment_ok": True, "actual_update_count": 0}, {"raw_doppler_update_count": 0})
    assert report["status"] == "activation_failed"
    assert report["recommended_next_stage"] == "N5B2_raw_doppler_activation_fix"


def test_decision_alignment_issue():
    report = make_n5c_decision({}, {}, {"update_alignment_ok": False, "actual_update_count": 2}, {"raw_doppler_update_count": 2})
    assert report["status"] == "alignment_issue"


def test_decision_source_issue():
    report = make_n5c_decision(
        {},
        {"possible_pvt_velocity_copy_suspect": True},
        {"update_alignment_ok": True, "actual_update_count": 2},
        {"raw_doppler_update_count": 2},
    )
    assert report["status"] == "source_integrity_issue"


def test_decision_degraded_and_ready():
    degraded = make_n5c_decision(
        {},
        {"possible_pvt_velocity_copy_suspect": False},
        {"update_alignment_ok": True, "actual_update_count": 2},
        {"raw_doppler_update_count": 2, "raw_doppler_degrades_diagnostic": True},
    )
    assert degraded["status"] == "noise_model_needed"
    ready = make_n5c_decision(
        {},
        {"possible_pvt_velocity_copy_suspect": False},
        {"update_alignment_ok": True, "actual_update_count": 2},
        {"raw_doppler_update_count": 2, "velocity_isolation_delta": {"horizontal_rmse_m": -0.1}},
    )
    assert ready["status"] == "ablation_ready"
    assert ready["evidence_raw_doppler_independent_velocity_constraint"] is True
