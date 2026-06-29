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


def test_clean_sentinel_gate_passes_and_yaw_is_trace_labeled():
    rows = read_csv(stage_root() / "02_PREFLIGHT_SENTINEL" / "PAPER10M1R2C_R1_CLEAN_SENTINEL_RESULT_TABLE.csv")
    assert len(rows) == 4
    by_method = {row["method_mode_id"]: row for row in rows}
    assert float(by_method["basic_dual_baseline"]["yaw_rmse_deg"]) <= 10.0
    for method in ["strong_dual_yaw_baseline", "legsa_without_qm", "legsa_full_candidate_with_qm"]:
        assert float(by_method[method]["yaw_rmse_deg"]) <= 5.0
    assert all(row["yaw_reference_role"] == "trace_evaluation_only" for row in rows)
    text = (stage_root() / "02_PREFLIGHT_SENTINEL" / "PAPER10M1R2C_R1_CLEAN_YAW_GATE.md").read_text(
        encoding="utf-8"
    )
    assert "PASS_PAPER10M1R2C_R1_CLEAN_SENTINEL_GATE" in text
