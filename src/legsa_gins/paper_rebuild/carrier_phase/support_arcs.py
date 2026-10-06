"""Causal SDK-force support episodes, not physical contact or no-slip truth.

Policies are caller-supplied frozen working thresholds. This module neither
calibrates force nor fits thresholds. No interpolation, future read, backdating,
or automatic missing-field zero fill occurs. Continuity means the *observed SDK
proxy history* stayed eligible; unobserved between-sample changes remain unknown.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping
import uuid
import weakref


class SupportArcError(ValueError):
    pass


def _finite_scalar(value, name):
    if isinstance(value, bool):
        raise SupportArcError(name + " must be a finite numeric scalar, not bool")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SupportArcError(name + " must be a finite numeric scalar") from exc
    if not math.isfinite(result):
        raise SupportArcError(name + " must be finite")
    return result


@dataclass(frozen=True)
class FootForceThreshold:
    foot_id: str
    on: float
    off: float

    def __post_init__(self):
        if not isinstance(self.foot_id, str) or not self.foot_id:
            raise SupportArcError("explicit nonempty foot identity required")
        on, off = _finite_scalar(self.on, "on"), _finite_scalar(self.off, "off")
        if not off < on:
            raise SupportArcError("force policy requires off < on")
        object.__setattr__(self, "on", on)
        object.__setattr__(self, "off", off)


@dataclass(frozen=True)
class SupportPolicy:
    foot_thresholds: tuple[FootForceThreshold, ...]
    dwell_s: float
    max_source_gap_s: float

    def __post_init__(self):
        thresholds = tuple(self.foot_thresholds)
        if not thresholds or any(not isinstance(v, FootForceThreshold) for v in thresholds):
            raise SupportArcError("explicit per-foot thresholds required")
        if len({v.foot_id for v in thresholds}) != len(thresholds):
            raise SupportArcError("duplicate foot identity")
        dwell = _finite_scalar(self.dwell_s, "dwell")
        gap = _finite_scalar(self.max_source_gap_s, "max source gap")
        if dwell <= 0 or gap <= 0:
            raise SupportArcError("positive dwell and max source gap required")
        object.__setattr__(self, "foot_thresholds", thresholds)
        object.__setattr__(self, "dwell_s", dwell)
        object.__setattr__(self, "max_source_gap_s", gap)

    @property
    def foot_ids(self):
        return tuple(v.foot_id for v in self.foot_thresholds)


@dataclass(frozen=True)
class FootSupportState:
    foot_id: str
    state: str
    token: str | None
    eligible: bool
    force_sdk_units: float | None
    pending_state: str | None
    pending_since_source_time_s: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SupportEpoch:
    time_s: float
    available_time_s: float
    stream_id: str
    tracker_instance_id: str
    sequence: int
    feet: tuple[FootSupportState, ...]
    source_role: str = "SDK_FORCE_SUPPORT_PROXY_NOT_CONTACT_TRUTH"
    calibrated_force: bool = False
    physical_no_slip_certified: bool = False
    intersample_contact_changes_excluded: bool = False

    def by_foot(self):
        return {v.foot_id: v for v in self.feet}


@dataclass
class _Memory:
    state: str = "UNKNOWN"
    token: str | None = None
    pending: str | None = None
    pending_since: float | None = None
    episode: int = 0


class SupportArcTracker:
    """A separate tracker per explicitly identified source stream.

    Availability is caller-declared receipt/replay availability, not a calibrated
    physical sample time. Both source and availability clocks must be monotonic;
    source time is strictly increasing. Rejected malformed updates invalidate
    every current episode, so repairing input cannot silently continue an old arc.

    Tokens contain an opaque per-instance UUID only to prevent reuse after a
    restart; that nonce is not sensor data and has no statistical role.
    """

    def __init__(self, policy: SupportPolicy, *, stream_id: str):
        if not isinstance(policy, SupportPolicy):
            raise SupportArcError("SupportPolicy required")
        if not isinstance(stream_id, str) or not stream_id:
            raise SupportArcError("explicit nonempty source stream ID required")
        self.policy = policy
        self.stream_id = stream_id
        self.instance_id = uuid.uuid4().hex
        self._mem = {v.foot_id: _Memory() for v in policy.foot_thresholds}
        self._last_time = None
        self._last_available = None
        self._sequence = 0
        # Authenticate caller-retained snapshots without retaining the full log.
        self._issued = weakref.WeakValueDictionary()
        self._pending_rejection_reason = None
        self.rejected_update_count = 0

    @staticmethod
    def _invalidate(memory):
        retired = memory.token is not None
        memory.state = "UNKNOWN"
        memory.token = None
        memory.pending = None
        memory.pending_since = None
        return retired

    def _reject(self, reason):
        for memory in self._mem.values():
            self._invalidate(memory)
        self._pending_rejection_reason = reason
        self.rejected_update_count += 1
        raise SupportArcError(reason)

    def update(self, time_s, forces: Mapping[str, object], *, available_time_s,
               source_ok: bool = True,
               foot_source_ok: Mapping[str, bool] | None = None) -> SupportEpoch:
        """Missing/invalid force retires only that foot; source errors retire all.

        A STANCE sample at force <= off immediately loses its token. Even if
        the next sample returns to the hysteresis band, the token never returns:
        high force must again persist for the declared dwell, creating a new arc.
        """
        try:
            t = _finite_scalar(time_s, "source time")
            available = _finite_scalar(available_time_s, "availability")
        except SupportArcError:
            return self._reject("INVALID_SOURCE_OR_AVAILABILITY_TIME")
        if self._last_time is not None and t <= self._last_time:
            return self._reject("NONMONOTONIC_SOURCE_TIME")
        if available < t or (self._last_available is not None and available < self._last_available):
            return self._reject("NONCAUSAL_OR_NONMONOTONIC_AVAILABILITY")
        if not isinstance(forces, Mapping) or set(forces) - set(self.policy.foot_ids):
            return self._reject("UNKNOWN_FOOT_OR_INVALID_FORCE_MAPPING")
        if type(source_ok) is not bool:
            return self._reject("SOURCE_VALIDITY_MUST_BE_EXPLICIT_BOOL")
        if foot_source_ok is not None:
            if (not isinstance(foot_source_ok, Mapping)
                    or set(foot_source_ok) != set(self.policy.foot_ids)
                    or any(type(v) is not bool for v in foot_source_ok.values())):
                return self._reject("PER_FOOT_SOURCE_VALIDITY_MAPPING_MISMATCH")
        gap = self._last_time is not None and t - self._last_time > self.policy.max_source_gap_s
        records = []
        for threshold in self.policy.foot_thresholds:
            name = threshold.foot_id
            memory = self._mem[name]
            reasons = []
            if self._pending_rejection_reason:
                reasons.append("PRIOR_REJECTED_UPDATE:" + self._pending_rejection_reason)
            if gap:
                if self._invalidate(memory):
                    reasons.append("CONTACT_EPISODE_RETIRED")
                reasons.append("SOURCE_GAP")
            invalid_reason = None
            force = None
            if not source_ok:
                invalid_reason = "SOURCE_ERROR"
            elif foot_source_ok is not None and not foot_source_ok[name]:
                invalid_reason = "FOOT_SOURCE_ERROR"
            elif name not in forces:
                invalid_reason = "MISSING_FORCE_FIELD"
            else:
                try:
                    force = _finite_scalar(forces[name], "force")
                except SupportArcError:
                    invalid_reason = "INVALID_FORCE_FIELD"
            if invalid_reason:
                if self._invalidate(memory):
                    reasons.append("CONTACT_EPISODE_RETIRED")
                reasons.append(invalid_reason)
            elif memory.state == "STANCE" and force > threshold.off:
                memory.pending = None
                memory.pending_since = None
                reasons.append("STANCE_PROXY_CONTINUES")
            else:
                if memory.state == "STANCE":
                    self._invalidate(memory)
                    reasons.extend(("FIRST_LOW_FORCE_RETIRES_EPISODE", "CONTACT_EPISODE_RETIRED"))
                target = ("STANCE" if force >= threshold.on else
                          "SWING" if force <= threshold.off else None)
                if target is None:
                    memory.pending = None
                    memory.pending_since = None
                    reasons.append("HYSTERESIS_BAND_NO_NEW_EPISODE")
                elif memory.state == target:
                    memory.pending = None
                    memory.pending_since = None
                    reasons.append("SWING_PROXY_CONTINUES")
                else:
                    if memory.pending != target:
                        memory.pending = target
                        memory.pending_since = t
                    if t - memory.pending_since >= self.policy.dwell_s:
                        memory.state = target
                        memory.pending = None
                        memory.pending_since = None
                        if target == "STANCE":
                            memory.episode += 1
                            memory.token = (self.stream_id + "|" + self.instance_id + "|" +
                                            name + "|" + str(memory.episode))
                            reasons.append("NEW_STANCE_EPISODE_AVAILABLE_NOW")
                        else:
                            memory.token = None
                            reasons.append("SWING_DWELL_CONFIRMED_NOW")
                    else:
                        reasons.append(target + "_DWELL_PENDING")
            records.append(FootSupportState(
                name, memory.state, memory.token,
                memory.state == "STANCE" and memory.token is not None,
                force, memory.pending, memory.pending_since, tuple(reasons)))
        self._last_time, self._last_available = t, available
        self._pending_rejection_reason = None
        self._sequence += 1
        out = SupportEpoch(t, available, self.stream_id, self.instance_id,
                           self._sequence, tuple(records))
        self._issued[out.sequence] = out
        return out

    def interval_continuity(self, previous: SupportEpoch, current: SupportEpoch):
        """Observed-proxy continuity per foot, never a claim about physical slip.

        Accepts only ordered snapshots issued by this live tracker. Matching
        nonempty tokens imply no intervening observed low/error/gap/restart,
        because every such event permanently retires the token. Equal endpoint
        states by themselves cannot satisfy this condition.
        """
        for snapshot in (previous, current):
            if (not isinstance(snapshot, SupportEpoch)
                    or snapshot.tracker_instance_id != self.instance_id
                    or self._issued.get(snapshot.sequence) is not snapshot):
                raise SupportArcError("snapshots must be issued by this tracker")
        if current.sequence <= previous.sequence or current.time_s <= previous.time_s:
            raise SupportArcError("strictly ordered interval snapshots required")
        left, right = previous.by_foot(), current.by_foot()
        return {name: bool(left[name].eligible and right[name].eligible
                           and left[name].token is not None
                           and left[name].token == right[name].token)
                for name in self.policy.foot_ids}
