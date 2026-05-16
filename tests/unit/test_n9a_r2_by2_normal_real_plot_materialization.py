from pathlib import Path

# 中文说明：单元测试只验证 N9A_R2 发现和决策契约，不验证性能指标。
from legsa_gins.reporting.n9a_r2_by2_normal_real_plot_materialization import (
    R2Args,
    STATUS_R1_SOURCE_LINEAGE_ONLY,
    TARGET_ALGORITHM_SERIES,
    build_decision,
    discover_algorithm_outputs,
)


def _args(tmp_path: Path, *roots: Path) -> R2Args:
    return R2Args(
        by2_plot_root=tmp_path / "plot",
        n8k_tag="N8K-v0.1-BY2-formal-ablation-plot-audit",
        by2_fixposition_root=tmp_path / "fix",
        gnss1_raw=tmp_path / "gnss1-raw.csv",
        gnss2_raw=tmp_path / "gnss2-raw.csv",
        gnss1_status=tmp_path / "gnss1-status.csv",
        gnss2_status=tmp_path / "gnss2-status.csv",
        trace_truth=tmp_path / "trace.csv",
        go2_body_imu_highlevel=tmp_path / "by2.txt",
        algorithm_output_search_roots=tuple(roots),
        clean_replay_root=tmp_path / "clean",
        dual_final_v23_artifact_root=tmp_path / "dual",
        legsa_run_root=tmp_path / "runs",
        output_dir=tmp_path / "out",
        figure_output_dir=tmp_path / "fig",
        case_review_dir=tmp_path / "case",
        summary_dir=tmp_path / "summary",
        index_output_dir=tmp_path / "index",
    )


def _write_algorithm_output(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "LegSA_PORT_NAV.nav").write_text(
        "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n"
        "0 39.0 116.0 40.0 0.0 0.0 0.0 0.1 0.2 1.0\n"
        "1 39.000001 116.000001 40.1 0.1 0.2 0.0 0.2 0.3 1.2\n",
        encoding="utf-8",
    )
    (root / "EVAL_NAV.csv").write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0,39.0,116.0,40.0,0,0,0,0.1,0.2,1.0\n",
        encoding="utf-8",
    )
    (root / "LegSA_PORT_STD.csv").write_text(
        "row,std_pos_n_m,std_pos_e_m,std_pos_d_m,std_vel_n_mps,std_vel_e_mps,std_vel_d_mps,std_roll_deg,std_pitch_deg,std_yaw_deg\n"
        "0,1,1,1,1,1,1,1,1,1\n",
        encoding="utf-8",
    )
    (root / "RUN_MANIFEST.json").write_text('{"port_role": "source_backed_clean_replay_candidate"}\n', encoding="utf-8")
    (root / "summary.json").write_text('{"paper_performance_claim": false}\n', encoding="utf-8")


def test_n9a_r2_discovery_counts_real_nav_and_keeps_target_schema(tmp_path):
    output_root = tmp_path / "runs" / "N5B" / "baseline_replay"
    _write_algorithm_output(output_root)
    discovery = discover_algorithm_outputs(_args(tmp_path))
    assert discovery["algorithm_series_count"] == len(TARGET_ALGORITHM_SERIES)
    assert discovery["available_algorithm_series_count"] == 1
    source_backed = next(item for item in discovery["algorithm_series"] if item["series_name"] == "source_backed_EKF")
    assert source_backed["available"] is True
    assert source_backed["row_count_nav"] == 2
    assert source_backed["can_plot_consistency"] is True


def test_n9a_r2_discovery_excludes_formal_ablation_plot_archive(tmp_path):
    figure_root = tmp_path / "plot" / "N8K2_BY2_formal_ablation_real_plot_fix" / "绘图" / "A0_source_backed_ekf_baseline"
    figure_root.mkdir(parents=True)
    (figure_root / "case_key_metrics_table.csv").write_text("metric,value\nhorizontal_rmse,1\n", encoding="utf-8")
    discovery = discover_algorithm_outputs(_args(tmp_path))
    assert discovery["available_algorithm_series_count"] == 0
    source_backed = next(item for item in discovery["algorithm_series"] if item["series_name"] == "source_backed_EKF")
    assert source_backed["available"] is False
    assert "NAV" in source_backed["missing_reason"] or "excluded" in source_backed["missing_reason"]


def test_n9a_r2_decision_zero_outputs_is_failed():
    discovery = {"available_algorithm_series_count": 0}
    category = {"category_coverage_complete": False}
    plot = {"missing_count": 1}
    semantic = {"N9A_R2_CONSISTENCY_REQUIRES_STD_REPORT.json": {"available_std_series_count": 0}}
    decision = build_decision(discovery, category, plot, semantic)
    assert decision["status"] == "N9A_R2_algorithm_outputs_missing"
    assert decision["ready_for_N9B"] is False
    assert decision["r1_corrected_status"] == STATUS_R1_SOURCE_LINEAGE_ONLY
