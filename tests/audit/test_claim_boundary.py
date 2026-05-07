"""中文说明：audit 测试验证工程边界，不依赖 raw data，也不产生 numerical performance claim。
"""

from pathlib import Path


def test_claim_boundary_contains_required_n0_guards():
    """
    N0 audit:
    Verify the claim-boundary document carries the minimum forbidden-claim guards.
    """
    root = Path(__file__).resolve().parents[2]
    text = (root / "CLAIM_BOUNDARY.md").read_text(encoding="utf-8")
    for required in [
        "Forbidden Phase-I Claims",
        "evidence_missing",
        "RTK fixed",
        "FGO feedback",
    ]:
        assert required in text
