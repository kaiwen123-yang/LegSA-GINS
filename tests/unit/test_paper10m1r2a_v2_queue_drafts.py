from collections import Counter

from tests.paper10m1r2a_v2_common import read_csv


def test_provider_generation_queue_has_541_locked_rows():
    rows = read_csv("06_QUEUE_DRAFT/PAPER10M1R2B_PROVIDER_GENERATION_QUEUE_DRAFT.csv")
    assert len(rows) == 541
    assert {row["run_allowed_now"] for row in rows} == {"false"}
    assert {row["trace_eval_only"] for row in rows} == {"true"}


def test_full_algorithm_queue_has_2164_rows_and_four_modes():
    rows = read_csv("06_QUEUE_DRAFT/PAPER10M1R2C_FULL_ALGORITHM_QUEUE_DRAFT.csv")
    assert len(rows) == 2164
    assert {row["run_allowed_now"] for row in rows} == {"false"}
    counts = Counter(row["method_mode_id"] for row in rows)
    assert counts == {
        "basic_dual_baseline": 541,
        "strong_dual_yaw_baseline": 541,
        "legsa_without_qm": 541,
        "legsa_full_candidate_with_qm": 541,
    }


def test_internal_ablation_queue_has_4869_rows_and_nine_methods():
    rows = read_csv("06_QUEUE_DRAFT/PAPER10M1R2D_INTERNAL_ABLATION_QUEUE_DRAFT.csv")
    assert len(rows) == 4869
    assert {row["run_allowed_now"] for row in rows} == {"false"}
    counts = Counter(row["ablation_method_id"] for row in rows)
    assert len(counts) == 9
    assert set(counts.values()) == {541}
