from pathlib import Path

from legsa_gins.da_repro.raw_csv_schema_probe import probe_csv


def test_da3r2_raw_csv_schema_probe(tmp_path: Path):
    csv_path = tmp_path / "gnss1-raw.csv"
    csv_path.write_text("Time,name,data\n1.0,UBX-RXM-RAWX,b''\n", encoding="utf-8")
    report = probe_csv(csv_path)
    assert report["file_name"] == "gnss1-raw.csv"
    assert report["column_count"] == 3
