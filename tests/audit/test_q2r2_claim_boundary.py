from pathlib import Path


def test_q2r2_script_writes_forbidden_claim_boundary():
    text = Path("scripts/experiments/run_paper10q2r2_dual_antenna_targeted_rerun.py").read_text(encoding="utf-8")
    assert "Q2R2_FORBIDDEN_CLAIMS.md" in text
    assert "universal superiority" in text
    assert "BY3 yaw generalization" in text
    assert "XB high-precision severe-GNSS" in text
