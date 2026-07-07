from pathlib import Path


def test_da03_no_trace_online_true_literal():
    files = [
        "src/legsa_gins/da_repro/wrapped_ls_solver.py",
        "src/legsa_gins/da_repro/method_liu_cwls.py",
        "scripts/experiments/run_paper10_da3_da03_liu_cwls.py",
    ]
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert '"trace_used_online": True' not in text
    assert '"trace_used_for_sign_or_offset": True' not in text
    assert "trace_used_online=True" not in text
