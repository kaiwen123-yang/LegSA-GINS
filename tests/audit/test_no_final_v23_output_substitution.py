"""中文说明：audit 测试验证工程边界，不依赖 raw data，也不产生 numerical performance claim。
"""

from pathlib import Path


def test_no_final_v23_output_substitution_in_config_or_schema():
    root = Path(__file__).resolve().parents[2]
    config_text = (root / "baseline/final_v23_wrapper/configs/final_v23_wrapper.yaml").read_text(
        encoding="utf-8"
    )
    schema_text = (
        root / "baseline/final_v23_wrapper/manifests/final_v23_manifest.schema.yaml"
    ).read_text(encoding="utf-8")

    assert "proposed_reads_final_v23_output: false" in config_text
    assert "final_v23_output_substitution" in config_text
    assert "proposed_reads_final_v23_output" in schema_text
    assert "final_v23_output_substitution" in schema_text
