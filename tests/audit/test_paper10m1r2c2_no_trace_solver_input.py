from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_m1r2c2_scripts_keep_trace_as_evaluation_only() -> None:
    text = (ROOT / "scripts" / "paper10m1r2c2_clean_sentinel_runner.py").read_text(encoding="utf-8")

    assert "trace_solver_input" in text
    assert "trace_tuned_yaw_fix" in text
    assert "raw_trace_csv" in text
    assert "gnsspath" not in text
