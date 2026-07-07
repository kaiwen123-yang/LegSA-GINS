from pathlib import Path


def test_da01r2_no_old_aggregate_or_summary_reconstruction():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            Path("src/legsa_gins/da_repro/full_backend_classic_runner.py"),
            Path("scripts/experiments/run_paper10_da3_da01r2_full_backend_18classic.py"),
        ]
    )
    assert "OLD_IMPORTED_AGGREGATE" not in text
    assert "SUMMARY_RECONSTRUCTED" not in text
    assert "old_aggregate_imported\": True" not in text
    assert "summary_reconstructed\": True" not in text
