from pathlib import Path


def test_da01r2a_no_trace_selected_sign_in_sources():
    paths = [
        Path("src/legsa_gins/da_repro/orientation_audit.py"),
        Path("scripts/experiments/run_paper10_da3_da01r2a_orientation_audit.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "trace_used_for_selection\": True" not in text
    assert "trace_rmse_selected_sign\": True" not in text
    assert "select" in text
