"""New block/support/physical-point contracts; never open actual reference."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.fgo_comparison.oisam_inputs import SequenceInput
from legsa_gins.paper_rebuild.fgo_comparison.segmented_diagnostic import partition_intervals, execute_blocks
from legsa_gins.paper_rebuild.fgo_comparison.segmented_evaluation import imu_to_gnss1, score_gnss1, common_rows, reference_metadata


def row(time):
    return np.array([time, 40., 116., 40., .02, .02, .03, 0., 0., 0., .05, .05, .05, 20., 1.5, 1., 1., 1.])


def inputs():
    intervals = np.array([[.9, 1.], [1., 1.1], [1.9, 2.], [2., 2.1], [3.9, 4.], [4., 4.1], [4.1, 4.2]])
    nodes = [(float(t), row(t), t) for t in (1, 2, 3, 4)]
    imu = np.zeros((len(intervals), 7)); imu[:, 0] = intervals[:, 1]
    return SequenceInput("BY2", np.stack([row(t) for t in (1, 2, 3, 4)]), imu, nodes, {}, intervals)


def test_partition_uses_source_intervals_including_singleton_and_gap_epochs():
    blocks, assignment = partition_intervals(inputs().imu_intervals, inputs().nodes, maximum_dt=.100001)
    assert [b["scheduled_nodes"] for b in blocks] == [1, 1, 1]
    assert assignment.tolist() == [1, 2, -1, 3]
    assert blocks[1]["start_s"] == 1.9 and blocks[1]["first_node_s"] == 2.


@pytest.mark.parametrize("intervals", [np.array([[1., 1.]]), np.array([[1., 1.2]]),
    np.array([[1., 1.1], [1.05, 1.15]]), np.array([[1., np.nan]])])
def test_invalid_or_overlapping_interval_never_becomes_a_recovery_block(intervals):
    with pytest.raises(ValueError):
        partition_intervals(intervals, [(1., row(1), 1)])


def test_all_true_gap_blocks_attempted_even_after_prior_numerical_failure():
    invoked = []
    def executor(selected, cfg, state, event, **kwargs):
        invoked.append(selected.nodes[0][0])
        fail = len(invoked) == 1
        time = selected.nodes[0][0]
        state([time, *([np.nan]*9 if fail else [0.]*9), int(not fail), "NUMERICAL_SOLVER_FAILURE" if fail else "INITIALIZED"])
        event({"time_rel_s": time, "mode": "UNAVAILABLE" if fail else "SEGMENT_INITIALIZATION"})
        segment = [] if fail else [{"start_s": time}]
        return {"actual_rows": len(selected.nodes), "segments": segment, "numerical_failure": "fatal" if fail else None}
    rows, events, records = execute_blocks(inputs(), {"gap_policy": "strict_single_initialization_no_gap_bridge", "maximum_imu_interval_s": .100001}, executor=executor)
    assert invoked == [1., 2., 4.] and all(r["attempted"] for r in records)
    assert len(rows) == len(events) == 4 and rows[2][-1] == "NO_CONTINUOUS_IMU_SUPPORT"
    assert records[1]["singleton_prior_only"] and records[1]["dynamic_valid_nodes"] == 0
    assert records[1]["initializations"][0]["yaw_deg"] == 20.
    assert records[1]["initializations"][0]["reference_used"] is False


def test_within_block_extra_initialization_is_rejected():
    def executor(selected, cfg, state, event, **kwargs):
        t = selected.nodes[0][0]
        state([t, *([0.]*9), 1, "INITIALIZED"]); event({"time_rel_s": t})
        return {"actual_rows": 1, "segments": [{"start_s": t}, {"start_s": t}]}
    with pytest.raises(ValueError, match="WITHIN_BLOCK"):
        execute_blocks(inputs(), {"gap_policy": "strict_single_initialization_no_gap_bridge", "maximum_imu_interval_s": .100001}, executor=executor)


def test_optional_factory_default_is_numerically_identical_on_continuous_input():
    from legsa_gins.paper_rebuild.fgo_comparison.oisam import run_inputs, OiSAMGraph
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads((root/"configs/paper_rebuild/fgo_comparison/OISAM_2025.json").read_text())
    times = np.arange(801)*.01
    imu = np.zeros((len(times), 7)); imu[:, 0] = times; imu[:, 6] = -cfg["gravity_mps2"]["BY2"]*.01
    nodes = [(float(t), row(t), t) for t in range(1, 8)]
    data = SequenceInput("BY2", np.stack([row(t) for t in range(1, 8)]), imu, nodes, {})
    one, two, e1, e2 = [], [], [], []
    r1 = run_inputs(data, cfg, one.append, e1.append)
    r2 = run_inputs(data, cfg, two.append, e2.append, graph_factory=OiSAMGraph)
    np.testing.assert_array_equal(np.asarray(one, object), np.asarray(two, object))
    assert r1 == r2 and e1 == e2


def test_actual_native_loop_preserves_numerical_failure_tail_without_within_block_restart():
    from legsa_gins.paper_rebuild.fgo_comparison.oisam import OiSAMGraph
    root = Path(__file__).resolve().parents[2]
    cfg = json.loads((root/"configs/paper_rebuild/fgo_comparison/OISAM_2025.json").read_text())
    cfg["gap_policy"] = "strict_single_initialization_no_gap_bridge"
    times = np.r_[np.arange(1, 301)*.01, np.arange(500, 801)*.01]
    intervals = np.column_stack((times-.01, times))
    imu = np.zeros((len(times), 7)); imu[:, 0] = times; imu[:, 6] = -cfg["gravity_mps2"]["BY2"]*.01
    nodes = [(float(t), row(t), t) for t in (1, 2, 3, 5, 6, 7)]
    data = SequenceInput("BY2", np.stack([row(t) for t in (1, 2, 3, 5, 6, 7)]), imu, nodes, {}, intervals)
    class Failure(OiSAMGraph):
        def step(self, *args):
            raise np.linalg.LinAlgError("INJECTED_NUMERICAL_FAILURE")
    rows, _, blocks = execute_blocks(data, cfg, graph_factory=Failure)
    assert len(blocks) == 2 and all(b["attempted"] for b in blocks)
    assert sum(len(b["initializations"]) for b in blocks) == 2
    assert [r[-1] for r in rows] == ["INITIALIZED", "NUMERICAL_SOLVER_FAILURE:INJECTED_NUMERICAL_FAILURE",
        "AFTER_NUMERICAL_SOLVER_FAILURE", "INITIALIZED", "NUMERICAL_SOLVER_FAILURE:INJECTED_NUMERICAL_FAILURE", "AFTER_NUMERICAL_SOLVER_FAILURE"]


def model():
    def xyz(lat, lon, height):
        a, b = np.deg2rad(lat), np.deg2rad(lon)
        n = 6378137/np.sqrt(1-6.6943799901413165e-3*np.sin(a)**2)
        return ((n+height)*np.cos(a)*np.cos(b), (n+height)*np.cos(a)*np.sin(b), (n*(1-6.6943799901413165e-3)+height)*np.sin(a))
    return SimpleNamespace(lla_to_ecef=xyz, wrap_deg=lambda x: (x+180)%360-180)


def reference():
    return pd.DataFrame({"time": [0., 5.], "lat": [0., 0.], "lon": [0., 0.], "alt": [0., 0.],
                         "roll": [0., 0.], "pitch": [0., 0.], "yaw": [90., 90.]})


def states():
    return pd.DataFrame({"time_rel_s": [1., 2., 3.], "x_ecef_m": [6378137.]*3, "y_ecef_m": [0.]*3,
        "z_ecef_m": [0.]*3, "roll_deg": [0.]*3, "pitch_deg": [0.]*3, "yaw_deg": [0.]*3,
        "valid": [1, 1, 0], "status": ["INITIALIZED", "OK", "MISSING"],
        "prior_only": [1, 0, 0], "dynamic_valid": [0, 1, 0], "block_id": [1, 1, np.nan]})


def test_reference_coordinate_check_metadata_uses_the_registered_anchor():
    metadata = reference_metadata(model(), reference(), {"window_seconds": [1, 3], "baseline_median_m": .4})
    assert metadata == {"anchor_llh_deg_m": [0., 0., 0.], "reference_time_min_s": 0.,
                        "reference_time_max_s": 5., "reference_clean_epoch_count": 2}


def test_point_transform_uses_own_attitude_and_body_lever_not_reference_attitude():
    position = np.array([[6378137., 0., 0.]])
    np.testing.assert_allclose(imu_to_gnss1(position, np.array([[0., 0., 0.]]), [0., .2, 0.]), [[6378137., .2, 0.]], atol=1e-12)
    np.testing.assert_allclose(imu_to_gnss1(position, np.array([[0., 0., 90.]]), [0., .2, 0.]), [[6378137., 0., -.2]], atol=1e-12)
    assert imu_to_gnss1(np.empty((0, 3)), np.empty((0, 3)), [0., .2, 0.]).shape == (0, 3)


def test_primary_excludes_prior_and_secondary_keeps_it_without_changing_denominator():
    spec = {"window_seconds": [1, 3], "baseline_median_m": .4, "dataset_id": "SYNTHETIC"}
    run = {"terminal_status": "ALL_BLOCKS_ATTEMPTED"}
    primary, error, trajectory = score_gnss1(model(), reference(), states(), spec, "OISAM", run, "PRIMARY_DYNAMIC_ONLY", [0., .2, 0.])
    secondary, _, _ = score_gnss1(model(), reference(), states(), spec, "OISAM", run, "SECONDARY_ALL_VALID_POSITION", [0., .2, 0.])
    assert primary["expected_epoch_count"] == secondary["expected_epoch_count"] == 3
    assert primary["matched_epoch_count"] == 1 and secondary["matched_epoch_count"] == 2
    assert primary["missing_or_invalid_count"] == 2 and primary["physical_point"] == "GNSS1_ANTENNA"
    assert np.isnan(error.horizontal_err_m.iloc[0]) and np.isnan(trajectory.x_ecef_m.iloc[0])
    assert primary["horizontal_rmse_m"] == 0 and primary["prior_only_primary_excluded_count"] == 1


def test_no_valid_output_keeps_na_and_position_only_never_gets_attitude_metrics():
    spec = {"window_seconds": [1, 3], "baseline_median_m": .4, "dataset_id": "SYNTHETIC"}
    source = states(); source["valid"] = 0
    row, error, _ = score_gnss1(model(), reference(), source, spec, "GNC", {"terminal_status": "FAILED"}, "PRIMARY_DYNAMIC_ONLY", [0., .2, 0.])
    assert row["matched_epoch_count"] == 0 and row["expected_epoch_count"] == 3
    assert row["horizontal_rmse_m"] is None and "yaw_rmse_deg" not in row
    assert error.horizontal_err_m.isna().all()


def test_common_support_uses_original_keys_and_recomputes_every_metric():
    rows, errors = [], {}
    spec = {"window_seconds": [1, 3], "baseline_median_m": .4, "dataset_id": "SYNTHETIC"}
    for method in ("OISAM", "WEN_TC", "GNC"):
        source = states()
        if method != "OISAM":
            source.time_rel_s -= .002
            source["y_ecef_m"] = .2
        row, error, _ = score_gnss1(model(), reference(), source, spec, method, {"terminal_status": "OK"}, "PRIMARY_DYNAMIC_ONLY", [0., .2, 0.])
        rows.append(row); errors[method] = error
    common, keys = common_rows(rows, errors)
    assert keys == [2] and all(r["matched_epoch_count"] == 1 for r in common)
    assert all(r["first_output_s"] >= 1.998 for r in common)
    errors["GNC"].loc[:, "valid"] = 0
    empty, keys = common_rows(rows, errors)
    assert keys == [] and all(r["horizontal_rmse_m"] is None for r in empty)
