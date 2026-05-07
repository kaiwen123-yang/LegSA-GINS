import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "baseline/final_v23_reproduction/scripts/parse_kfgins_nav.py"
spec = importlib.util.spec_from_file_location("parse_kfgins_nav", SCRIPT)
parse_kfgins_nav = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(parse_kfgins_nav)


def test_parse_kfgins_nav_and_write_csv(tmp_path):
    nav = tmp_path / "KF_GINS_Navresult.nav"
    nav.write_text(
        "\n".join(
            [
                "0 100.0 36.0 120.0 10.0 1.0 2.0 -0.1 0.5 -0.3 45.0",
                "0,101.0,36.00001,120.00001,10.2,1.1,2.1,-0.1,0.6,-0.2,45.5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = parse_kfgins_nav.parse_nav_file(nav)
    assert len(rows) == 2
    assert rows[0]["gps_week"] == 0
    assert rows[0]["status"] == "baseline_final_v23"
    assert rows[0]["source_role"] == "baseline"

    output = tmp_path / "FINAL_V23_NAV.csv"
    parse_kfgins_nav.write_nav_csv(rows, output)
    with output.open(newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 2
    assert written[0]["lat_deg"] == "36.0"


def test_parse_kfgins_nav_rejects_bad_column_count(tmp_path):
    nav = tmp_path / "bad.nav"
    nav.write_text("0 100.0 36.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_kfgins_nav.parse_nav_file(nav)


def test_parse_kfgins_nav_rejects_nonmonotonic_tow(tmp_path):
    nav = tmp_path / "bad.nav"
    nav.write_text(
        "\n".join(
            [
                "0 101.0 36.0 120.0 10.0 1.0 2.0 -0.1 0.5 -0.3 45.0",
                "0 100.0 36.0 120.0 10.0 1.0 2.0 -0.1 0.5 -0.3 45.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        parse_kfgins_nav.parse_nav_file(nav)
