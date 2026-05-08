"""中文说明：测试图像包 manifest 边界字段与人工复核标志。"""

from pathlib import Path

from legsa_gins.visualization.plot_bundle_manifest import build_figure_manifest, write_figure_manifest


def test_manifest_contains_required_flags(tmp_path):
    (tmp_path / "01_trajectory").mkdir()
    (tmp_path / "01_trajectory" / "dual_replay_traj_truth_est.png").write_text("png", encoding="utf-8")
    manifest = build_figure_manifest(
        tmp_path,
        metrics_snapshot={"yaw_rmse_deg": 1.9},
        gates_snapshot={"yaw_gate_pass": True},
    )
    assert manifest["phase"] == "N4H2E"
    assert manifest["manual_visual_review_required"]
    assert not manifest["solver_output_changed"]
    assert not manifest["trace_solver_input"]
    assert not manifest["numerical_performance_claim"]
    path = write_figure_manifest(tmp_path / "figure_manifest.json", manifest)
    assert Path(path).exists()
