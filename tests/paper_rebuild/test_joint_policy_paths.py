"""One continuous two-source navigation case and independent full-policy replay."""
import time

import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator
from legsa_gins.paper_rebuild.joint_navigation.support_policy import canonical_policy, policy_identity


def two_group_events():
    events = []
    for index in range(20):
        t = index*.1
        group = "A" if index < 6 else "B"
        displacement = min(max(index-2, 0)*.04, .12) if group == "A" else -min(max(index-8, 0)*.035, .105)
        feet = [dict(arc_id=f"{group}{foot}", foot_id=foot, force=120.,
                     point_body=np.array([.2+displacement, (-1.)**foot*.15, -.5])) for foot in range(2)]
        events.append(dict(time_s=t, feet=feet,
            imu=np.array([[.1, 0., 0., -9.81, 0., 0., 0.]]) if index else np.empty((0, 7)),
            gnss_position=np.array([.003*np.sin(index), 0., .5]), gnss_velocity=np.zeros(3),
            carrier=EpochBlock(t, np.array([0., -.35, 0.]), np.empty((3, 0)),
                               np.eye(3), np.eye(3)*.0001, ())))
    return events


def test_continuous_policy_paths_equal_independent_full_history_reconstruction():
    started = time.monotonic()
    events = two_group_events()
    metadata = dict(baseline_body=[0., -.35, 0.], support_inference="shared_separator", lag_s=.3,
                    accel_bias_random_walk=0., gyro_bias_random_walk=0.,
                    gnss_position_sigma=.015, gnss_velocity_sigma=.015)
    navigator = JointNavigator(metadata, "U3")
    result = navigator.run(events)
    expected_policy = canonical_policy([
        dict(group_id="first_observed_group", arc_ids=("A0", "A1"), mode="common_translation_release"),
        dict(group_id="second_observed_group", arc_ids=("B0", "B1"), mode="common_translation_release")])
    identity = policy_identity(expected_policy)
    track = navigator.support_tracks[identity]
    assert track.edit_count == 2 and track.policy == expected_policy
    assert track.origin.time_s < 0. and track.first_use == 0.
    assert track.parent_ids and all(parent in navigator.support_tracks for parent in track.parent_ids)
    assert set(navigator.policy_parent_cursors) == set(navigator.support_tracks)
    assert all(len({arc for part in item.policy for arc in part["arc_ids"]}) ==
               sum(len(part["arc_ids"]) for part in item.policy) for item in navigator.support_tracks.values())
    items = [decision for decision in result["decisions"] if decision["kind"] == "SOURCE_POLICY_PATH_ITEM_EXPLORED"]
    assert items and max(sum(item["time_s"] == t for item in items) for t in {item["time_s"] for item in items}) <= 2
    unsupported_fifo = sum(item["route"] == "FIFO_FAIR_EXPLORATION" and not item["parent_was_supported"] for item in items)
    assert unsupported_fifo > 0
    assert result["rows"][0]["policy_search"]["pending_parent_group_items"] > 0
    assert not result["rows"][0]["policy_search"]["exploration_started"]

    # Independently specify the two complete source edits. Use the same causal
    # row identities/common charts, never sum parent scores or copy their states.
    independent = JointNavigator(navigator.metadata, "U3", monitor_support=False,
                                 support_models=list(expected_policy))
    independent._restore(track.origin)
    independent.events = navigator.recovery_events
    for index, event in enumerate(events):
        independent._advance(independent._filter(event), index, navigator.recovery_rows[index],
                             None if track.nonlinear_expanded else navigator.anchor_history[index])
    actual, expected = track.navigator.branches[0], independent.branches[0]
    state_error = max(float(np.max(np.abs(actual.current_output()[name]-expected.current_output()[name])))
                      for name in ("p", "v", "rpy_rad", "bias"))
    score_error = abs(actual.predictive_score-expected.predictive_score)
    np.testing.assert_allclose(state_error, 0., atol=2e-10)
    np.testing.assert_allclose(score_error, 0., atol=2e-8)
    assert actual.predictive_row_count == expected.predictive_row_count
    assert track.navigator.predictive_rows_fingerprint == independent.predictive_rows_fingerprint
    assert navigator._same_predictive_rows(track.navigator)
    alternatives, costs, _, _, _ = navigator._contact_support(events[-1])
    selected = next(j for j, alternative in enumerate(alternatives) if alternative[0] == identity)
    np.testing.assert_allclose(costs[selected], actual.predictive_score+2*navigator.model_edit_cost, atol=1e-10)

    # Exercise full-policy nonlinear expansion explicitly if this conditional
    # was not the online winner, then rebuild that same complete policy afresh.
    if not track.nonlinear_expanded:
        navigator._expand_support_history(track, len(events)-1, events[-1]["time_s"])
    nonlinear = JointNavigator(navigator.metadata, "U3", monitor_support=False,
                              support_models=list(expected_policy))
    nonlinear._restore(track.origin)
    nonlinear.events = navigator.recovery_events
    for index, event in enumerate(events):
        nonlinear._advance(nonlinear._filter(event), index, navigator.recovery_rows[index])
    actual, expected = track.navigator.branches[0], nonlinear.branches[0]
    nonlinear_state_error = max(float(np.max(np.abs(actual.current_output()[name]-expected.current_output()[name])))
                                for name in ("p", "v", "rpy_rad", "bias"))
    nonlinear_score_error = abs(actual.predictive_score-expected.predictive_score)
    np.testing.assert_allclose(nonlinear_state_error, 0., atol=2e-10)
    np.testing.assert_allclose(nonlinear_score_error, 0., atol=2e-8)
    return dict(case="TWO_SUCCESSIVE_OBSERVED_ARC_GROUPS_NOT_THE_90S_SCENE", events=len(events),
        elapsed_s=time.monotonic()-started, registered_policies=len(navigator.support_tracks),
        extension_items=len(items), unsupported_parent_fifo_items=unsupported_fifo,
        maximum_pending_items=max(row["policy_search"]["pending_parent_group_items"] for row in result["rows"]),
        maximum_queued_parents=max(row["policy_search"]["queued_parent_count"] for row in result["rows"]),
        final_search=navigator._policy_search_readout(),
        conditional_state_max_abs=state_error, conditional_predictive_score_abs=score_error,
        nonlinear_state_max_abs=nonlinear_state_error, nonlinear_predictive_score_abs=nonlinear_score_error,
        predictive_rows=actual.predictive_row_count)


if __name__ == "__main__":
    import json
    print(json.dumps(test_continuous_policy_paths_equal_independent_full_history_reconstruction(), indent=2))
