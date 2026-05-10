import csv
from pathlib import Path

from legsa_gins.raw_gnss.raw_doppler_clean_ablation_plot_fix import (
    generate_repaired_clean_ablation_figures,
    load_clean_ablation_error_rows,
)


def _write_reference(path: Path, count: int = 1200) -> None:
    lines = [f"0 {i * 0.25:.6f} {39.0+i*1e-9:.12f} {116.0+i*1e-9:.12f} 40.0 0 0 0 0.0 0.0 1.0" for i in range(count)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_eval_nav(path: Path, offset: float, count: int = 1200) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"])
        writer.writeheader()
        for index in range(count):
            writer.writerow(
                {
                    "time": f"{index * 0.25:.6f}",
                    "lat_deg": f"{39.0 + index * 1e-9 + offset:.12f}",
                    "lon_deg": f"{116.0 + index * 1e-9 + offset:.12f}",
                    "height_m": "40.0",
                    "vn": "0",
                    "ve": "0",
                    "vd": "0",
                    "roll_deg": "0.0",
                    "pitch_deg": "0.0",
                    "yaw_deg": "1.0",
                }
            )


def test_clean_ablation_plot_fix_repairs_from_toy_time_series(tmp_path: Path):
    # 中文说明：从真实格式的 EVAL_NAV/reference 重建曲线，不伪造空图。
    n5c = tmp_path / "n5c"
    dual = tmp_path / "dual"
    _write_reference(dual / "KF_GINS_Navresult.nav")
    _write_eval_nav(n5c / "variants" / "baseline_full" / "EVAL_NAV.csv", 1e-8)
    _write_eval_nav(n5c / "variants" / "baseline_plus_raw_doppler_r1" / "EVAL_NAV.csv", 0.8e-8)
    data = load_clean_ablation_error_rows(n5c_root=n5c, n5d_root=None, dual_root=dual)
    assert data["clean_ablation_data_missing"] is False
    report = generate_repaired_clean_ablation_figures(clean_data=data, figure_output_dir=tmp_path / "figs")
    assert report["repaired_figures_count"] == 6
    assert all(not item.empty_plot_suspect for item in report["coverage"])


def test_clean_ablation_plot_fix_rejects_missing_timeseries_without_fabrication(tmp_path: Path):
    dual = tmp_path / "dual"
    _write_reference(dual / "KF_GINS_Navresult.nav")
    data = load_clean_ablation_error_rows(n5c_root=tmp_path / "missing", n5d_root=None, dual_root=dual)
    assert data["clean_ablation_data_missing"] is True
    report = generate_repaired_clean_ablation_figures(clean_data=data, figure_output_dir=tmp_path / "figs")
    assert report["repaired_figures_count"] == 0
    assert report["clean_ablation_data_missing"] is True
