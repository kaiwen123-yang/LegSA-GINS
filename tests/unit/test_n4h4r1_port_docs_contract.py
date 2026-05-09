"""中文说明：锁定 N4H4R1 文档中的 port boundary。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_n4h4r1_docs_contract_terms():
    docs = [
        ROOT / "docs/experiments/n4h4r1_source_backed_port_foundation.md",
        ROOT / "docs/experiments/n4h4r1_port_boundary.md",
        ROOT / "docs/experiments/n4h4r1_next_stage_clean_parity_plan.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in docs)
    assert "final_v23 is not proposed" in text
    assert "diagnostic/self-written attempt" in text
    assert "source-backed port-core" in text
    assert "not performance evidence" in text
    assert "No factor claims until port parity" in text

