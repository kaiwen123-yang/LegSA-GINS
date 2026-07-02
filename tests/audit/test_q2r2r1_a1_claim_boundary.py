from pathlib import Path


def test_a1_claim_boundary_forbids_overclaims():
    text = Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py").read_text(encoding="utf-8")
    assert "universal superiority" in text
    assert "BY3 yaw generalization" in text
    assert "XB high-precision severe-GNSS" in text
    assert "final paper claim ready" in text
