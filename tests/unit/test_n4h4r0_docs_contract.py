"""中文说明：锁定 N4H4R0 文档的失败证据和 claim boundary。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _combined_docs() -> str:
    docs = [
        ROOT / "docs/experiments/n4h4r0_pr21_failure_evidence_freeze.md",
        ROOT / "docs/experiments/n4h4r0_route_reset_decision.md",
        ROOT / "docs/experiments/n4h4r0_source_backed_port_policy.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in docs)


def test_pr21_retained_as_failure_evidence():
    text = _combined_docs()
    assert "PR #21 is not merged" in text
    assert "PR #21 is not closed" in text
    assert "evidence branch" in text
    assert "diagnostic/self-written attempt" in text


def test_final_v23_not_proposed_and_no_performance_claim():
    text = _combined_docs()
    assert "final_v23 is not proposed" in text
    assert "not paper novelty" in text
    assert "no performance claim" in text.lower()
    assert "final_v23 output must not be used as solver input" in text


def test_nine_factor_starts_after_parity():
    text = _combined_docs()
    assert "Factor claims start only after backbone parity" in text
    assert "No nine-factor claim before ablation evidence" in text
    assert "no raw Doppler" in text
    assert "no FGO" in text

