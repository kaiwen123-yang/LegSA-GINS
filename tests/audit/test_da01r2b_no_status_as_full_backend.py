from pathlib import Path


def test_da01r2b_no_status_as_real_full_backend_true_literal():
    files = [
        "src/legsa_gins/da_repro/semisynthetic_by2_geometry_validation.py",
        "scripts/experiments/run_paper10_da3_da01r2b_validity_raw_unsupported.py",
    ]
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert '"status_used_as_real_full_backend_output": True' not in text
    assert '"status_baseline_used_as_real_full_backend": True' not in text
    assert '"status_diagnostic_used_as_full_backend": True' not in text
