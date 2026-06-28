import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_STAGE_ROOT")
    assert root, "PAPER10M1R2C_STAGE_ROOT must be set for M1R2C artifact tests"
    return Path(root)


def test_provider_regeneration_forbidden_in_guard_report():
    text = (stage_root() / "10_TESTS" / "PAPER10M1R2C_GUARD_VALIDATION_REPORT.md").read_text(encoding="utf-8")
    assert "no provider regeneration: true" in text


def test_locked_queue_uses_provider_ready_manifest_references_only():
    with (stage_root() / "03_QUEUE" / "PAPER10M1R2C_FULL_ALGORITHM_QUEUE_LOCKED.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert all(row["provider_root"].startswith("<DEGRADED_PROVIDER_ROOT>/") for row in rows)
    assert all(row["provider_ready"] == "true" for row in rows)
