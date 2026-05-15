from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data
from legsa_gins.reporting.by2_real_trajectory_plots import generate_real_trajectory_plot
from tests.unit.test_by2_real_plot_data_loader import make_n8k2_toy_inputs

# 中文说明：轨迹图必须生成非空真实 PNG。


def test_real_trajectory_plot(tmp_path):
    n8k, n8j = make_n8k2_toy_inputs(tmp_path)
    data = load_real_plot_data(n8k, n8j)["variants"]["A1_plus_raw_doppler_ekf"]
    entry = generate_real_trajectory_plot("A1_plus_raw_doppler_ekf", data, "trajectory_delta_vector.png", tmp_path / "delta.png")
    assert entry["nonempty"]
    assert entry["row_count"] >= 100
