"""Known-truth carrier units/SD/arc tests; no raw records, solver or reference."""
from dataclasses import replace
import math

import pytest

from legsa_gins.paper_rebuild.carrier_phase.observations import (
    AcceptedIntegerSolution, CarrierObservation, EpochKey, IntegerCandidate,
    ObservationError, SignalIdentity, from_rawx, phase_model_cycles,
    signal_frequency_hz, single_difference, wavelength_m,
)
from legsa_gins.paper_rebuild.carrier_phase.arcs import (
    ArcConfig, ArcTracker, tdcp_doppler_check,
)
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    RawxEpoch, RawxMeasurement,
)

GPS = SignalIdentity(0, 6, 0, 0)


def observation(t=10.0, phase=100.0, doppler=-5.0, **kwargs):
    values = dict(receiver_id="rx1", epoch=EpochKey(2408, t), signal=GPS,
                  phase_cycles=phase, doppler_hz=doppler, pseudorange_m=20e6,
                  locktime_ms=1000 + round((t - 10) * 1000),
                  carrier_valid=True, half_cycle_valid=True,
                  half_cycle_subtracted=False, cp_std_code=4, do_std_code=2)
    values.update(kwargs)
    return CarrierObservation(**values)


def step(tracker, obs):
    return tracker.update_epoch(obs.receiver_id, obs.epoch, [obs])[0]


def test_full_identity_and_frequency_are_not_collapsed_to_sv():
    assert GPS != SignalIdentity(0, 6, 3, 0)
    assert GPS != SignalIdentity(2, 6, 0, 0)
    assert GPS != SignalIdentity(6, 6, 0, 0)
    assert wavelength_m(GPS) == pytest.approx(299792458 / 1575420000)
    assert signal_frequency_hz(SignalIdentity(6, 6, 0, 7)) == 1602000000
    assert signal_frequency_hz(SignalIdentity(6, 6, 0, 8)) == 1602562500
    with pytest.raises(ValueError):
        observation(signal=SignalIdentity(0, 6, 0, 7))
    with pytest.raises(ValueError):
        observation(signal=SignalIdentity(0, 6, 99, 0))


def test_rawx_units_flags_and_subhalf_are_preserved():
    raw = RawxMeasurement(GPS, 20e6, 12345.25, 10.0, 64500, 44, 4, 5, 3, 15)
    epoch = RawxEpoch(10.0, 2408, 18, 2, 1, (raw,))
    item = from_rawx("rx1", epoch, raw)
    assert item.phase_cycles == raw.cp_mes_cycles  # NEVER add/subtract .5
    assert item.half_cycle_subtracted and item.receiver_clock_reset
    assert item.phase_std_cycles == 0.020
    assert item.doppler_std_hz == 0.016
    assert item.range_rate_mps() == pytest.approx(-10 * wavelength_m(GPS))
    assert item.phase_m() == pytest.approx(raw.cp_mes_cycles * wavelength_m(GPS))
    with pytest.raises(ObservationError, match="version"):
        from_rawx("rx1", replace(epoch, version=0), raw)
    with pytest.raises(ObservationError, match="belong"):
        from_rawx("rx1", epoch, replace(raw, cp_mes_cycles=8.0))


@pytest.mark.parametrize("kwargs,reason", [
    ({"carrier_valid": False}, "CARRIER_INVALID"),
    ({"half_cycle_valid": False}, "HALF_CYCLE_UNRESOLVED"),
    ({"cp_std_code": 15}, "PHASE_STD_INVALID"),
    ({"phase_cycles": float("nan")}, "PHASE_VALUE_INVALID"),
    ({"phase_cycles": -0.5}, "PHASE_VALUE_INVALID"),
    ({"phase_cycles": None}, "PHASE_VALUE_INVALID"),
    ({"locktime_ms": 0}, "NO_CARRIER_LOCK"),
])
def test_invalid_phase_stays_unavailable(kwargs, reason):
    obs = observation(**kwargs)
    assert not obs.phase_eligible
    assert reason in obs.phase_eligibility_reasons
    with pytest.raises(ObservationError, match=reason):
        obs.phase_m()


