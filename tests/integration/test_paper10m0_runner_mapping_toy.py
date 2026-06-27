"""中文说明：PAPER10M0 runner mapping toy test; 不启动 solver。"""

from pathlib import Path

from scripts.paper10m0_method_mode_loader import load_all, resolve_effective_feature_flags
from scripts.paper10m0_runner_adapter import Paper10M0Paths, build_runtime_config


def test_paper10m0_runtime_config_contains_required_safety_flags(tmp_path):
    root = Path(__file__).resolve().parents[2]
    loaded = load_all(root)
    mode = loaded["method_modes"]["legsa_full_candidate_with_qm"].data
    effective = resolve_effective_feature_flags(
        mode,
        {
            "raw_doppler": True,
            "go2_roll_pitch": True,
            "go2_horizontal_velocity": True,
            "go2_joint_factor": True,
            "multi_state_qm": True,
        },
    )
    paths = Paper10M0Paths(
        code_root=root,
        project_root=tmp_path,
        runtime_root=tmp_path / "runtime",
        by2_imu=tmp_path / "input.imu",
        by2_gnss=tmp_path / "input.gnss",
        by2_body=tmp_path / "body_source.txt",
        by2_trace=tmp_path / "trace.csv",
        raw_doppler_provider=tmp_path / "raw.csv",
        go2_attitude_provider=tmp_path / "att.csv",
        go2_horizontal_velocity_provider=tmp_path / "hv.csv",
        go2_joint_provider=tmp_path / "joint.csv",
    )
    config = build_runtime_config(
        "legsa_full_candidate_with_qm",
        mode,
        effective,
        tmp_path / "out",
        paths,
        loaded["config_sha256"],
    )
    assert "method_mode_id: legsa_full_candidate_with_qm" in config
    assert "paper10m0_smoke: true" in config
    assert "paper10m1_full_matrix: false" in config
    assert "trace_solver_input: false" in config
    assert "final_v23_output_solver_input: false" in config
    assert "legsa_output_solver_input: false" in config
    assert "benchmark_output_solver_input: false" in config
    assert "enable_qa_fallback: false" in config
    assert "output_only_correction: false" in config
