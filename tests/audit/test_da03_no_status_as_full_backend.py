from pathlib import Path


def test_da03_no_status_as_full_backend_true_literal():
    files = [
        "src/legsa_gins/da_repro/method_liu_cwls.py",
        "scripts/experiments/run_paper10_da3_da03_liu_cwls.py",
    ]
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert '"status_diagnostic_used_as_full_backend": True' not in text
    assert '"status_yaw_as_full_backend": True' not in text
    assert "status_diagnostic_used_as_full_backend=True" not in text
