"""Check the N4H3 clean/noisy provenance policy doc.

中文说明：provenance policy 测试防止 noisy artifact 被写成 clean nominal。
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_clean_noisy_provenance_policy_doc():
    text = (ROOT / "docs/experiments/clean_noisy_input_provenance_policy.md").read_text(encoding="utf-8")
    assert "Noisy artifact not clean nominal" in text
    assert "Clean replay preferred for N4H4 baseline parity" in text
    assert "No performance claim" in text
