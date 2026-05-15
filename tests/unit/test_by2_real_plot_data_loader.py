import csv
from pathlib import Path

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_formal_ablation_metrics import build_formal_ablation_metrics
from legsa_gins.reporting.by2_formal_ablation_plot_catalog import build_plot_catalog
from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec
from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data
from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root

# 中文说明：toy runtime 提供真实 EVAL/STD 行，验证 loader 不生成空绘图数据。


def make_n8k2_toy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    n8j = tmp_path / "n8j"
    make_toy_n8j_root(n8j)
    _write_runtime(n8j / "variants" / "baseline_no_feedback" / "run")
    _write_runtime(n8j / "variants" / "n8j_selected_conservative_feedback" / "run")
    n8k = tmp_path / "n8k"
    n8k.mkdir()
    spec = build_formal_ablation_spec({"n8j": str(n8j)})
    matrix = build_formal_ablation_matrix(spec)
    metrics = build_formal_ablation_metrics(matrix, n8j)
    write_json(n8k / "N8K_BY2_FORMAL_ABLATION_MATRIX.json", matrix)
    write_json(n8k / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json", metrics)
    write_json(n8k / "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json", _slim_catalog(matrix))
    return n8k, n8j


def test_load_real_plot_data_has_rows(tmp_path: Path):
    n8k, n8j = make_n8k2_toy_inputs(tmp_path)
    bundle = load_real_plot_data(n8k, n8j)
    assert bundle["report"]["variant_count"] == 30
    assert bundle["report"]["unresolved_missing_data_count"] == 0
    assert min(item["plot_row_count"] for item in bundle["variants"].values()) >= 120


def _write_runtime(run: Path) -> None:
    run.mkdir(parents=True, exist_ok=True)
    with (run / "EVAL_NAV.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"])
        for i in range(140):
            writer.writerow([i * 0.1, 39.0 + i * 1e-7, 116.0 + i * 1e-7, 40.0 + i * 0.01, 0.1, 0.2, 0.0, 0.01 * i, 0.02 * i, 1.0 + 0.01 * i])
    with (run / "LegSA_PORT_STD.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", "std_pos_n_m", "std_pos_e_m", "std_pos_d_m", "std_vel_n_mps", "std_vel_e_mps", "std_vel_d_mps", "std_roll_deg", "std_pitch_deg", "std_yaw_deg"])
        for i in range(140):
            writer.writerow([i, 1, 1, 1, 0.1, 0.1, 0.1, 0.5, 0.5, 0.5])
    write_json(run / "RUN_MANIFEST.json", {"runtime_outputs_generated": True})


def _slim_catalog(matrix: dict) -> dict:
    full = build_plot_catalog(matrix)
    keep = {
        "01_trajectory": ["local_trajectory_overlay.png", "trajectory_delta_vector.png"],
        "02_position_errors": ["horizontal_error_time.png"],
        "03_velocity": ["velocity_components_estimate.png"],
        "04_attitude": ["yaw_time.png"],
        "05_consistency": ["position_error_3sigma.png"],
        "06_observation_quality": ["gnss_position_observation.png"],
        "07_compare": ["compare_horizontal_error.png"],
        "08_summary_panels": ["ablation_metric_heatmap_horizontal.png"],
        "10_fgo_factors": ["fgo_factor_residual_by_type.png"],
        "11_feedback": ["feedback_accept_reject_timeline.png"],
        "12_legged_factors": ["contact_probability_time.png"],
        "13_ablation_meta": ["variant_configuration_panel.png"],
        "14_audit_sanity": ["row_count_summary.png"],
    }
    variants = []
    for variant in full["variants"][:2]:
        files = []
        for item in variant["files"]:
            if item["category"] in keep and item["filename"] in keep[item["category"]]:
                copied = dict(item)
                copied["applicable"] = True
                copied["not_applicable_reason"] = ""
                files.append(copied)
        variants.append({"variant_id": variant["variant_id"], "group": variant["group"], "files": files})
    return {"stage": "N8K", "variant_count": len(variants), "category_count": 14, "variants": variants, "paper_performance_claim": False}
