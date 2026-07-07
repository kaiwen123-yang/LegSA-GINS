from pathlib import Path


def test_da01r1_sources_do_not_promote_status_diagnostic_to_full_backend():
    paths = [
        Path("src/legsa_gins/da_repro/float_baseline_solver.py"),
        Path("src/legsa_gins/da_repro/receiver_position.py"),
        Path("scripts/experiments/run_paper10_da3_da01r1_satpos_los_dd_repair.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "status_diagnostic_used_as_full_backend\": True" not in text
    assert "status_yaw_used_as_full_backend\": True" not in text
    assert "status_yaw_heading_used\": True" not in text
