import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "baseline/final_v23_reproduction/scripts/parse_kfgins_std.py"
spec = importlib.util.spec_from_file_location("parse_kfgins_std", SCRIPT)
parse_kfgins_std = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(parse_kfgins_std)


TOY_STD_ROW_1 = "100.0 1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1"
TOY_STD_ROW_2 = "101.0 1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1"


def test_parse_kfgins_std_and_write_csv(tmp_path):
    std = tmp_path / "KF_GINS_STD.txt"
    std.write_text(f"{TOY_STD_ROW_1}\n{TOY_STD_ROW_2}\n", encoding="utf-8")
    rows = parse_kfgins_std.parse_std_file(std)
    assert len(rows) == 2
    assert rows[0]["tow"] == 100.0
    assert rows[0]["std_pos_n_m"] == 1.0

    output = tmp_path / "FINAL_V23_STD.csv"
    parse_kfgins_std.write_std_csv(rows, output)
    with output.open(newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 2
    assert written[0]["std_yaw_deg"] == "1.0"


def test_parse_kfgins_std_rejects_negative_std(tmp_path):
    std = tmp_path / "bad.txt"
    std.write_text(
        "100.0 -1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        parse_kfgins_std.parse_std_file(std)


def test_parse_kfgins_std_rejects_bad_column_count(tmp_path):
    std = tmp_path / "bad.txt"
    std.write_text("100.0 1 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_kfgins_std.parse_std_file(std)
