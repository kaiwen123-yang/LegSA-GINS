from legsa_gins.reporting.n9a_r2_by2_normal_real_plot_materialization import R2Args, run_n9a_r2_by2_normal_real_plot_materialization


# 中文说明：集成测试使用玩具数据验证 runner 能生成报告，但不产生性能结论。
def _write_sources(tmp_path):
    for name in ["gnss1-raw.csv", "gnss2-raw.csv"]:
        (tmp_path / name).write_text("time,value\n0,1\n1,2\n", encoding="utf-8")
    for name in ["gnss1-status.csv", "gnss2-status.csv"]:
        (tmp_path / name).write_text("time,pos_lat,pos_lon,pos_height,rel_pos_e,rel_pos_n,vel_n,vel_e\n0,39,116,40,0,1,0.1,0.2\n1,39.000001,116.000001,40.1,0.1,1,0.2,0.3\n", encoding="utf-8")
    (tmp_path / "trace.csv").write_text("time,lat,lon,height,yaw,pitch,roll\n0,39,116,40,1,0.2,0.1\n1,39.000001,116.000001,40.1,1.2,0.3,0.2\n", encoding="utf-8")
    (tmp_path / "by2.txt").write_text("0 0 0 0\n1 0.1 0.1 0\n", encoding="utf-8")


def _write_algorithm_output(root):
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


def test_n9a_r2_runner_materializes_reports_with_one_real_output(tmp_path):
    _write_sources(tmp_path)
    _write_algorithm_output(tmp_path / "runs" / "N5B" / "baseline_replay")
    args = R2Args(
        by2_plot_root=tmp_path / "plot",
        n8k_tag="N8K-v0.1-BY2-formal-ablation-plot-audit",
        by2_fixposition_root=tmp_path,
        gnss1_raw=tmp_path / "gnss1-raw.csv",
        gnss2_raw=tmp_path / "gnss2-raw.csv",
        gnss1_status=tmp_path / "gnss1-status.csv",
        gnss2_status=tmp_path / "gnss2-status.csv",
        trace_truth=tmp_path / "trace.csv",
        go2_body_imu_highlevel=tmp_path / "by2.txt",
        algorithm_output_search_roots=(),
        clean_replay_root=tmp_path / "clean",
        dual_final_v23_artifact_root=tmp_path / "dual",
        legsa_run_root=tmp_path / "runs",
        output_dir=tmp_path / "out",
        figure_output_dir=tmp_path / "fig",
        case_review_dir=tmp_path / "case",
        summary_dir=tmp_path / "summary",
        index_output_dir=tmp_path / "index",
    )
    summary = run_n9a_r2_by2_normal_real_plot_materialization(args)
    assert summary["available_algorithm_series_count"] == 1
    assert summary["ready_for_N9B"] is False
    assert (tmp_path / "out" / "N9A_R2_ALGORITHM_OUTPUT_DISCOVERY_REPORT.json").exists()
    assert (tmp_path / "out" / "N9A_R2_DECISION_REPORT.json").exists()
