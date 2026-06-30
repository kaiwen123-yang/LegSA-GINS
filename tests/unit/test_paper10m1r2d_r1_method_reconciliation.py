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


def test_method_reconciliation_has_nine_queue_ids_without_silent_merge():
    rows = read_csv(stage_root() / "03_METHODS" / "PAPER10M1R2D_R1_METHOD_ID_RECONCILIATION.csv")
    assert len(rows) == 9
    methods = {row["ablation_method_id"] for row in rows}
    assert "legsa_without_qm" in methods
    assert "legsa_no_qm" in methods
    assert "legsa_no_fgo_feedback_or_ekf_only" in methods
    assert all(row["queue_status"] == "present" for row in rows)


def test_alias_reconciliation_is_explicit_for_feedback_or_ekf_only():
    text = (stage_root() / "03_METHODS" / "METHOD_ALIAS_RECONCILIATION.md").read_text(encoding="utf-8")
    assert "legsa_no_fgo_feedback_or_ekf_only" in text
    assert "not silently merged" in text
