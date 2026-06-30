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


def test_clean_yaw_sanity_passes_for_all_ablation_methods():
    rows = read_csv(stage_root() / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_YAW_SANITY_SUMMARY.csv")
    clean = [row for row in rows if row["check_id"] == "clean_yaw_by_method"]
    assert len(clean) == 9
    assert all(row["status"] == "PASS" for row in clean)


def test_d30_d41_yaw_family_audit_is_present():
    rows = read_csv(
        stage_root() / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_DUAL_YAW_DEGRADATION_FAMILY_AUDIT.csv"
    )
    assert len(rows) == 12 * 9
    assert {row["degradation_type_id"] for row in rows} == {f"D{i:02d}" for i in range(30, 42)}
