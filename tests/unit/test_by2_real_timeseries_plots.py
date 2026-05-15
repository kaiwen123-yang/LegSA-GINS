from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data
from legsa_gins.reporting.by2_real_timeseries_plots import generate_real_timeseries_plot
from tests.unit.test_by2_real_plot_data_loader import make_n8k2_toy_inputs

# 中文说明：时间序列图必须有非空曲线和行数记录。


def test_real_timeseries_plot(tmp_path):
    n8k, n8j = make_n8k2_toy_inputs(tmp_path)
    data = load_real_plot_data(n8k, n8j)["variants"]["A1_plus_raw_doppler_ekf"]
    entry = generate_real_timeseries_plot("A1_plus_raw_doppler_ekf", data, "02_position_errors", "horizontal_error_time.png", tmp_path / "horizontal.png")
    assert entry["nonempty"]
    assert entry["real_data"] is True
