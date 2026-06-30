import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2D_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2D_R1_STAGE_ROOT must be set"
    return Path(root)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_parallel_smoke_is_bounded_and_successful():
    rows = read_csv(stage_root() / "02_PARALLEL" / "PAPER10M1R2D_R1_PARALLEL_SMOKE_RESULT.csv")
    assert 0 < len(rows) <= 90
    assert {row["ablation_method_id"] for row in rows}
    assert all(row["terminal_status"] == "COMPLETED_EVALUABLE" for row in rows)
    assert len({row["row_id"] for row in rows}) == len(rows)


def test_locked_queue_has_unique_expected_output_roots():
    rows = read_csv(stage_root() / "04_QUEUE" / "PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_LOCKED.csv")
    roots = [row["expected_output_root"] for row in rows]
    assert len(roots) == len(set(roots)) == 4869
