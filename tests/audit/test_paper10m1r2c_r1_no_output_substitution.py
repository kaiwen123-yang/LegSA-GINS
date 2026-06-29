import csv
import os
from pathlib import Path


FORBIDDEN_FIELDS = [
    "final_v23_output_used_as_input",
    "legsa_output_used_as_input",
    "benchmark_output_used_as_input",
    "receiver_imu_data_as_body_imu",
    "go2_position_used_as_truth",
    "go2_yaw_used_as_truth",
    "go2_velocity_used_as_truth",
    "qa_fallback_as_final_method",
    "per_case_tuning_used",
    "output_only_correction_used",
    "epoch_deleted_for_metric",
]


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2C_R1_STAGE_ROOT must be set"
    return Path(root)


def test_no_output_substitution_or_forbidden_inputs():
    with (stage_root() / "05_EXECUTION" / "PAPER10M1R2C_R1_ROW_LEVEL_RESULT_TABLE.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for field in FORBIDDEN_FIELDS:
        assert all(row[field] == "false" for row in rows), field
