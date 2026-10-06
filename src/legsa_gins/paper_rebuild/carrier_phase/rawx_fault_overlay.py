"""Deterministic RAWX-observation-level semi-synthetic carrier faults.

Original UBX bytes are never modified. This is not a receiver/firmware simulator,
not a natural fault label, and not an oracle for the original integers.
"""
from __future__ import annotations
from bisect import bisect_left
from dataclasses import dataclass, replace
import hashlib
import math
import struct
from typing import Mapping, Sequence

from ..horizontal_literature.shared_raw_backend import RawxEpoch, SignalIdentity, identity_text
from .observations import from_rawx
from .arcs import tdcp_doppler_check


@dataclass(frozen=True)
class OverlayPolicy:
    duration_s: float = 1.0
    bias_cycles: float = 0.25
    history_epochs: int = 5
    epoch_interval_s: float = 0.2
    time_tolerance_s: float = 0.01
    tdcp_limit_cycles: float = 0.5
    observation_tail_s: float = 20.0

    def __post_init__(self):
        if (self.duration_s != 1.0 or self.bias_cycles != 0.25 or self.history_epochs != 5
                or self.epoch_interval_s != 0.2 or self.time_tolerance_s != 0.01
                or self.tdcp_limit_cycles != 0.5 or self.observation_tail_s != 20.0):
            raise ValueError("This overlay implements only the fixed three-event contract")


@dataclass(frozen=True)
class OverlayResult:
    epochs: dict[int, tuple[RawxEpoch, ...]]
    audit: dict


def local_time(epoch: RawxEpoch, base_time: float) -> float:
    return 315964800.0 + epoch.gps_week * 604800.0 + epoch.gps_tow_seconds - epoch.leap_seconds - base_time


def code_doppler_fingerprint(epochs: Mapping[int, Sequence[RawxEpoch]]) -> str:
    """All time/code/Doppler/clock identity, excluding the three authorized fields."""
    h = hashlib.sha256()
    for rx in (1, 2):
        h.update(struct.pack("<iq", rx, len(epochs[rx])))
        for e in epochs[rx]:
            h.update(struct.pack("<diiiiq", e.gps_tow_seconds, e.gps_week, e.leap_seconds,
                                 e.receiver_status, e.version, len(e.measurements)))
            for m in e.measurements:
                s = m.identity
                h.update(struct.pack("<iiiiddiiii", s.gnss_id, s.sv_id, s.sig_id, s.freq_id,
                                     m.pr_mes_m, m.do_mes_hz, m.cno_dbhz, m.pr_std_code,
                                     m.do_std_code, int(m.pseudorange_valid)))
    return h.hexdigest()


def _signal(value):
    if isinstance(value, SignalIdentity):
        return value
    if isinstance(value, str):
        return SignalIdentity(*map(int, value.split(":")))
    return SignalIdentity(**value)


