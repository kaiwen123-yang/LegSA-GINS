from pathlib import Path


def test_final_v23_is_not_proposed_in_config_and_docs():
    root = Path(__file__).resolve().parents[2]
    config_text = (root / "baseline/final_v23_wrapper/configs/final_v23_wrapper.yaml").read_text(
        encoding="utf-8"
    )
    docs_text = (root / "docs/final_v23_baseline_wrapper.md").read_text(encoding="utf-8")

    assert "final_v23_is_proposed: false" in config_text
    assert "It is not the proposed method." in docs_text
