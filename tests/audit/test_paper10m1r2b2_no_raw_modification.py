from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_b2_scripts_do_not_open_raw_sources_for_write() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts").glob("paper10m1r2b2_*.py"))
    assert "gnss1-raw.csv" not in text
    assert "gnss2-raw.csv" not in text
    assert "corr-raw.csv" not in text
    assert "by2.txt" not in text
    assert ".open(\"w\"" not in text
    assert ".open('w'" not in text

