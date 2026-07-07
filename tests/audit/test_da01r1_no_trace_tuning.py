from pathlib import Path


def test_da01r1_sources_do_not_enable_trace_tuning():
    paths = list(Path("src/legsa_gins/da_repro").glob("*da01r1*.py"))
    paths += [
        Path("src/legsa_gins/da_repro/rinex_nav_satpos.py"),
        Path("src/legsa_gins/da_repro/dd_design_matrix.py"),
        Path("src/legsa_gins/da_repro/float_baseline_solver.py"),
        Path("scripts/experiments/run_paper10_da3_da01r1_satpos_los_dd_repair.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())
    assert "trace_used_online\": True" not in text
    assert "trace_used_online=True" not in text
    assert "trace_rmse_selected_sign\": True" not in text
    assert "per_case_offset\": True" not in text
