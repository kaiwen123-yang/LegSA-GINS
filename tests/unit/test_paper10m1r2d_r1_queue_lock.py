import csv
import os
from collections import Counter
from pathlib import Path


EXPECTED_METHODS = {
    "legsa_full_candidate_with_qm",
    "legsa_without_qm",
    "legsa_no_raw_doppler",
    "legsa_no_source_aware",
    "legsa_no_go2_roll_pitch",
    "legsa_no_go2_horizontal_velocity",
    "legsa_no_go2_joint",
    "legsa_no_qm",
    "legsa_no_fgo_feedback_or_ekf_only",
}


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2D_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2D_R1_STAGE_ROOT must be set"
    return Path(root)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_queue_lock_has_4869_rows_and_yaw_corrected_provider_guards():
    rows = read_csv(stage_root() / "04_QUEUE" / "PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_LOCKED.csv")
    assert len(rows) == 4869
    assert {row["dataset"] for row in rows} == {"BY2"}
    assert {row["ablation_method_id"] for row in rows} == EXPECTED_METHODS
    assert Counter(row["ablation_method_id"] for row in rows) == {method: 541 for method in EXPECTED_METHODS}
    assert len({row["case_id"] for row in rows}) == 541
    assert len({row["expected_output_root"] for row in rows}) == 4869
    assert all(row["provider_ready"] == "true" for row in rows)
    assert all(row["effect_validation_status"] == "PASS" for row in rows)
    assert all(row["yaw_lineage_validation_status"] == "PASS" for row in rows)
    assert all(row["yaw_wrap_validation_status"] == "PASS" for row in rows)
    assert all(row["provider_root"].startswith("<DEGRADED_PROVIDER_ROOT>/") for row in rows)
