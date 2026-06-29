from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_clean_sentinel_queue_is_four_methods_only() -> None:
    text = (ROOT / "scripts" / "paper10m1r2c2_clean_sentinel_runner.py").read_text(encoding="utf-8")

    assert "METHODS = [" in text
    assert "PAPER10M1R2C2_clean_sentinel_" in text
    assert "ThreadPoolExecutor" not in text
    assert "EXPECTED_ROWS" not in text
