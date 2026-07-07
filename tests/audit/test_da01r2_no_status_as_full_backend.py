from pathlib import Path


def test_da01r2_no_status_diagnostic_promoted_to_full_backend():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            Path("src/legsa_gins/da_repro/full_backend_classic_runner.py"),
            Path("scripts/experiments/run_paper10_da3_da01r2_full_backend_18classic.py"),
        ]
    )
    assert "status_diagnostic_used_as_full_backend\": True" not in text
    assert "status_yaw_heading_used\": True" not in text
    assert "COMPLETED_EVALUABLE_DIAGNOSTIC_FALLBACK" not in text
