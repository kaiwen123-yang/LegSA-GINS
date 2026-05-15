from scripts.audit_n8k2_real_timeseries_plots import _audit
from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import make_toy_n8k2_root

# 中文说明：时间序列图审计要求 all_real。


def test_n8k2_real_timeseries_plots_toy(tmp_path):
    root = tmp_path / "n8k2"
    make_toy_n8k2_root(root)
    _audit(root)
