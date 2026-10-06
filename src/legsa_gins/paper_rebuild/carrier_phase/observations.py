"""Typed carrier observations, faithful RAWX units and receiver-2 minus receiver-1 SD.

Protocol: u-blox UBX-22008968 R01, section 3.17.6, pp. 189-190:
https://content.u-blox.com/sites/default/files/documents/
u-blox-F9-HPG-1.32_InterfaceDescription_UBX-22008968.pdf

cpMes is kept unchanged, including when subHalfCyc is set.  That bit reports
receiver-side processing; it is not an instruction to add/subtract half a
cycle again.  Unresolved half-cycle validity does not qualify for integer AR.
RAWX Doppler is positive on approach: phase-range rate = -wavelength * Doppler.
A single satellite constrains one range combination, never a 3D baseline.

This namespace consumes already decoded observations. It performs no file I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral

from ..horizontal_literature.shared_raw_backend import (
    RawxEpoch, RawxMeasurement, SignalIdentity, signal_frequency_hz, wavelength_m,
)

SPEED_OF_LIGHT_MPS = 299_792_458.0
GPS_WEEK_SECONDS = 604_800.0


class ObservationError(ValueError):
    """An observation contract fails; no corrected value is fabricated."""


@dataclass(frozen=True, order=True)
class EpochKey:
    """Exact receiver GPS-labelled key; matching is not physical clock calibration."""

    gps_week: int
    tow_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.gps_week, Integral) or isinstance(self.gps_week, bool) or self.gps_week < 0:
            raise ObservationError("gps_week must be a nonnegative integer")
        if isinstance(self.tow_seconds, bool) or not math.isfinite(self.tow_seconds) or not 0 <= self.tow_seconds < GPS_WEEK_SECONDS:
            raise ObservationError("tow_seconds must be finite and inside a GPS week")

    def seconds_since(self, previous: EpochKey) -> float:
        # Do not subtract two large absolute timestamps and lose local precision.
        return (self.gps_week - previous.gps_week) * GPS_WEEK_SECONDS + self.tow_seconds - previous.tow_seconds


def validate_signal(signal: SignalIdentity) -> None:
    for value in (signal.gnss_id, signal.sv_id, signal.sig_id, signal.freq_id):
        if not isinstance(value, Integral) or isinstance(value, bool) or value < 0:
            raise ObservationError("signal identity requires nonnegative integer fields")
    if not 1 <= signal.sv_id <= 255:
        raise ObservationError("sv_id outside supported wire range")
    # Existing explicit registry rejects unknown signals, nonzero CDMA freqId and
    # unsupported GLONASS channels instead of silently using GPS L1 wavelength.
    signal_frequency_hz(signal)


@dataclass(frozen=True)
class CarrierObservation:
    receiver_id: str
    epoch: EpochKey
    signal: SignalIdentity
    phase_cycles: float | None
    doppler_hz: float | None
    pseudorange_m: float | None
    locktime_ms: int
    carrier_valid: bool
    half_cycle_valid: bool
    half_cycle_subtracted: bool
    pseudorange_valid: bool = True
    cp_std_code: int = 0
    do_std_code: int = 0
    cno_dbhz: float = 0.0
    receiver_clock_reset: bool = False

    def __post_init__(self) -> None:
        if not self.receiver_id:
            raise ObservationError("receiver_id is required")
        validate_signal(self.signal)
        if not isinstance(self.locktime_ms, Integral) or isinstance(self.locktime_ms, bool) or not 0 <= self.locktime_ms <= 64500:
            raise ObservationError("locktime_ms must be in the RAWX 0..64500 range")
        if any(not isinstance(x, Integral) or isinstance(x, bool) or not 0 <= x <= 15
               for x in (self.cp_std_code, self.do_std_code)):
            raise ObservationError("RAWX standard-deviation codes must be integers 0..15")

    @property
    def wavelength_m(self) -> float:
        return wavelength_m(self.signal)

    @property
    def phase_std_cycles(self) -> float | None:
        return None if self.cp_std_code == 15 else 0.004 * self.cp_std_code

    @property
    def doppler_std_hz(self) -> float:
        return 0.002 * 2 ** self.do_std_code

    @property
    def phase_eligibility_reasons(self) -> tuple[str, ...]:
        reasons = []
        if not self.carrier_valid:
            reasons.append("CARRIER_INVALID")
        if not self.half_cycle_valid:
            reasons.append("HALF_CYCLE_UNRESOLVED")
        if self.cp_std_code == 15:
            reasons.append("PHASE_STD_INVALID")
        if self.phase_cycles is None or not math.isfinite(self.phase_cycles) or self.phase_cycles == -0.5:
            reasons.append("PHASE_VALUE_INVALID")
        if self.locktime_ms == 0:
            reasons.append("NO_CARRIER_LOCK")
        return tuple(reasons)

    @property
    def phase_eligible(self) -> bool:
        """Candidate-observation eligibility only, not accepted integers."""
        return not self.phase_eligibility_reasons

    def phase_m(self) -> float:
        if not self.phase_eligible:
            raise ObservationError(",".join(self.phase_eligibility_reasons))
        return float(self.phase_cycles) * self.wavelength_m

    def range_rate_mps(self) -> float:
        if self.doppler_hz is None or not math.isfinite(self.doppler_hz):
            raise ObservationError("DOPPLER_UNAVAILABLE")
        return -self.wavelength_m * self.doppler_hz


def from_rawx(receiver_id: str, epoch: RawxEpoch, measurement: RawxMeasurement) -> CarrierObservation:
    """Adapt one decoded RAWX v1 item; never touch raw or reference files."""
    if epoch.version != 1:
        raise ObservationError("unsupported RAWX message version for this adapter")
    if sum(m.identity == measurement.identity for m in epoch.measurements) != 1:
        raise ObservationError("duplicate or absent signal identity in epoch")
    if measurement not in epoch.measurements:
        raise ObservationError("measurement does not belong to the supplied epoch")
    return CarrierObservation(
        receiver_id=receiver_id, epoch=EpochKey(epoch.gps_week, epoch.gps_tow_seconds),
        signal=measurement.identity, phase_cycles=measurement.cp_mes_cycles,
        doppler_hz=measurement.do_mes_hz, pseudorange_m=measurement.pr_mes_m,
        locktime_ms=measurement.locktime_ms, carrier_valid=measurement.carrier_valid,
        half_cycle_valid=measurement.half_cycle_valid,
        half_cycle_subtracted=measurement.half_cycle_subtracted,
        pseudorange_valid=measurement.pseudorange_valid,
        cp_std_code=measurement.cp_std_code, do_std_code=measurement.do_std_code,
        cno_dbhz=measurement.cno_dbhz,
        receiver_clock_reset=bool(epoch.receiver_status & 0x02),
    )


def phase_model_cycles(
    signal: SignalIdentity, geometric_range_m: float, integer_ambiguity: int, *,
    receiver_clock_range_m: float = 0.0, satellite_clock_range_m: float = 0.0,
    troposphere_m: float = 0.0, ionosphere_m: float = 0.0,
    noninteger_phase_bias_cycles: float = 0.0,
) -> float:
    """L = (rho + receiver clock - satellite clock + T - I)/lambda + N + bias.

    This scalar measurement equation is also useful for synthetic truth tests.
    An integer cycle slip changes N; a noninteger phase bias does not.
    """
    validate_signal(signal)
    if not isinstance(integer_ambiguity, Integral) or isinstance(integer_ambiguity, bool):
        raise ObservationError("integer ambiguity must have an integer type")
    values = (geometric_range_m, receiver_clock_range_m, satellite_clock_range_m,
              troposphere_m, ionosphere_m, noninteger_phase_bias_cycles)
    if not all(math.isfinite(value) for value in values):
        raise ObservationError("nonfinite phase-model input")
    return ((geometric_range_m + receiver_clock_range_m - satellite_clock_range_m
             + troposphere_m - ionosphere_m) / wavelength_m(signal)
            + integer_ambiguity + noninteger_phase_bias_cycles)


@dataclass(frozen=True)
class SingleDifference:
    """Exactly paired receiver-2 minus receiver-1 scalar observation."""

    receiver1: CarrierObservation
    receiver2: CarrierObservation
    phase_cycles: float
    phase_m: float
    pseudorange_m: float | None
    doppler_hz: float | None
    range_rate_mps: float | None

    @property
    def signal(self) -> SignalIdentity:
        return self.receiver1.signal

    @property
    def epoch(self) -> EpochKey:
        return self.receiver1.epoch


def single_difference(receiver1: CarrierObservation, receiver2: CarrierObservation) -> SingleDifference:
    """Same signal/epoch only; SD N = N2-N1, geometric term approximately -LOS·b.

    b is receiver2 position minus receiver1 position; LOS points receiver to
    satellite. Receiver clock difference remains. No baseline is solved here.
    """
    if receiver1.receiver_id == receiver2.receiver_id:
        raise ObservationError("single difference requires distinct receivers")
    if receiver1.signal != receiver2.signal:
        raise ObservationError("single difference requires identical full signal identity")
    if receiver1.epoch != receiver2.epoch:
        raise ObservationError("single difference requires exact receiver-time pairing")
    for obs in (receiver1, receiver2):
        if not obs.phase_eligible:
            raise ObservationError(",".join(obs.phase_eligibility_reasons))
    phase = float(receiver2.phase_cycles) - float(receiver1.phase_cycles)
    code = None
    if all(obs.pseudorange_valid and obs.pseudorange_m is not None and math.isfinite(obs.pseudorange_m)
           for obs in (receiver1, receiver2)):
        code = float(receiver2.pseudorange_m) - float(receiver1.pseudorange_m)
    doppler = None
    if all(obs.doppler_hz is not None and math.isfinite(obs.doppler_hz) for obs in (receiver1, receiver2)):
        doppler = float(receiver2.doppler_hz) - float(receiver1.doppler_hz)
    return SingleDifference(receiver1, receiver2, phase, phase * receiver1.wavelength_m,
                            code, doppler, None if doppler is None else -receiver1.wavelength_m * doppler)


@dataclass(frozen=True)
class IntegerCandidate:
    """A candidate has no accepted/fixed flag, even if its objective is certified."""

    labels: tuple[str, ...]
    integers: tuple[int, ...]
    objective: float
    source_arc_tokens: tuple[str, ...]
    objective_certified: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "labels", tuple(self.labels))
        object.__setattr__(self, "integers", tuple(self.integers))
        object.__setattr__(self, "source_arc_tokens", tuple(self.source_arc_tokens))
        if not all(isinstance(label, str) and label for label in self.labels):
            raise ObservationError("candidate labels must be nonempty strings")
        if len(self.labels) != len(self.integers) or len(set(self.labels)) != len(self.labels):
            raise ObservationError("candidate labels must be unique and match integer dimension")
        if not self.labels or not all(isinstance(n, Integral) and not isinstance(n, bool) for n in self.integers):
            raise ObservationError("candidate needs an explicit integer vector")
        if not math.isfinite(self.objective) or self.objective < 0:
            raise ObservationError("candidate objective must be finite and nonnegative")


@dataclass(frozen=True)
class AcceptedIntegerSolution:
    """Explicit external decision record, not an automatic candidate conversion.

    Construction records the caller's declared acceptance. It does not certify
    the statistical calibration of that rule; no acceptance policy exists here.
    """

    candidate: IntegerCandidate
    acceptance_rule_id: str
    evidence_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, IntegerCandidate):
            raise ObservationError("acceptance requires an explicit candidate")
        if not self.acceptance_rule_id.strip() or not self.evidence_id.strip():
            raise ObservationError("acceptance requires a named rule and evidence record")
