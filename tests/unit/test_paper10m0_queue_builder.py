"""中文说明：PAPER10M0 queue draft tests; 不执行 PAPER10M1。"""

from scripts.paper10m0_method_mode_loader import METHOD_MODE_IDS
from scripts.paper10m0_queue_builder import build_paper10m1_queue, canonical_by2_cases, smoke_queue


def test_paper10m0_canonical_by2_case_count_is_120():
    cases = canonical_by2_cases()
    assert len(cases) == 120
    assert cases[0]["case_id"] == "BY2_NORMAL_CLEAN"


def test_paper10m0_queue_is_locked_and_human_gated():
    rows = build_paper10m1_queue({mode_id: {} for mode_id in METHOD_MODE_IDS}, "<PAPER10M1_FULL_MATRIX_ROOT>")
    assert len(rows) == 480
    assert {row["method_mode_id"] for row in rows} == set(METHOD_MODE_IDS)
    assert all(row["run_allowed_now"] == "false" for row in rows)
    assert all(row["run_allowed_in_paper10m1"] == "true" for row in rows)
    assert all(row["human_approval_required"] == "true" for row in rows)


def test_paper10m0_smoke_queue_is_four_rows():
    rows = smoke_queue()
    assert len(rows) == 4
    assert [row["method_mode_id"] for row in rows] == METHOD_MODE_IDS
    assert all(row["run_allowed_now"] == "true_paper10m0_smoke_only" for row in rows)
