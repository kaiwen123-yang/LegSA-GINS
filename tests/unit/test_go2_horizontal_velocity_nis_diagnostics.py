"""中文说明：单元测试覆盖 N7C4 residual/NIS proxy 诊断。"""

import csv
from pathlib import Path

from legsa_gins.go2_prior.go2_horizontal_velocity_nis_diagnostics import summarize_go2_horizontal_velocity_nis


def test_nis_diagnostics_flags_overconfidence(tmp_path: Path):
    path = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "source_id", "residual_norm", "normalized_innovation", "combined_R_scale"])
        writer.writeheader()
        writer.writerow({"time": 0.0, "source_id": "go2_horizontal_velocity", "residual_norm": 1.0, "normalized_innovation": 4.0, "combined_R_scale": 2.0})
    report = summarize_go2_horizontal_velocity_nis("toy", tmp_path)
    assert report["overconfidence_status"] == "overconfident"
    assert report["source_aware_R_inflation_count"] == 1
