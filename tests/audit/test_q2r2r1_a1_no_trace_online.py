from pathlib import Path


def test_a1_trace_is_declared_eval_only_not_online():
    files = [
        Path("src/legsa_gins/external_dual/trace_reference_adapter.py"),
        Path("src/legsa_gins/external_dual/method_runner.py"),
        Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "solver_input_allowed" in text
    assert '"trace_used_online": "false"' in text
    assert "trace_tuned_sign_or_offset" in text
    assert '"trace_tuned_sign_or_offset": "true"' not in text
