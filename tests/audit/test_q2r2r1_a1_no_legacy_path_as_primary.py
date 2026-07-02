from pathlib import Path


def test_a1_does_not_hardcode_legacy_primary_paths():
    text = Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py").read_text(encoding="utf-8")
    assert ("/mnt/" + "g/LegSA-GINS") not in text
    assert ("C:" + "\\\\Users\\\\ykw") not in text
    assert "Legacy fallback was not selected" in text
