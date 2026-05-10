from pathlib import Path

from scripts.audit_n5d_raw_doppler_visual_stress_protocol import _toy_visual


def test_n5d_raw_doppler_visual_stress_toy_generates_reports_and_figures(tmp_path: Path):
    # 中文说明：复用审计中的 synthetic toy，验证 stress matrix、图像和报告链路。
    del tmp_path
    _toy_visual()
