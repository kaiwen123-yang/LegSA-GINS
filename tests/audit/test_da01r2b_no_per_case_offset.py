from pathlib import Path


def test_da01r2b_no_per_case_offset_true_literal():
    files = [
        "src/legsa_gins/da_repro/synthetic_clambda_validation.py",
        "src/legsa_gins/da_repro/semisynthetic_by2_geometry_validation.py",
        "src/legsa_gins/da_repro/real_raw_failure_diag.py",
        "scripts/experiments/run_paper10_da3_da01r2b_validity_raw_unsupported.py",
    ]
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert '"per_case_offset": True' not in text
    assert "per_case_offset=True" not in text
