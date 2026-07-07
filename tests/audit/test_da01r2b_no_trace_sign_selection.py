from pathlib import Path


DA01R2B_FILES = [
    "src/legsa_gins/da_repro/synthetic_dd_generator.py",
    "src/legsa_gins/da_repro/synthetic_clambda_validation.py",
    "src/legsa_gins/da_repro/semisynthetic_by2_geometry_validation.py",
    "src/legsa_gins/da_repro/real_raw_failure_diag.py",
    "src/legsa_gins/da_repro/rtklib_independent_check.py",
    "scripts/experiments/run_paper10_da3_da01r2b_validity_raw_unsupported.py",
]


def test_da01r2b_no_trace_sign_selection_literals():
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in DA01R2B_FILES)
    forbidden = [
        '"trace_used_for_selection": True',
        '"trace_used_for_sign_or_offset": True',
        '"trace_rmse_selected_sign": True',
        '"trace_used_online": True',
    ]
    for token in forbidden:
        assert token not in text