def test_sd_sign_integer_truth_clock_and_atmospheric_terms():
    lam = wavelength_m(GPS)
    # Antenna2 has shorter range by .35m along LOS, so geometry SD is -.35m.
    p1 = phase_model_cycles(GPS, 100.0, 10, receiver_clock_range_m=2,
                            satellite_clock_range_m=4, troposphere_m=3, ionosphere_m=1)
    p2 = phase_model_cycles(GPS, 99.65, 13, receiver_clock_range_m=2.2,
                            satellite_clock_range_m=4, troposphere_m=3, ionosphere_m=1)
    a = observation(phase=p1, doppler=4)
    b = observation(phase=p2, doppler=6, receiver_id="rx2")
    sd = single_difference(a, b)
    assert sd.phase_m == pytest.approx(-.35 + .2 + lam * 3)
    assert sd.phase_cycles == pytest.approx((-.35 + .2) / lam + 3)
    assert sd.range_rate_mps == pytest.approx(-lam * 2)
    reversed_sd = single_difference(b, a)
    assert reversed_sd.phase_cycles == -sd.phase_cycles
    assert not hasattr(sd, "baseline_m")  # one satellite gives one scalar, not a 3D pose


@pytest.mark.parametrize("change", [
    {"receiver_id": "rx1"},
    {"epoch": EpochKey(2408, 10.001)},
    {"signal": SignalIdentity(0, 6, 3, 0)},
    {"signal": SignalIdentity(2, 6, 0, 0)},
    {"half_cycle_valid": False},
])
def test_sd_rejects_nonmatching_or_unqualified_pairs(change):
    a = observation()
    b = replace(observation(receiver_id="rx2"), **change)
    with pytest.raises(ValueError):
        single_difference(a, b)


def test_sd_retains_phase_when_optional_code_or_doppler_is_unavailable():
    a = observation()
    b = observation(receiver_id="rx2", phase=102, doppler=None,
                    pseudorange_valid=False)
    sd = single_difference(a, b)
    assert sd.phase_cycles == 2
    assert sd.pseudorange_m is None
    assert sd.doppler_hz is None and sd.range_rate_mps is None


def test_doppler_approach_sign_and_week_rollover_tdcp():
    a = observation(phase=100, doppler=5, epoch=EpochKey(2408, 604799.8))
    b = observation(phase=99, doppler=5, epoch=EpochKey(2409, 0.0))
    result = tdcp_doppler_check(a, b, residual_limit_cycles=1e-8)
    assert result.dt_s == pytest.approx(.2)
    assert result.tdcp_cycles == -1
    assert result.status == "CONSISTENT"
    assert b.range_rate_mps() < 0


def test_clean_arc_and_lock_saturation():
    tracker = ArcTracker(ArcConfig(.3, .05))
    a = observation(locktime_ms=64500)
    first = step(tracker, a)
    second = step(tracker, observation(10.2, 101, locktime_ms=64500))
    assert first.arc_id == 1 and first.eligible and not first.temporal_link_qualified
    assert second.arc_token == first.arc_token
    assert second.continued and second.temporal_link_qualified
    assert second.tdcp.residual_cycles == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("change,reason", [
    ({"locktime_ms": 5}, "LOCKTIME_REGRESSION"),
    ({"receiver_clock_reset": True}, "RECEIVER_CLOCK_RESET"),
    ({"half_cycle_subtracted": True}, "HALF_CYCLE_CORRECTION_CHANGED"),
])
def test_metadata_changes_start_new_arc_without_fixing_phase(change, reason):
    tracker = ArcTracker(ArcConfig(.3, .05))
    first = step(tracker, observation())
    obs = observation(10.2, 101, **change)
    second = step(tracker, obs)
    assert reason in second.reasons
    assert second.arc_id == first.arc_id + 1
    assert not second.continued and not second.temporal_link_qualified
    assert second.observation.phase_cycles == 101


