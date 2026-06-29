import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2C_R1_STAGE_ROOT must be set"
    return Path(root)


def test_locked_queue_uses_m1r2b2_degraded_provider_alias_only():
    path = stage_root() / "04_QUEUE" / "PAPER10M1R2C_R1_FULL_ALGORITHM_QUEUE_LOCKED.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["provider_root"].startswith("<DEGRADED_PROVIDER_ROOT>/") for row in rows)
    assert not any("paper10m1r2b_v2_by2_degraded_providers" in row["provider_root"] for row in rows)
