from legsa_gins.da_repro.full_backend_classic_runner import classic_case_manifest_rows


def test_da01r2_manifest_has_exact_18_classic_cases():
    rows = classic_case_manifest_rows()
    assert [row["case_id"] for row in rows] == [
        "C00_clean_normal",
        "C01_outage_10s",
        "C02_downsample_2Hz",
        "C03_downsample_1Hz",
        "C04_position_noise_medium_seed0",
        "C05_position_noise_medium_seed1",
        "C06_position_noise_medium_seed2",
        "C07_position_spike_medium_seed0",
        "C08_position_spike_medium_seed1",
        "C09_position_spike_medium_seed2",
        "C10_std_inflation_strong",
        "C11_yaw_spike_10_seed0",
        "C12_yaw_spike_10_seed1",
        "C13_yaw_spike_10_seed2",
        "C14_yawstd_inflation_2x",
        "C15_mixed_medium_seed0",
        "C16_mixed_medium_seed1",
        "C17_mixed_medium_seed2",
    ]
    assert all(row["method_mode"] == "full_backend" for row in rows)
    assert all(row["provider_layer_used"] == "raw_carrier_dd_los" for row in rows)