def test_missing_and_gap_do_not_reuse_old_ambiguity_tokens():
    tracker = ArcTracker(ArcConfig(.3, .05))
    first = step(tracker, observation())
    missing = tracker.update_epoch("rx1", EpochKey(2408, 10.2), [])[0]
    assert missing.reasons == ("MISSING",) and missing.arc_id is None
    resumed = step(tracker, observation(10.4, 102))
    assert resumed.arc_id == first.arc_id + 1
    assert "REACQUIRED_AFTER_MISSING" in resumed.reasons
    gap = step(tracker, observation(11, 105))
    assert gap.arc_id == resumed.arc_id + 1 and "TIME_GAP" in gap.reasons


def test_unresolved_half_cycle_is_not_repaired_or_accepted():
    tracker = ArcTracker(ArcConfig(.3, .05))
    first = step(tracker, observation())
    bad = step(tracker, observation(10.2, 101.5, half_cycle_valid=False,
                                    half_cycle_subtracted=True))
    assert not bad.eligible and bad.arc_id is None
    assert bad.observation.phase_cycles == 101.5
    valid = step(tracker, observation(10.4, 102, half_cycle_subtracted=True))
    assert valid.arc_id == first.arc_id + 1
    assert not valid.continued


@pytest.mark.parametrize("integer_jump,noninteger_bias", [(1, 0), (-2, 0), (0, .25)])
def test_truth_distinguishes_integer_slip_from_noninteger_bias(integer_jump, noninteger_bias):
    base_n = 7
    initial = phase_model_cycles(GPS, 100, base_n)
    final_n = base_n + integer_jump
    later = phase_model_cycles(GPS, 100, final_n,
                               noninteger_phase_bias_cycles=noninteger_bias)
    tracker = ArcTracker(ArcConfig(.3, .05))
    a = step(tracker, observation(phase=initial, doppler=0))
    b = step(tracker, observation(10.2, later, doppler=0))
    assert final_n - base_n == integer_jump  # known truth changed only for real integer slip
    assert b.tdcp.residual_cycles == pytest.approx(integer_jump + noninteger_bias)
    assert "TDCP_DOPPLER_INCONSISTENT" in b.reasons
    assert b.arc_id == a.arc_id + 1
    assert b.metadata_continuous  # raw flags alone missed this synthetic discontinuity
    # The diagnostic intentionally does not label the .25-cycle phase bias an integer slip.
    assert all("CYCLE_SLIP" not in r for r in b.reasons)


def test_unbounded_diagnostic_is_not_temporal_qualification():
    tracker = ArcTracker(ArcConfig(.3))
    first = step(tracker, observation())
    second = step(tracker, observation(10.2, 101))
    assert first.arc_id == second.arc_id
    assert second.continued and second.metadata_continuous
    assert not second.temporal_link_qualified
    assert second.tdcp.status == "UNASSESSED"


def test_missing_doppler_breaks_a_requested_temporal_test():
    tracker = ArcTracker(ArcConfig(.3, .05))
    first = step(tracker, observation())
    second = step(tracker, observation(10.2, 101, doppler=None))
    assert second.arc_id == first.arc_id + 1
    assert not second.temporal_link_qualified
    assert "TDCP_DOPPLER_UNAVAILABLE" in second.reasons


def test_receiver_clock_reset_applies_to_every_signal():
    tracker = ArcTracker(ArcConfig(.3, .05))
    a = observation()
    b = replace(a, signal=SignalIdentity(0, 11, 0, 0))
    tracker.update_epoch("rx1", a.epoch, [a, b])
    aa = observation(10.2, 101)
    bb = replace(aa, signal=b.signal)
    events = tracker.update_epoch("rx1", aa.epoch, [aa, bb], receiver_clock_reset=True)
    assert all(e.arc_id == 2 and "RECEIVER_CLOCK_RESET" in e.reasons for e in events)


def test_bad_epoch_batches_fail_before_state_mutation():
    tracker = ArcTracker(ArcConfig(.3, .05))
    a = observation()
    first = step(tracker, a)
    with pytest.raises(ObservationError, match="strictly"):
        step(tracker, a)
    b = observation(10.2, 101)
    with pytest.raises(ObservationError, match="duplicate"):
        tracker.update_epoch("rx1", b.epoch, [b, b])
    with pytest.raises(ObservationError, match="mismatch"):
        tracker.update_epoch("rx2", b.epoch, [b])
    resumed = step(tracker, b)
    assert resumed.arc_token == first.arc_token and resumed.temporal_link_qualified


