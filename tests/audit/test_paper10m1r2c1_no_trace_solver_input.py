from pathlib import Path


def test_m1r2c1_code_does_not_enable_trace_solver_input():
    root = Path(__file__).resolve().parents[2]
    paths = [
        root / "src/legsa_gins/evaluation/yaw_semantic_audit.py",
        root / "src/legsa_gins/evaluation/qm_trace_semantic_audit.py",
        root / "src/legsa_gins/evaluation/yaw_metric_repair.py",
        root / "scripts/paper10m1r2c1_result_gate.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "trace_solver_input: true" not in text
    assert '"trace_solver_input": true' not in text
    assert "Trace is evaluation-only" in text or "trace_evaluation_only" in text
