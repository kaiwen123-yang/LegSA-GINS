"""Synthetic causal SDK-force proxy tests, not measured contact validation."""
from dataclasses import asdict, replace
import json
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.support_arcs import (
    FootForceThreshold, SupportArcError, SupportArcTracker, SupportPolicy,
)
from legsa_gins.paper_rebuild.carrier_phase.contact_rotation import (
    FootPositionEpoch, estimate_contact_rotation,
)


def tracker(ids=("FR", "FL"), dwell=.125, gap=.5):
    return SupportArcTracker(
        SupportPolicy(tuple(FootForceThreshold(name, on=30., off=20.) for name in ids),
                      dwell_s=dwell, max_source_gap_s=gap),
        stream_id="synthetic-sdk-stream",
    )


def update(track, t, forces=None, **kwargs):
    if forces is None:
        forces = {name: 40. for name in track.policy.foot_ids}
    availability = kwargs.pop("available_time_s", t)
    return track.update(t, forces, available_time_s=availability, **kwargs)


def stance(track, t=0.):
    first = update(track, t)
    established = update(track, t + .125)
    assert all(v.state == "UNKNOWN" for v in first.feet)
    assert all(v.eligible for v in established.feet)
    return established


def test_initial_high_is_left_censored_and_not_backdated():
    track = tracker()
    first = update(track, 5., available_time_s=5.02)
    pre = update(track, 5.0625, available_time_s=5.07)
    now = update(track, 5.125, available_time_s=5.2)
    assert all(v.state == "UNKNOWN" and not v.eligible and v.token is None for v in first.feet)
    assert all(v.pending_since_source_time_s == 5. for v in pre.feet)
    assert all(v.state == "STANCE" and v.eligible for v in now.feet)
    assert now.time_s == 5.125 and now.available_time_s == 5.2
    assert not any(track.interval_continuity(first, now).values())
    assert not now.physical_no_slip_certified and not now.calibrated_force
    assert not now.intersample_contact_changes_excluded


def test_initial_low_needs_dwell_for_swing_too():
    track = tracker()
    a = update(track, 0, {"FR": 0, "FL": 0})
    b = update(track, .125, {"FR": 0, "FL": 0})
    assert all(v.state == "UNKNOWN" and v.pending_state == "SWING" for v in a.feet)
    assert all(v.state == "SWING" and not v.eligible and v.token is None for v in b.feet)


def test_high_dwell_is_reset_by_band_not_accumulated():
    track = tracker()
    update(track, 0)
    band = update(track, .0625, {"FR": 25, "FL": 25})
    update(track, .125)
    pre = update(track, .1875)
    now = update(track, .25)
    assert all(v.pending_state is None for v in band.feet)
    assert all(v.state == "UNKNOWN" for v in pre.feet)
    assert all(v.eligible for v in now.feet)


def test_stance_can_continue_in_band_without_reclassifying_force():
    track = tracker()
    a = stance(track)
    b = update(track, .1875, {"FR": 25, "FL": 21})
    assert all(v.eligible for v in b.feet)
    assert track.interval_continuity(a, b) == {"FR": True, "FL": True}
    assert b.by_foot()["FR"].force_sdk_units == 25


def test_first_low_retires_before_dwell_and_band_never_restores_old_token():
    track = tracker()
    a = stance(track)
    low = update(track, .1875, {"FR": 20, "FL": 40})
    band = update(track, .25, {"FR": 25, "FL": 40})
    high = update(track, .3125)
    recovered = update(track, .4375)
    assert low.by_foot()["FR"].state == "UNKNOWN"
    assert low.by_foot()["FR"].token is None
    assert "FIRST_LOW_FORCE_RETIRES_EPISODE" in low.by_foot()["FR"].reasons
    assert band.by_foot()["FR"].state == "UNKNOWN"
    assert band.by_foot()["FR"].pending_state is None
    assert not high.by_foot()["FR"].eligible
    assert recovered.by_foot()["FR"].token != a.by_foot()["FR"].token
    assert track.interval_continuity(a, recovered) == {"FR": False, "FL": True}


