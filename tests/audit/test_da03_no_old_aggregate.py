from pathlib import Path


def test_da03_no_old_aggregate_true_literal():
    files = [
        "src/legsa_gins/da_repro/method_liu_cwls.py",
        "scripts/experiments/run_paper10_da3_da03_liu_cwls.py",
    ]
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in files)
    assert '"old_aggregate_imported": True' not in text
    assert "old_aggregate_imported=True" not in text
    assert "OLD_IMPORTED_AGGREGATE" not in text
