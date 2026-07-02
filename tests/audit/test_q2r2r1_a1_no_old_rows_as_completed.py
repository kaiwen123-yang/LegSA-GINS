from pathlib import Path


def test_a1_does_not_promote_old_aggregate_rows():
    text = Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py").read_text(encoding="utf-8")
    assert "OLD_IMPORTED_AGGREGATE" not in text
    assert "PAPER1F diagnostic rows" not in text