def test_sustained_low_confirms_swing_only_when_dwell_met():
    track = tracker()
    stance(track)
    low = update(track, .25, {"FR": 0, "FL": 0})
    pre = update(track, .3125, {"FR": 0, "FL": 0})
    swing = update(track, .375, {"FR": 0, "FL": 0})
    assert all(v.state == "UNKNOWN" for v in low.feet + pre.feet)
    assert all(v.state == "SWING" and v.token is None for v in swing.feet)
    pending = update(track, .4375)
    assert all(v.state == "SWING" and v.pending_state == "STANCE" for v in pending.feet)
    recovered = update(track, .5625)
    assert all(v.eligible for v in recovered.feet)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, True, "bad"])
def test_invalid_field_retires_only_affected_foot_without_zero_fill(bad):
    track = tracker()
    a = stance(track)
    failure = update(track, .25, {"FR": bad, "FL": 40})
    assert failure.by_foot()["FR"].state == "UNKNOWN"
    assert failure.by_foot()["FR"].force_sdk_units is None
    assert "INVALID_FORCE_FIELD" in failure.by_foot()["FR"].reasons
    assert failure.by_foot()["FL"].token == a.by_foot()["FL"].token
    update(track, .3125)
    recovered = update(track, .4375)
    assert track.interval_continuity(a, recovered) == {"FR": False, "FL": True}


def test_missing_field_not_interpreted_as_zero_or_previous_force():
    track = tracker()
    a = stance(track)
    missing = update(track, .25, {"FL": 40})
    assert missing.by_foot()["FR"].force_sdk_units is None
    assert missing.by_foot()["FR"].pending_state is None
    assert "MISSING_FORCE_FIELD" in missing.by_foot()["FR"].reasons
    assert track.interval_continuity(a, missing) == {"FR": False, "FL": True}


def test_global_error_resets_all_even_with_high_force():
    track = tracker()
    a = stance(track)
    failure = update(track, .25, source_ok=False)
    assert all(v.state == "UNKNOWN" and v.token is None for v in failure.feet)
    assert all("SOURCE_ERROR" in v.reasons for v in failure.feet)
    update(track, .375)
    recovered = update(track, .5)
    assert not any(track.interval_continuity(a, recovered).values())


def test_per_foot_source_error_is_independent():
    track = tracker()
    a = stance(track)
    failure = update(track, .25, foot_source_ok={"FR": True, "FL": False})
    assert track.interval_continuity(a, failure) == {"FR": True, "FL": False}
    assert "FOOT_SOURCE_ERROR" in failure.by_foot()["FL"].reasons


def test_gap_breaks_tokens_and_recovery_needs_new_dwell():
    track = tracker(gap=.25)
    a = stance(track)
    failure = update(track, .5)
    assert all(v.state == "UNKNOWN" and v.token is None for v in failure.feet)
    assert all("SOURCE_GAP" in v.reasons for v in failure.feet)
    recovered = update(track, .625)
    assert all(v.eligible for v in recovered.feet)
    assert not any(track.interval_continuity(a, recovered).values())


def test_gap_boundary_is_explicit_strict_greater_than():
    track = tracker(gap=.25)
    a = stance(track)
    b = update(track, .375)
    assert all(track.interval_continuity(a, b).values())
    assert not any("SOURCE_GAP" in v.reasons for v in b.feet)


def test_both_endpoints_stance_with_intervening_liftoff_are_not_continuous():
    track = tracker()
    a = stance(track)
    update(track, .25, {"FR": 0, "FL": 0})
    update(track, .375, {"FR": 0, "FL": 0})
    update(track, .5)
    b = update(track, .625)
    assert all(v.state == "STANCE" for v in a.feet + b.feet)
    assert not any(track.interval_continuity(a, b).values())


def test_per_foot_thresholds_not_a_shared_unlabelled_vector():
    policy = SupportPolicy((FootForceThreshold("FR", 30, 20),
                            FootForceThreshold("RL", 60, 50)), .125, .5)
    track = SupportArcTracker(policy, stream_id="two-feet")
    update(track, 0, {"FR": 40, "RL": 40})
    out = update(track, .125, {"FR": 40, "RL": 40})
    assert out.by_foot()["FR"].state == "STANCE"
    assert out.by_foot()["RL"].state == "SWING"


