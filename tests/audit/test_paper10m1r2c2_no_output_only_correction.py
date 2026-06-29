from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_yaw_repair_rewrites_provider_not_metric_only() -> None:
    text = (ROOT / "scripts" / "paper10m1r2c2_clean_sentinel_runner.py").read_text(encoding="utf-8")

    assert "repair_provider_rows_from_source_yaw" in text
    assert "output_only_correction_used" in text
    assert "output_only_metric_correction" in (
        ROOT / "src" / "legsa_gins" / "evaluation" / "yaw_provider_lineage.py"
    ).read_text(encoding="utf-8")
