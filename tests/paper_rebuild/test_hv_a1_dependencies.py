"""Six synthetic timing tests; no native run or real scientific input."""
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.hv_a1_dependencies import dependencies


def test_exact_endpoints_have_only_one_nonzero_dependency():
    rows = dependencies([0., 1., 2.], [0., 1., 2.], round_to_ms=False)
    for i, row in enumerate(rows):
        assert row["support"] and row["kind"] == "EXACT_ENDPOINT"
        assert row["endpoint_indices"] == [i]
        assert row["weights"] == [1.]
        assert row["latest_endpoint_source_time"] == row["query_time"]
        assert row["unwrap_prefix_last_index"] == i
        assert row["actual_arrival_qualified"] is False


def test_strict_interior_keeps_both_even_at_float_neighbors():
    rows = dependencies([.25, np.nextafter(1., 0.), np.nextafter(0., 1.)],
                        [0., 1.], round_to_ms=False)
    assert rows[0]["weights"] == [.75, .25]
    for row in rows:
        assert row["support"] and row["kind"] == "INTERIOR"
        assert row["endpoint_indices"] == [0, 1]
        assert all(w > 0 for w in row["weights"])
        assert sum(row["weights"]) == pytest.approx(1.)
        assert row["latest_endpoint_source_time"] > row["query_time"]
        assert row["unwrap_prefix_last_index"] == 1


def test_long_gap_is_open_and_threshold_is_strict():
    at_limit = dependencies([0., .6, 1.2], [0., 1.2], round_to_ms=False)
    assert all(row["support"] for row in at_limit)
    end = np.nextafter(1.2, np.inf)
    above = dependencies([0., .6, end], [0., end], round_to_ms=False)
    assert [row["support"] for row in above] == [True, False, True]
    assert above[1]["kind"] == "LONG_GAP_INTERIOR"
    assert above[1]["endpoint_indices"] == [0, 1]
    assert all(w > 0 for w in above[1]["weights"])
    assert above[2]["endpoint_indices"] == [1]


def test_empty_singleton_and_outside_are_explicit():
    empty = dependencies([-1., 0., 1.], [])
    assert len(empty) == 3
    for row in empty:
        assert not row["support"] and row["kind"] == "NO_ENDPOINTS"
        assert row["endpoint_indices"] == row["weights"] == []
        assert row["latest_endpoint_source_time"] is None
        assert row["unwrap_prefix_last_index"] is None
    single = dependencies([-1., 0., 1.], [0.], round_to_ms=False)
    assert [r["kind"] for r in single] == ["OUTSIDE_LEFT", "EXACT_ENDPOINT", "OUTSIDE_RIGHT"]
    assert [r["support"] for r in single] == [False, True, False]
    assert all(r["endpoint_indices"] == [0] and r["weights"] == [1.] for r in single)
    outside = dependencies([-1., 2.], [0., 1.], round_to_ms=False)
    assert [r["endpoint_indices"] for r in outside] == [[0], [1]]
    assert not any(r["support"] for r in outside)


def test_millisecond_rounding_does_not_relabel_source_time():
    rows = dependencies([0., .0005], [.00049, .00149])
    endpoint, interior = rows
    assert endpoint["kind"] == "EXACT_ENDPOINT" and endpoint["support"]
    assert endpoint["endpoint_coordinates"] == [0.]
    assert endpoint["endpoint_source_times"] == [.00049]
    assert endpoint["latest_endpoint_source_time"] > endpoint["query_time"]
    assert interior["endpoint_coordinates"] == [0., .001]
    assert interior["endpoint_source_times"] == [.00049, .00149]
    assert interior["weights"] == [.5, .5]
    assert interior["scope"] == "CALIBRATED_GNSS18_INTERPOLATION_ENDPOINTS_ONLY"


def test_invalid_and_round_collapsed_inputs_fail_without_repair():
    cases = [
        ([np.nan], [0., 1.], {}),
        ([0.], [0., np.inf], {}),
        ([0.], [0., 0.], {}),
        ([0.], [1., 0.], {}),
        ([0.], [.0001, .0002], {}),
        ([0.], [0., 1.], {"maximum_gap_s": np.nan}),
        ([[0.]], [0., 1.], {}),
        ([0.], [np.finfo(float).max], {}),
    ]
    for query, source, kwargs in cases:
        with pytest.raises(ValueError):
            dependencies(query, source, **kwargs)
