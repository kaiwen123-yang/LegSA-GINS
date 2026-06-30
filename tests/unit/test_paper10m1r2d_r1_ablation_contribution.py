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


def test_ablation_contribution_table_has_expected_module_comparisons():
    rows = read_csv(stage_root() / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_ABLATION_CONTRIBUTION_TABLE.csv")
    assert len(rows) == 8
    modules = {row["removed_module"] for row in rows}
    assert {
        "raw_doppler",
        "source_aware_weighting",
        "go2_roll_pitch_prior",
        "go2_horizontal_velocity_prior",
        "go2_joint_factor",
        "multi_state_qm",
        "fgo_feedback_or_ekf_only_alias",
    }.issubset(modules)
    assert all(row["claim_level"] == "bounded_internal_ablation_metric_delta" for row in rows)
    assert all(int(row["case_count"]) == 541 for row in rows)
