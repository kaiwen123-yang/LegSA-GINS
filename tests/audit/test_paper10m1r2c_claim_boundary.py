import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_STAGE_ROOT")
    assert root, "PAPER10M1R2C_STAGE_ROOT must be set for M1R2C artifact tests"
    return Path(root)


def test_claim_boundary_forbids_universal_superiority_and_m1r2d_completion():
    text = (stage_root() / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_FORBIDDEN_CLAIMS.md").read_text(encoding="utf-8")
    assert "universal superiority" in text
    assert "M1R2D internal ablation completed" in text
    assert "final paper claim ready" in text


def test_allowed_claims_are_bounded():
    with (stage_root() / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_ALLOWED_CLAIMS.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["claim_level"] in {"bounded", "guard"} for row in rows)
