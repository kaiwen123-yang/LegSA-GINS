from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_export_clean_has_b2_zip_name_and_path_scan() -> None:
    text = (ROOT / "src/legsa_gins/degradation/m1r2b2_provider_regen.py").read_text(encoding="utf-8")
    assert "paper10m1r2b2_v2_yaw_provider_regen_pack.zip" in text
    assert "export_clean_path_scan.json" in text
    assert "<DEGRADED_PROVIDER_ROOT>" in text

