from pathlib import Path


Q2R2_FILES = [
    Path("src/legsa_gins/external_dual_methods/method_contracts.py"),
    Path("src/legsa_gins/external_dual_methods/runner.py"),
    Path("scripts/experiments/run_paper10q2r2_dual_antenna_targeted_rerun.py"),
]


def test_q2r2_code_declares_trace_eval_only_and_no_online_usage():
    text = "\n".join(path.read_text(encoding="utf-8") for path in Q2R2_FILES)
    assert "trace_used_online" in text
    assert "trace_used_online\": \"false\"" in text or "trace_used_online=false" in text
    assert "trace-tuned" in text