@pytest.mark.parametrize("bad_time", [.125, .1, float("nan"), float("inf")])
def test_rejected_nonmonotonic_or_invalid_time_poison_old_arcs(bad_time):
    track = tracker()
    a = stance(track)
    with pytest.raises(SupportArcError):
        update(track, bad_time)
    assert track.rejected_update_count == 1
    pending = update(track, .25)
    assert all(v.state == "UNKNOWN" for v in pending.feet)
    recovered = update(track, .375)
    assert not any(track.interval_continuity(a, recovered).values())


def test_invalid_availability_or_unknown_identity_cannot_leave_old_arc_alive():
    track = tracker()
    a = stance(track)
    with pytest.raises(SupportArcError, match="AVAILABILITY"):
        update(track, .25, available_time_s=.2)
    with pytest.raises(SupportArcError, match="UNKNOWN_FOOT"):
        update(track, .25, {"wrong-id": 40})
    update(track, .25)
    b = update(track, .375)
    assert not any(track.interval_continuity(a, b).values())


def test_interval_requires_same_tracker_issued_objects_and_order():
    first, second = tracker(), tracker()
    a = stance(first)
    b = update(first, .25)
    foreign = stance(second)
    assert all(first.interval_continuity(a, b).values())
    with pytest.raises(SupportArcError, match="issued"):
        first.interval_continuity(a, foreign)
    with pytest.raises(SupportArcError, match="issued"):
        first.interval_continuity(a, replace(b))
    with pytest.raises(SupportArcError, match="ordered"):
        first.interval_continuity(b, a)
    with pytest.raises(SupportArcError, match="ordered"):
        first.interval_continuity(a, a)
    assert a.by_foot()["FR"].token != foreign.by_foot()["FR"].token


def test_output_serializes_and_does_not_mutate_old_snapshots():
    track = tracker()
    a = stance(track)
    before = json.dumps(asdict(a), sort_keys=True, allow_nan=False)
    update(track, .25, {"FR": float("nan"), "FL": 0})
    assert json.dumps(asdict(a), sort_keys=True, allow_nan=False) == before
    assert all(v.eligible for v in a.feet)


@pytest.mark.parametrize("dwell,gap", [(0, .1), (-.1, .1), (.1, 0), (.1, float("inf"))])
def test_policy_requires_explicit_positive_dwell_and_gap(dwell, gap):
    with pytest.raises(SupportArcError):
        SupportPolicy((FootForceThreshold("FR", 30, 20),), dwell, gap)


def test_policy_rejects_duplicate_ids_or_invalid_threshold_order():
    with pytest.raises(SupportArcError):
        FootForceThreshold("FR", 20, 30)
    with pytest.raises(SupportArcError):
        FootForceThreshold("FR", float("nan"), 20)
    with pytest.raises(SupportArcError):
        SupportPolicy((FootForceThreshold("FR", 30, 20),
                       FootForceThreshold("FR", 30, 20)), .1, .5)


def test_contact_rotation_consumes_proxy_interval_without_promoting_to_contact_truth():
    track = tracker()
    a = stance(track)
    b = update(track, .25)
    points = np.array([[.3, .2, .4], [-.3, -.2, .4]])
    def foot_epoch(support):
        records = support.feet
        return FootPositionEpoch(support.time_s, support.available_time_s,
                                 tuple(v.foot_id for v in records), points,
                                 tuple(v.eligible for v in records),
                                 tuple(v.token for v in records), "FRD")
    proxy = estimate_contact_rotation(
        foot_epoch(a), foot_epoch(b), np.eye(12) * 1e-6,
        linearization_cayley_rate_frd_rad_s=np.zeros(3),
        interval_continuous_support=track.interval_continuity(a, b))
    assert proxy.rank == 2
    assert proxy.principal_rotation_vector_frd_rad is None
    assert not proxy.navigation_admission and not proxy.imu_independence_claim
    update(track, .3125, {"FR": 0, "FL": 40})
    update(track, .375)
    c = update(track, .5)
    excluded = estimate_contact_rotation(
        foot_epoch(a), foot_epoch(c), np.eye(12) * 1e-6,
        linearization_cayley_rate_frd_rad_s=np.zeros(3),
        interval_continuous_support=track.interval_continuity(a, c))
    assert excluded.status == "UNAVAILABLE_SINGLE_STANCE"
    assert excluded.foot_ids == ("FL",)
