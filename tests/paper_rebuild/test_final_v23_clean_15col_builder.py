from pathlib import Path

from legsa_gins.paper_rebuild.final_v23_clean_input import (
    GNSS_COLUMNS,
    _read_numeric_table,
    build_column_audit,
    load_contract,
    _write_exact_input_tables,
)


CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "configs/paper_rebuild/final_v23_parity_contract.yaml"
)


def test_clean_gnss_table_is_exact_finite_15_columns(tmp_path: Path) -> None:
    path = tmp_path / "FINAL_V23_CLEAN_FRESH.gnss"
    path.write_text(
        "66.0 39.0 116.0 41.0 0.1 0.1 0.2 1.0 2.0 -0.1 0.05 0.05 0.05 90.0 1.5\n"
        "67.0 39.1 116.1 41.1 0.1 0.1 0.2 1.1 2.1 -0.2 0.05 0.05 0.05 91.0 1.5\n",
        encoding="utf-8",
    )

    rows = _read_numeric_table(path, GNSS_COLUMNS)
    audit = build_column_audit(rows, load_contract(CONTRACT))

    assert len(rows) == 2
    assert len(rows[0]) == 15
    assert [row["name"] for row in audit] == list(GNSS_COLUMNS)
    assert all(row["finite_count"] == 2 for row in audit)
    assert all(row["missing_count"] == 0 for row in audit)
    assert audit[13]["name"] == "yaw"
    assert audit[14]["name"] == "yaw_std"


def test_clean_input_serialization_matches_archive_precision(tmp_path: Path) -> None:
    gnss = tmp_path / "fresh.gnss"
    imu = tmp_path / "fresh.imu"
    _write_exact_input_tables(
        gnss,
        imu,
        [[66.123456789, *([1.23456789] * 14)]],
        [[66.123456789, *([0.123456789] * 6)]],
    )
    assert gnss.read_text(encoding="utf-8") == "66.123457 " + " ".join(["1.234568"] * 14) + "\n"
    assert imu.read_text(encoding="utf-8") == "66.123457 " + " ".join(["0.12345679"] * 6) + "\n"


def test_clean_builder_keeps_archived_plus08_base_time_not_utc_midnight() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src/legsa_gins/paper_rebuild/final_v23_clean_input.py"
    ).read_text(encoding="utf-8")
    assert "expected_base_time - source_utc_day_midnight != 8.0 * 3600.0" in source
    assert "archive_base_time_offset_from_utc_midnight_seconds" in source
