import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2C_R1_STAGE_ROOT must be set"
    return Path(root)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_clean_yaw_sanity_passes_and_d30_d41_audit_exists():
    sanity = read_csv(stage_root() / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_YAW_SANITY_SUMMARY.csv")
    clean = [row for row in sanity if row["check_id"] == "clean_yaw_by_method"]
    assert len(clean) == 4
    assert all(row["status"] == "PASS" for row in clean)
    family = read_csv(
        stage_root() / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_DUAL_YAW_DEGRADATION_FAMILY_AUDIT.csv"
    )
    assert {row["degradation_type_id"] for row in family} == {f"D{i:02d}" for i in range(30, 42)}
