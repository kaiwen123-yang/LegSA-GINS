import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2D_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2D_R1_STAGE_ROOT must be set"
    return Path(root)


def test_claim_boundary_forbids_universal_superiority_and_paper_ready_module_causality():
    text = (stage_root() / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_FORBIDDEN_CLAIMS.md").read_text(
        encoding="utf-8"
    )
    assert "universal superiority" in text
    assert "final paper claim ready" in text
    assert "old M1R2C yaw metrics as paper evidence" in text
    assert "paper-ready module causality without M1R2E review" in text


def test_allowed_claims_are_bounded():
    with (stage_root() / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_ALLOWED_CLAIMS.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["claim_level"] in {"bounded", "guard"} for row in rows)