def apply_rawx_fault_overlay(epochs: Mapping[int, Sequence[RawxEpoch]], *, base_time: float,
        window_s: tuple[float, float], supported_groups: Sequence[tuple[int, int, int]],
        pivot_history: Mapping[float, Sequence[SignalIdentity]] | None = None,
        policy: OverlayPolicy = OverlayPolicy()) -> OverlayResult:
    """Choose signals from the five pre-event RAWX epochs, never accepted outputs.

    Event times are first paired epoch >= window quartile. Partial outage prefers
    a supported clean-prepared pivot at the immediately previous epoch; stable
    full signal ordering breaks ties. The phase pulse prefers non-pivots. These
    are input-only preferences, not assertions about a current owner or pivot.
    Missing qualification is recorded with no replacement event.
    """
    lo, hi = map(float, window_s)
    if not all(map(math.isfinite, (base_time, lo, hi))) or hi <= lo or set(epochs) != {1, 2}:
        raise ValueError("finite window and receivers 1/2 required")
    original = {rx: tuple(epochs[rx]) for rx in (1, 2)}
    indexed = {}
    for rx in (1, 2):
        keys = [(e.gps_week, e.gps_tow_seconds) for e in original[rx]]
        if any(not math.isfinite(k[1]) for k in keys) or any(b <= a for a, b in zip(keys, keys[1:])):
            raise ValueError("RAWX epochs must be finite, unique, and strictly increasing")
        indexed[rx] = dict(zip(keys, original[rx]))
    paired = sorted(set(indexed[1]) & set(indexed[2]))
    times = [local_time(indexed[1][k], base_time) for k in paired]
    if not times or any(local_time(indexed[2][k], base_time) != t for k, t in zip(paired, times)):
        raise ValueError("nonempty exactly tagged receiver pairing required")
    if any(t < lo or t > hi for t in times):
        raise ValueError("overlay epochs outside the declared full window")
    group_set = {tuple(x) for x in supported_groups}
    pivots = {} if pivot_history is None else pivot_history
    events = []
    definitions = ((0.25, "SINGLE_SIGNAL_CARRIER_QUALIFICATION_OUTAGE"),
                   (0.50, "RX2_ALL_CARRIER_QUALIFICATION_OUTAGE"),
                   (0.75, "UNANNOUNCED_SINGLE_SIGNAL_PHASE_PULSE"))
    for ordinal, (fraction, kind) in enumerate(definitions, 1):
        target = lo + fraction * (hi - lo)
        index = bisect_left(times, target)
        event = dict(event_id=f"F{ordinal}", kind=kind, receiver=2,
                     fraction=fraction, nominal_start_s=target, duration_s=policy.duration_s,
                     signal=None, status="NOT_IMPLEMENTABLE", reason="NO_EPOCH_AT_OR_AFTER_QUARTILE")
        if index >= len(times):
            events.append(event); continue
        start = times[index]; end = start + policy.duration_s
        event.update(start_s=start, end_s=end, observation_end_s=end+policy.observation_tail_s,
                     paired_start_index=index, interval="[start,end)")
        if times[-1] < end + policy.observation_tail_s:
            event["reason"] = "INSUFFICIENT_REGISTERED_POSTFAULT_SUPPORT"
            events.append(event); continue
        if ordinal == 2:
            event.update(status="PLANNED", reason=None, selection="all receiver-2 measurements, all signals")
            events.append(event); continue
        history = paired[max(0, index-policy.history_epochs):index]
        ht = times[max(0, index-policy.history_epochs):index]
        if len(history) != policy.history_epochs or any(abs(b-a-policy.epoch_interval_s) > policy.time_tolerance_s
                                                       for a, b in zip(ht, ht[1:]+[start])):
            event["reason"] = "PRE_EVENT_FIVE_EPOCH_HISTORY_MISSING_OR_GAPPED"
            events.append(event); continue
        stable = None
        histories = {}
        for rx in (1, 2):
            per_epoch = []
            for key in history:
                epoch = indexed[rx][key]
                obs = {}
                for m in epoch.measurements:
                    try:
                        o = from_rawx(str(rx), epoch, m)
                        if o.phase_eligible and not o.receiver_clock_reset and (m.identity.gnss_id, m.identity.sig_id,
                                                                               m.identity.freq_id) in group_set:
                            obs[m.identity] = o
                    except ValueError:
                        continue
                per_epoch.append(obs)
            common = set.intersection(*(set(x) for x in per_epoch))
            for s in tuple(common):
                chain = [x[s] for x in per_epoch]
                try:
                    discontinuous = any(b.locktime_ms < a.locktime_ms or b.half_cycle_subtracted != a.half_cycle_subtracted
                        or tdcp_doppler_check(a, b, residual_limit_cycles=policy.tdcp_limit_cycles).status != "CONSISTENT"
                        for a, b in zip(chain, chain[1:]))
                except ValueError:
                    discontinuous = True
                if discontinuous:
                    common.remove(s)
            stable = common if stable is None else stable & common
            histories[rx] = per_epoch
        preferred_pivots = {_signal(x) for x in pivots.get(ht[-1], ())}
        candidates = sorted(stable, key=lambda s: ((s not in preferred_pivots) if ordinal == 1
                                                  else (s in preferred_pivots), s))
        event.update(history_time_s=ht, candidate_signals=[identity_text(s) for s in candidates],
                     previous_clean_pivots=sorted(identity_text(s) for s in preferred_pivots),
                     selection="past-five phase qualification/TDCP; pivot preference then full-signal stable order")
        if candidates:
            event.update(signal=identity_text(candidates[0]), status="PLANNED", reason=None)
        else:
            event["reason"] = "NO_SUPPORTED_CONTINUOUS_SIGNAL_IN_PRE_EVENT_HISTORY"
        events.append(event)
    changed = []
    result = {1: original[1], 2: []}
    for epoch in original[2]:
        t = local_time(epoch, base_time); measurements = []
        for m in epoch.measurements:
            new = m
            for event in events:
                if event["status"] != "PLANNED" or not event["start_s"] <= t < event["end_s"]:
                    continue
                if event["signal"] is not None and identity_text(m.identity) != event["signal"]:
                    continue
                before = new
                if event["event_id"] in ("F1", "F2"):
                    new = replace(new, tracking_status=new.tracking_status & ~0x02, locktime_ms=0)
                else:
                    # Do not turn an invalid/sentinel phase into a usable observation.
                    try:
                        eligible = from_rawx("2", epoch, m).phase_eligible
                    except ValueError:
                        eligible = False
                    if not eligible:
                        continue
                    new = replace(new, cp_mes_cycles=new.cp_mes_cycles+policy.bias_cycles)
                changed.append(dict(event_id=event["event_id"], receiver=2, time_s=t,
                    signal=identity_text(m.identity), phase_before_cycles=(before.cp_mes_cycles
                    if math.isfinite(before.cp_mes_cycles) else None), phase_after_cycles=(new.cp_mes_cycles
                    if math.isfinite(new.cp_mes_cycles) else None), locktime_before_ms=before.locktime_ms,
                    locktime_after_ms=new.locktime_ms, tracking_status_before=before.tracking_status,
                    tracking_status_after=new.tracking_status))
            measurements.append(new)
        result[2].append(replace(epoch, measurements=tuple(measurements)))
    result[2] = tuple(result[2])
    before = code_doppler_fingerprint(original); after = code_doppler_fingerprint(result)
    if before != after:
        raise AssertionError("time/code/Doppler/clock identity changed")
    for event in events:
        mods = [x for x in changed if x["event_id"] == event["event_id"]]
        event["modified_measurements"] = len(mods)
        event["modified_epochs"] = len({x["time_s"] for x in mods})
        if event["status"] == "PLANNED":
            event["status"] = "APPLIED" if mods else "NO_QUALIFIED_MEASUREMENT_AT_FIXED_EVENT"
    return OverlayResult(result, dict(schema="rawx_observation_fault_overlay.v1",
        data_mode="RAWX_OBSERVATION_LEVEL_SEMISYNTHETIC", original_raw_modified=False,
        natural_fault_claim=False, receiver_firmware_simulation=False, real_integer_truth_available=False,
        code_doppler_clock_identity_unchanged=True, unchanged_code_doppler_sha256=before,
        receiver_1_unchanged=True, events=events, modifications=changed,
        restoration="original decoded fields resume; tracker must issue fresh arc tokens",
        accepted_result_or_reference_selection=False, parameter_sweep=False))
