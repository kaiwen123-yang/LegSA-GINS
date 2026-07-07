from pathlib import Path


def test_da01r2a_no_per_case_offset_enabled():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            Path("src/legsa_gins/da_repro/orientation_audit.py"),
            Path("scripts/experiments/run_paper10_da3_da01r2a_orientation_audit.py"),
        ]
    )
    assert "per_case_offset\": True" not in text
    assert "per_case_offset=True" not in text
