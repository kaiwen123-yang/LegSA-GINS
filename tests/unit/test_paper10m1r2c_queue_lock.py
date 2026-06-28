import csv
import os
from collections import Counter
from pathlib import Path


EXPECTED_METHODS = {
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
}


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_STAGE_ROOT")
    assert root, "PAPER10M1R2C_STAGE_ROOT must be set for M1R2C artifact tests"
    return Path(root)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_queue_lock_has_2164_rows_and_four_frozen_modes():
    rows = read_csv(stage_root() / "03_QUEUE" / "PAPER10M1R2C_FULL_ALGORITHM_QUEUE_LOCKED.csv")
    assert len(rows) == 2164
    assert {row["dataset"] for row in rows} == {"BY2"}
    assert {row["method_mode_id"] for row in rows} == EXPECTED_METHODS
    assert Counter(row["method_mode_id"] for row in rows) == {method: 541 for method in EXPECTED_METHODS}
    assert all(row["run_allowed_now"] == "true" for row in rows)
    assert all(row["provider_ready"] == "true" for row in rows)
    assert all(row["effect_validation_status"] == "PASS" for row in rows)
    assert all(row["trace_eval_only"] == "true" for row in rows)