def test_candidate_and_accepted_integer_types_are_explicitly_separate():
    candidate = IntegerCandidate(("N(rx2-rx1):G06-G11",), (3,), 1.2,
                                 ("rx1|0:6:0:0|arc=1",), True)
    assert candidate.objective_certified
    assert not isinstance(candidate, AcceptedIntegerSolution)
    with pytest.raises(ObservationError, match="named rule"):
        AcceptedIntegerSolution(candidate, "", "")
    record = AcceptedIntegerSolution(candidate, "explicit-test-rule", "synthetic-test-receipt")
    assert record.candidate is candidate  # receipt, not implementation of the named rule
    with pytest.raises(ObservationError):
        IntegerCandidate(("N1",), (3.2,), 1, ())
    with pytest.raises(ObservationError):
        phase_model_cycles(GPS, 100, 3.2)


@pytest.mark.parametrize("args", [(-1, 10), (2408, -1), (2408, 604800), (2408, math.nan)])
def test_invalid_epoch_keys_fail(args):
    with pytest.raises(ObservationError):
        EpochKey(*args)


def test_sd_arc_token_joins_receivers_and_restarts_with_either_receiver():
    from legsa_gins.paper_rebuild.carrier_phase.arcs import stable_sd_arc_tokens
    tracker = ArcTracker(ArcConfig(.3, .05))
    a = observation()
    b = observation(receiver_id="rx2")
    aa = tracker.update_epoch("rx1", a.epoch, [a])
    bb = tracker.update_epoch("rx2", b.epoch, [b])
    assert stable_sd_arc_tokens(aa, bb) == {}  # first epoch: no temporal link yet
    initial = stable_sd_arc_tokens(aa, bb, require_qualified_links=False)[GPS]
    aa = tracker.update_epoch("rx1", EpochKey(2408, 10.2), [observation(10.2, 101)])
    bb = tracker.update_epoch("rx2", EpochKey(2408, 10.2), [observation(10.2, 101, receiver_id="rx2")])
    assert stable_sd_arc_tokens(aa, bb)[GPS] == initial
    aa = tracker.update_epoch("rx1", EpochKey(2408, 10.4), [observation(10.4, 102, receiver_clock_reset=True)])
    bb = tracker.update_epoch("rx2", EpochKey(2408, 10.4), [observation(10.4, 102, receiver_id="rx2")])
    assert stable_sd_arc_tokens(aa, bb) == {}
    assert stable_sd_arc_tokens(aa, bb, require_qualified_links=False)[GPS] != initial
    with pytest.raises(ObservationError, match="distinct"):
        stable_sd_arc_tokens(aa, aa)
    with pytest.raises(ObservationError, match="duplicate"):
        stable_sd_arc_tokens(aa + aa, bb)


def test_rawx_duplicate_identity_cannot_be_silently_selected():
    raw = RawxMeasurement(GPS, 20e6, 123.0, 0, 1000, 44, 4, 5, 3, 7)
    other = replace(raw, cp_mes_cycles=124)
    epoch = RawxEpoch(10, 2408, 18, 0, 1, (raw, other))
    with pytest.raises(ObservationError, match="duplicate"):
        from_rawx("rx1", epoch, raw)


def test_candidate_freezes_mutable_sequences_and_rejects_invalid_receipt():
    labels, integers, tokens = ["N1"], [3], ["arc1"]
    candidate = IntegerCandidate(labels, integers, 1, tokens)
    labels[0], integers[0], tokens[0] = "changed", 8, "changed"
    assert candidate.labels == ("N1",)
    assert candidate.integers == (3,)
    assert candidate.source_arc_tokens == ("arc1",)
    with pytest.raises(ObservationError, match="candidate"):
        AcceptedIntegerSolution(None, "rule", "evidence")
