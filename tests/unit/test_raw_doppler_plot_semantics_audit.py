from pathlib import Path

from legsa_gins.raw_gnss.raw_doppler_plot_semantics_audit import (
    CORRECTED_3SIGMA_FIGURE,
    deduplicate_stress_pairs,
    generate_semantics_fixed_figures,
)


def _pair(pair_id: str, yaw_delta: float) -> dict[str, object]:
    return {
        "pair_id": pair_id,
        "delta_plus_raw_minus_no_raw": {"yaw_rmse_deg": yaw_delta},
        "raw_doppler_effect": "helps",
    }


def test_plot_semantics_renames_velocity_error_to_consistency(tmp_path: Path):
    # 中文说明：receiver-native velocity 不是 truth，因此图名和报告必须改成 consistency。
    pairs = [{"time": float(i), "diff_norm": 0.1, "raw_3sigma_norm": 0.6} for i in range(250)]
    stress = {
        "pairwise_stress_deltas": [
            _pair("velocity_isolation", -0.4),
            _pair("receiver_velocity_disabled", -0.4),
            _pair("receiver_velocity_std_scale_5", -0.3),
            _pair("receiver_velocity_outage_30s", -0.2),
            _pair("receiver_velocity_noise_0p5", -0.1),
        ]
    }
    report = generate_semantics_fixed_figures(raw_receiver_velocity_pairs=pairs, stress_eval=stress, figure_output_dir=tmp_path)
    assert report["velocity_3sigma_semantics_fixed"] is True
    assert report["new_figure_name"] == CORRECTED_3SIGMA_FIGURE
    assert report["receiver_velocity_not_truth_note"] is True
    assert report["long_labels_fixed"] is True
    assert (tmp_path / CORRECTED_3SIGMA_FIGURE).exists()


def test_plot_semantics_deduplicates_stress_pairs():
    stress = {
        "pairwise_stress_deltas": [
            _pair("velocity_isolation", -0.4),
            _pair("receiver_velocity_disabled", -0.4),
            _pair("receiver_velocity_std_scale_5", -0.3),
            _pair("receiver_velocity_outage_30s", -0.2),
            _pair("receiver_velocity_noise_0p5", -0.1),
        ]
    }
    report = deduplicate_stress_pairs(stress)
    assert report["duplicate_stress_pair_count"] == 1
    assert report["unique_stress_pair_count"] == 4
    assert report["short_label_mapping"]["receiver_velocity_std_scale_5"] == "stdx5"
