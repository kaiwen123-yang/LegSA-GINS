from collections import Counter

from tests.paper10m1r2b_common import EXPECTED_ABLATION_METHODS, EXPECTED_METHOD_MODES, read_csv, read_json


def test_m1r2c_queue_has_2164_rows_locked_for_later_execution():
    rows = read_csv("06_QUEUE_LOCK/PAPER10M1R2C_FULL_ALGORITHM_QUEUE_PROVIDER_READY_DRAFT.csv")
    assert len(rows) == 2164
    assert {row["run_allowed_now"] for row in rows} == {"false"}
    assert {row["solver_allowed_now"] for row in rows} == {"false"}
    assert {row["provider_ready"] for row in rows} == {"true"}
    assert set(Counter(row["method_mode_id"] for row in rows)) == EXPECTED_METHOD_MODES
    assert set(Counter(row["method_mode_id"] for row in rows).values()) == {541}


def test_m1r2d_queue_has_4869_rows_locked_for_later_execution():
    rows = read_csv("06_QUEUE_LOCK/PAPER10M1R2D_INTERNAL_ABLATION_QUEUE_PROVIDER_READY_DRAFT.csv")
    assert len(rows) == 4869
    assert {row["run_allowed_now"] for row in rows} == {"false"}
    assert {row["solver_allowed_now"] for row in rows} == {"false"}
    assert {row["provider_ready"] for row in rows} == {"true"}
    counts = Counter(row["ablation_method_id"] for row in rows)
    assert set(counts) == EXPECTED_ABLATION_METHODS
    assert set(counts.values()) == {541}


def test_queue_hash_reports_expected_counts():
    data = read_json("06_QUEUE_LOCK/PAPER10M1R2_QUEUE_HASH.json")
    assert data["m1r2c_rows"] == 2164
    assert data["m1r2d_rows"] == 4869
