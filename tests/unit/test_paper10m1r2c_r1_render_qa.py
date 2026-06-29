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


def test_render_qa_all_required_figures_pass():
    rows = read_csv(stage_root() / "09_FIGURES" / "PAPER10M1R2C_R1_RENDER_QA_REPORT.csv")
    assert len(rows) >= 37
    assert all(row["render_status"] == "PASS" for row in rows)
    assert all(int(row["png_size_bytes"]) > 1000 for row in rows)
    assert all(int(row["pdf_size_bytes"]) > 1000 for row in rows)
