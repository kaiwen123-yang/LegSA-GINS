from argparse import Namespace

from legsa_gins.reporting.n9a_r1_by2_source_aligned_normal import ALGORITHM_SERIES, CASE_NAME, R1_CATEGORY_SCHEMA, build_args


# 中文说明：N9A_R1 单元测试锁定正常工况 case model 和源角色参数契约。


def test_n9a_r1_schema_keeps_single_normal_case_categories():
    assert CASE_NAME == "BY2_normal_clean"
    assert list(R1_CATEGORY_SCHEMA) == [
        "01_trajectory",
        "02_position_errors",
        "03_velocity",
        "04_attitude",
        "05_consistency",
        "06_observation_quality",
        "07_compare",
        "08_summary_panels",
        "09_case_review",
        "10_fgo_factors",
        "11_feedback",
        "12_legged_factors",
        "13_degradation_meta",
        "14_audit_sanity",
    ]
    assert "degradation_mask.png" in R1_CATEGORY_SCHEMA["13_degradation_meta"]
    assert "trace_evaluation_only.png" in R1_CATEGORY_SCHEMA["14_audit_sanity"]
    assert len(ALGORITHM_SERIES) == 10


def test_n9a_r1_build_args_preserves_runtime_path_parameters(tmp_path):
    ns = Namespace(
        by2_plot_root=str(tmp_path / "plot"),
        n8k_tag="N8K-v0.1-BY2-formal-ablation-plot-audit",
        by2_fixposition_root=str(tmp_path / "fix"),
        gnss1_raw=str(tmp_path / "gnss1-raw.csv"),
        gnss2_raw=str(tmp_path / "gnss2-raw.csv"),
        gnss1_status=str(tmp_path / "gnss1-status.csv"),
        gnss2_status=str(tmp_path / "gnss2-status.csv"),
        trace_truth=str(tmp_path / "trace.csv"),
        go2_body_imu_highlevel=str(tmp_path / "by2.txt"),
        fixposition_imu_data=str(tmp_path / "imu-data.csv"),
        fixposition_imu_biases=str(tmp_path / "imu-biases.csv"),
        fixposition_imu_temp=str(tmp_path / "imu-temp.csv"),
        ntrip_info=str(tmp_path / "ntrip-info.csv"),
        ntrip_latency=str(tmp_path / "ntrip-latency.csv"),
        corr_raw=str(tmp_path / "corr-raw.csv"),
        tf=str(tmp_path / "tf.csv"),
        tf_static=str(tmp_path / "tf_static.csv"),
        output_dir=str(tmp_path / "out"),
        figure_output_dir=str(tmp_path / "fig"),
        case_review_dir=str(tmp_path / "case"),
        summary_dir=str(tmp_path / "summary"),
        index_output_dir=str(tmp_path / "index"),
        ppt_output_dir=str(tmp_path / "ppt"),
    )
    args = build_args(ns)
    assert args.trace_truth.name == "trace.csv"
    assert args.go2_body_imu_highlevel.name == "by2.txt"
    assert args.fixposition_imu_data.name == "imu-data.csv"
