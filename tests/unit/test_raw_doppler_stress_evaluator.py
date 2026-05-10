from legsa_gins.raw_gnss.raw_doppler_stress_evaluator import evaluate_n5d_stress_pairs


def _report(name, h, up=1.0, yaw=1.0, raw=False):
    return {
        "variant_id": name,
        "summary": {
            "horizontal_rmse_m": h,
            "up_rmse_m": up,
            "yaw_rmse_deg": yaw,
            "roll_rmse_deg": 0.1,
            "pitch_rmse_deg": 0.1,
        },
        "raw_doppler_update_count": 3 if raw else 0,
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
    }


def test_pairwise_no_raw_vs_plus_raw_deltas_are_diagnostic_only():
    # 中文说明：delta 是 plus_raw - no_raw，负值只作为诊断帮助证据。
    reports = [
        _report("baseline_full", 1.0),
        _report("baseline_plus_raw_doppler_r1", 0.99, raw=True),
        _report("position_yaw_only", 2.0),
        _report("position_yaw_plus_raw_doppler_r1", 1.8, raw=True),
        _report("receiver_velocity_disabled_no_raw", 2.0),
        _report("receiver_velocity_disabled_plus_raw", 1.6, raw=True),
        _report("receiver_velocity_std_scale_5_no_raw", 1.8),
        _report("receiver_velocity_std_scale_5_plus_raw", 1.6, raw=True),
        _report("receiver_velocity_outage_30s_no_raw", 2.1),
        _report("receiver_velocity_outage_30s_plus_raw", 1.9, raw=True),
        _report("receiver_velocity_noise_0p5_no_raw", 1.7),
        _report("receiver_velocity_noise_0p5_plus_raw", 1.6, raw=True),
    ]
    report = evaluate_n5d_stress_pairs(reports)
    disabled = [row for row in report["pairwise_stress_deltas"] if row["pair_id"] == "receiver_velocity_disabled"][0]
    assert disabled["delta_plus_raw_minus_no_raw"]["horizontal_rmse_m"] < 0
    assert disabled["raw_doppler_effect"] == "helps"
    assert report["stress_help_pair_count"] >= 2
    assert report["paper_performance_claim"] is False
    assert report["proposed_factor_claim"] is False
