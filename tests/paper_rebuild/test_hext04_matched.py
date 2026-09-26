"""Synthetic-only library checks. NOT_AUTHORIZED_FOR_EXECUTION; no native loops."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext import ext05_sequence_runner as runner
from legsa_gins.paper_rebuild.hext import matched
from legsa_gins.paper_rebuild.horizontal_literature.ext05_pavlasek import (
    ExtendedPose, PavlasekIEKF, so3_exp,
)

ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = ROOT / "configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml"


def _filter(two_receiver=True):
    return PavlasekIEKF(
        ExtendedPose(so3_exp([.3, -.2, .4]), np.array([.2, -.1, .3]), np.array([1., 2., 3.])),
        np.diag([.04, .05, .06, .1, .2, .3, .01, .02, .03]),
        receiver1_from_imu_body_m=[.03, .03, -.30],
        receiver2_from_receiver1_body_m=[0., -.35, 0.],
        gyro_psd=[1e-7] * 3, accelerometer_psd=[1e-4] * 3,
        gravity_ned_mps2=[0., 0., 9.8], two_receiver=two_receiver,
    )


def _measurement(filter_):
    p1 = filter_.pose.position_ned_m + filter_.pose.C_nb @ filter_.lever + [.02, -.03, .01]
    p2 = p1 + filter_.pose.C_nb @ filter_.baseline + [.01, -.02, .03]
    return dict(receiver1_position_ned_m=p1, receiver1_covariance_ned_m2=np.diag([.01, .02, .03]),
                receiver2_position_ned_m=p2, receiver2_covariance_ned_m2=np.diag([.04, .05, .06]))


def _assert_same_state(left, right):
    np.testing.assert_array_equal(left.pose.matrix(), right.pose.matrix())
    np.testing.assert_array_equal(left.covariance, right.covariance)
    assert left.update_count == right.update_count
    assert left.propagation_count == right.propagation_count


def test_three_component_update_directly_delegates_original_exactly():
    original, projected = _filter(), _filter()
    inputs = _measurement(original)
    before = original.update(**inputs)
    after = matched.update_relative_components(projected, **inputs, components=matched.NED_COMPONENTS)
    _assert_same_state(original, projected)
    for key in vars(before):
        np.testing.assert_array_equal(getattr(before, key), getattr(after, key))


def test_ne_system_selects_navigation_axes_and_retains_position_relative_correlation():
    filter_ = _filter()
    inputs = _measurement(filter_)
    full = matched.relative_measurement_system(filter_, **inputs, components=matched.NED_COMPONENTS)
    ne = matched.relative_measurement_system(filter_, **inputs, components=matched.NE_COMPONENTS)
    C = filter_.pose.C_nb
    P = np.zeros((5, 6))
    P[:3, :3] = np.eye(3)
    P[3:, 3:] = C[:2]
    np.testing.assert_array_equal(ne.projection, P)
    np.testing.assert_array_equal(ne.innovation, P @ full.innovation)
    np.testing.assert_array_equal(ne.jacobian, P @ full.jacobian)
    np.testing.assert_array_equal(ne.covariance, P @ full.covariance @ P.T)
    np.testing.assert_allclose(ne.innovation[3:], full.relative_residual_ned_m[:2], atol=1e-15)
    assert not np.allclose(ne.innovation[3:], full.innovation[3:5], atol=1e-5)
    R1, R2 = inputs["receiver1_covariance_ned_m2"], inputs["receiver2_covariance_ned_m2"]
    S = np.eye(3)[:2]
    expected_R = np.block([[C.T @ R1 @ C, -C.T @ R1 @ S.T],
                           [-S @ R1 @ C, S @ (R1 + R2) @ S.T]])
    np.testing.assert_allclose(ne.covariance, expected_R, rtol=1e-14, atol=1e-15)
    assert np.linalg.norm(ne.covariance[:3, 3:]) > 0


def test_ne_update_ignores_pure_navigation_down_relative_perturbation():
    left, right = _filter(), _filter()
    inputs = _measurement(left)
    changed = deepcopy(inputs)
    changed["receiver2_position_ned_m"][2] += .4
    before = matched.update_relative_components(left, **inputs)
    after = matched.update_relative_components(right, **changed)
    np.testing.assert_allclose(before.innovation, after.innovation, rtol=0, atol=1e-15)
    np.testing.assert_allclose(left.pose.matrix(), right.pose.matrix(), rtol=0, atol=2e-15)
    np.testing.assert_array_equal(left.covariance, right.covariance)
    assert before.innovation.shape == (5,)
    assert before.gain.shape == (9, 5)


def _event_arrays(filter_):
    measurement = _measurement(filter_)
    return {"solution_itow": np.array([1000, 1200, 1400, 1600]),
            "p1": np.repeat(measurement["receiver1_position_ned_m"][None], 4, axis=0),
            "p2": np.repeat(measurement["receiver2_position_ned_m"][None], 4, axis=0),
            "pacc1": np.repeat(.01, 4), "pacc2": np.repeat(.02, 4),
            "valid1": np.ones(4, dtype=bool), "valid2": np.ones(4, dtype=bool)}


def _event(callback, filter_, arrays, index, innovation=None, nis=None):
    return callback(filter_, arrays, index, state_time=1000 + index * .2, base_time=1000.,
                    two_receiver=True, method_id="SYNTHETIC_FIXTURE",
                    innovation_rows=innovation if innovation is not None else [],
                    nis_rows=nis if nis is not None else [])


def test_matched_empty_set_uses_existing_single_receiver_update_exactly():
    actual, expected = _filter(), _filter(two_receiver=False)
    arrays = _event_arrays(actual)
    arrays["valid2"][:] = False  # p1-only events must not require receiver 2.
    dispatcher = matched.MatchedEpochUpdate([])
    actual_innovation, actual_nis, expected_innovation, expected_nis = [], [], [], []
    assert _event(dispatcher, actual, arrays, 0, actual_innovation, actual_nis)
    assert runner._h02_gnss_update(expected, arrays, 0, state_time=1000, base_time=1000,
        two_receiver=False, method_id="SYNTHETIC_FIXTURE", innovation_rows=expected_innovation, nis_rows=expected_nis)
    _assert_same_state(actual, expected)
    assert actual.two_receiver is True and actual.H.shape == (6, 9)
    assert actual_innovation == expected_innovation
    assert actual_nis == expected_nis
    assert dispatcher.audit()["single_receiver_update_count"] == 1


def test_matched_schedule_exact_itow_dual_validity_and_original_path_delegation():
    filter_ = _filter()
    arrays = _event_arrays(filter_)
    arrays["valid2"][2] = False
    dispatcher = matched.MatchedEpochUpdate([1000, 1400, 1600])
    assert [_event(dispatcher, filter_, arrays, i) for i in range(4)] == [True, True, False, True]
    audit = dispatcher.audit()
    assert audit["epoch_set_size"] == 3
    assert audit["dual_update_count"] == 2
    assert audit["single_receiver_update_count"] == 1
    assert audit["invalid_update_count"] == 1
    assert audit["epoch_set_not_observed_after_initialization"] == []
    assert [r["update_path"] for r in audit["events"]] == ["ORIGINAL_DUAL", "ORIGINAL_SINGLE_P1", "ORIGINAL_DUAL", "ORIGINAL_DUAL"]


def test_single_event_restores_original_filter_flags_even_on_exception(monkeypatch):
    filter_ = _filter()
    original_H = filter_.H
    arrays = _event_arrays(filter_)
    def fail(*args, **kwargs):
        raise ValueError("synthetic update failure")
    monkeypatch.setattr(filter_, "update", fail)
    with pytest.raises(ValueError, match="synthetic"):
        _event(matched.MatchedEpochUpdate([]), filter_, arrays, 0)
    assert filter_.two_receiver is True and filter_.H is original_H


def test_ne_event_logs_five_degrees_of_freedom_without_fake_down_innovation():
    filter_ = _filter()
    innovation, nis = [], []
    dispatcher = matched.MatchedEpochUpdate(None, components=matched.NE_COMPONENTS)
    assert _event(dispatcher, filter_, _event_arrays(filter_), 0, innovation, nis)
    assert innovation[0]["degrees_of_freedom"] == nis[0]["degrees_of_freedom"] == 5
    assert innovation[0]["innovation_5"] == ""
    assert nis[0]["normalized_nis"] == nis[0]["nis"] / 5
    assert dispatcher.audit()["update_schedule"] == "NATIVE_5HZ"

@pytest.mark.parametrize("bad", [[1.5], [True], [-1], [604800000], [float("nan")]])
def test_scheduler_rejects_ambiguous_or_noninteger_itow(bad):
    with pytest.raises(ValueError, match="iTOW"):
        matched.MatchedEpochUpdate(bad)


def test_unregistered_measurement_selection_rejected():
    with pytest.raises(ValueError, match="components"):
        matched.relative_projection(np.eye(3), ("E", "N"))
    with pytest.raises(ValueError, match="native 5 Hz"):
        matched.MatchedEpochUpdate([1000], components=matched.NE_COMPONENTS)
