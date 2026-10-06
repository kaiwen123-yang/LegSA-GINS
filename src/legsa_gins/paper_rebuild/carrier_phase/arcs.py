"""Per-receiver, per-signal carrier arcs with explicit unavailable transitions.

Tracking metadata and a TDCP-Doppler diagnostic are not proof of physical
cycle-slip absence. A reset creates a new ambiguity identity; no half-cycle
repair, N rounding, baseline inference or integer acceptance occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .observations import CarrierObservation, EpochKey, ObservationError, SignalIdentity


@dataclass(frozen=True)
class TdcpDopplerCheck:
    dt_s: float
    tdcp_cycles: float
    integrated_doppler_cycles: float
    residual_cycles: float
    tdcp_m: float
    status: str  # CONSISTENT / INCONSISTENT / UNASSESSED


def tdcp_doppler_check(
    previous: CarrierObservation, current: CarrierObservation, *,
    residual_limit_cycles: float | None = None,
) -> TdcpDopplerCheck:
    """Compare phase increment with trapezoidal -D integral over one interval.

    The explicit limit is a deterministic engineering criterion, not a calibrated
    slip test. Doppler integration can disagree through noise, clock behavior,
    nonlinear time variation, multipath or a phase discontinuity.
    """
    if previous.receiver_id != current.receiver_id or previous.signal != current.signal:
        raise ObservationError("TDCP requires the same receiver and full signal identity")
    if not previous.phase_eligible or not current.phase_eligible:
        raise ObservationError("TDCP requires eligible phase endpoints")
    if current.receiver_clock_reset:
        raise ObservationError("TDCP crosses a receiver clock reset")
    dt = current.epoch.seconds_since(previous.epoch)
    if dt <= 0:
        raise ObservationError("TDCP requires strictly increasing time")
    if residual_limit_cycles is not None and (not math.isfinite(residual_limit_cycles) or residual_limit_cycles <= 0):
        raise ObservationError("residual limit must be finite and positive")
    if any(x.doppler_hz is None or not math.isfinite(x.doppler_hz) for x in (previous, current)):
        raise ObservationError("DOPPLER_UNAVAILABLE")
    measured = float(current.phase_cycles) - float(previous.phase_cycles)
    predicted = -0.5 * (float(previous.doppler_hz) + float(current.doppler_hz)) * dt
    residual = measured - predicted
    status = "UNASSESSED" if residual_limit_cycles is None else (
        "CONSISTENT" if abs(residual) <= residual_limit_cycles else "INCONSISTENT")
    return TdcpDopplerCheck(dt, measured, predicted, residual,
                           measured * current.wavelength_m, status)


@dataclass(frozen=True)
class ArcConfig:
    max_gap_s: float
    tdcp_residual_limit_cycles: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.max_gap_s) or self.max_gap_s <= 0:
            raise ObservationError("max_gap_s must be finite and positive")
        if self.tdcp_residual_limit_cycles is not None and (
                not math.isfinite(self.tdcp_residual_limit_cycles) or self.tdcp_residual_limit_cycles <= 0):
            raise ObservationError("tdcp_residual_limit_cycles must be finite and positive")


@dataclass(frozen=True)
class ArcEvent:
    receiver_id: str
    signal: SignalIdentity
    epoch: EpochKey
    arc_id: int | None
    eligible: bool  # current phase candidate observation only
    continued: bool  # same arc token survived metadata and any configured check
    metadata_continuous: bool
    temporal_link_qualified: bool  # both metadata and an explicitly bounded diagnostic
    reasons: tuple[str, ...]
    tdcp: TdcpDopplerCheck | None
    observation: CarrierObservation | None

    @property
    def arc_token(self) -> str | None:
        if self.arc_id is None:
            return None
        s = self.signal
        return f"{self.receiver_id}|{s.gnss_id}:{s.sv_id}:{s.sig_id}:{s.freq_id}|arc={self.arc_id}"


@dataclass
class _State:
    serial: int = 0
    last: CarrierObservation | None = None
    active: bool = False


class ArcTracker:
    """Process complete receiver epochs; omitted known signals are explicit missing.

    A missing whole epoch is recognized through max_gap_s at the next call.
    Out-of-order/duplicate epochs and duplicate signal rows fail before mutation.
    An empty epoch is valid and marks all known receiver signals missing.

    With no TDCP limit, metadata arcs may continue but temporal_link_qualified
    remains false. Consumers must not promote that state into accepted integer
    continuity. Limits and temporal covariance models belong to an explicit
    experiment contract, not adaptive threshold fitting in this tracker.
    """

    def __init__(self, config: ArcConfig):
        self.config = config
        self._states: dict[tuple[str, SignalIdentity], _State] = {}
        self._receiver_epoch: dict[str, EpochKey] = {}

    def update_epoch(
        self, receiver_id: str, epoch: EpochKey,
        observations: Iterable[CarrierObservation], *,
        receiver_clock_reset: bool = False,
    ) -> tuple[ArcEvent, ...]:
        observations = tuple(observations)
        if not receiver_id:
            raise ObservationError("receiver_id is required")
        if receiver_id in self._receiver_epoch and epoch.seconds_since(self._receiver_epoch[receiver_id]) <= 0:
            raise ObservationError("receiver epochs must be strictly increasing; state unchanged")
        if any(o.receiver_id != receiver_id or o.epoch != epoch for o in observations):
            raise ObservationError("receiver/epoch mismatch in batch")
        if len({o.signal for o in observations}) != len(observations):
            raise ObservationError("duplicate full signal identity in epoch")
        if len({o.receiver_clock_reset for o in observations}) > 1:
            raise ObservationError("inconsistent receiver clock-reset metadata")
        reset = receiver_clock_reset or any(o.receiver_clock_reset for o in observations)
        incoming = {o.signal: o for o in observations}
        known = {signal for rx, signal in self._states if rx == receiver_id}
        events = []
        for signal in sorted(known | set(incoming)):
            state = self._states.setdefault((receiver_id, signal), _State())
            obs = incoming.get(signal)
            if obs is None:
                reasons = ("MISSING", "RECEIVER_CLOCK_RESET") if reset else ("MISSING",)
                events.append(ArcEvent(receiver_id, signal, epoch, None, False, False,
                                       False, False, reasons, None, None))
                state.active, state.last = False, None
                continue
            reasons = list(obs.phase_eligibility_reasons)
            if reset:
                reasons.append("RECEIVER_CLOCK_RESET")
            previous = state.last
            if previous is None:
                reasons.append("FIRST_OBSERVATION" if state.serial == 0 else "REACQUIRED_AFTER_MISSING")
            else:
                if obs.epoch.seconds_since(previous.epoch) > self.config.max_gap_s:
                    reasons.append("TIME_GAP")
                if obs.locktime_ms < previous.locktime_ms:
                    reasons.append("LOCKTIME_REGRESSION")
                if obs.half_cycle_valid != previous.half_cycle_valid:
                    reasons.append("HALF_CYCLE_VALIDITY_CHANGED")
                if obs.half_cycle_subtracted != previous.half_cycle_subtracted:
                    reasons.append("HALF_CYCLE_CORRECTION_CHANGED")
                if obs.carrier_valid != previous.carrier_valid:
                    reasons.append("CARRIER_VALIDITY_CHANGED")
                if not state.active:
                    reasons.append("REACQUIRED_AFTER_INVALID")
            metadata_continuous = obs.phase_eligible and state.active and not reasons
            check = None
            if metadata_continuous:
                try:
                    check = tdcp_doppler_check(previous, obs,
                        residual_limit_cycles=self.config.tdcp_residual_limit_cycles)
                except ObservationError:
                    reasons.append("TDCP_DOPPLER_UNAVAILABLE")
                else:
                    if check.status == "INCONSISTENT":
                        reasons.append("TDCP_DOPPLER_INCONSISTENT")
                    elif check.status == "UNASSESSED":
                        reasons.append("TDCP_DOPPLER_UNASSESSED")
            # In metadata-only mode an UNASSESSED diagnostic doesn't invent a
            # break, but it also cannot qualify the link. Missing Doppler does
            # break when a continuity criterion was explicitly requested.
            diagnostic_break = ("TDCP_DOPPLER_INCONSISTENT" in reasons or
                ("TDCP_DOPPLER_UNAVAILABLE" in reasons and self.config.tdcp_residual_limit_cycles is not None))
            continued = bool(metadata_continuous and not diagnostic_break)
            qualified = bool(continued and check is not None and check.status == "CONSISTENT")
            if obs.phase_eligible:
                if not continued:
                    state.serial += 1
                arc_id = state.serial
                state.active = True
            else:
                arc_id = None
                state.active = False
            events.append(ArcEvent(receiver_id, signal, epoch, arc_id, obs.phase_eligible,
                                   continued, bool(metadata_continuous), qualified,
                                   tuple(reasons), check, obs))
            state.last = obs
        self._receiver_epoch[receiver_id] = epoch
        return tuple(events)


def stable_sd_arc_tokens(
    receiver1_events: Iterable[ArcEvent], receiver2_events: Iterable[ArcEvent], *,
    require_qualified_links: bool = True,
) -> dict[SignalIdentity, str]:
    """Combine per-receiver tokens for exact-paired candidate SD ambiguities.

    The default includes only links that passed the caller's configured temporal
    diagnostic. To label the first epoch of an arc, callers must explicitly set
    require_qualified_links=False and enforce subsequent link qualification
    separately. A token is provenance, never evidence that N is correct.
    """
    sides = [tuple(receiver1_events), tuple(receiver2_events)]
    for events in sides:
        if len({e.signal for e in events}) != len(events):
            raise ObservationError("duplicate signal event in receiver batch")
        if len({e.receiver_id for e in events}) > 1 or len({e.epoch for e in events}) > 1:
            raise ObservationError("mixed receiver/epoch arc events")
    if not all(sides):
        return {}
    if sides[0][0].receiver_id == sides[1][0].receiver_id:
        raise ObservationError("SD arc tokens require distinct receivers")
    if sides[0][0].epoch != sides[1][0].epoch:
        raise ObservationError("SD arc tokens require exact epoch pairing")
    left, right = ({e.signal: e for e in events} for events in sides)
    result = {}
    for signal in sorted(left.keys() & right.keys()):
        a, b = left[signal], right[signal]
        if not (a.eligible and b.eligible and a.arc_token is not None and b.arc_token is not None):
            continue
        if require_qualified_links and not (a.temporal_link_qualified and b.temporal_link_qualified):
            continue
        result[signal] = f"SD[{b.arc_token}]-[{a.arc_token}]"
    return result
