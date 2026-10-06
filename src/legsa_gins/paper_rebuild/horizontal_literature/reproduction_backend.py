"""Versioned raw DD adapter for the EXT01--03 reproduction.

The frozen adapters remain unchanged.  This adapter uses each receiver's own
RAWX code to obtain its satellite transmit state.  No receiver navigation
solution, commercial reference, fixed ambiguity or clock message is consumed.
See EXT_REPRODUCTION/REPRODUCTION_NOTES.md for the linearization and remaining
short-baseline/asynchronous-sampling approximations.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence

import numpy as np

from . import shared_raw_backend as raw
from .ext03_yang2024 import DDObservationBlock

C = 299792458.0
ADAPTER_VERSION = "EXT_REPRO_DD_OWN_TRANSMIT_V1"


@dataclass(frozen=True)
class PairGeometry:
    satellite1_ecef_m: np.ndarray
    satellite2_ecef_m: np.ndarray
    los1: np.ndarray
    los2: np.ndarray
    geometric_sd_m: float
    satellite_clock_sd_m: float
    known_sd_m: float
    elevation_rad: float


def rotate_with_geometric_flight(satellite: Sequence[float], anchor: Sequence[float]) -> np.ndarray:
    """One Earth rotation only, with iterated geometric rather than code delay."""
    return raw.earth_rotation_correct_satellite_geometric(satellite, anchor)


def pair_geometry(epoch1, epoch2, measurement1, measurement2, provider, anchor) -> PairGeometry:
    """Compute the known SD at the same raw-code SPP anchor, not a baseline answer.

    RAWX T is receiver local time: RTKLIB satposs(T, P) already cancels receiver
    clock in T-P/c.  Do not subtract a receiver clock again.  The satellite
    clock term in a code/carrier observation is -c*dt_sat.
    """
    if measurement1.identity != measurement2.identity:
        raise raw.RawBackendError("receiver pair must use the same exact SignalIdentity")
    point = np.asarray(anchor, float)
    if point.shape != (3,) or not np.isfinite(point).all():
        raise raw.RawBackendError("invalid code-SPP anchor")
    states = []
    for epoch, measurement in ((epoch1, measurement1), (epoch2, measurement2)):
        if not measurement.pseudorange_valid or not 1e6 < measurement.pr_mes_m < 1e8:
            raise raw.RawBackendError("transmit state requires the receiver's own valid code")
        state = provider.state(measurement.identity, epoch.gps_week,
                               epoch.gps_tow_seconds, measurement.pr_mes_m)
        if state.health != 0:
            raise raw.RawBackendError("unhealthy broadcast satellite")
        states.append(state)
    satellites = [rotate_with_geometric_flight(s.position_ecef_m, point) for s in states]
    ranges = [float(np.linalg.norm(s - point)) for s in satellites]
    los = [(s - point) / distance for s, distance in zip(satellites, ranges)]
    geometric = ranges[1] - ranges[0]
    clock = -C * (states[1].clock_bias_s - states[0].clock_bias_s)
    elevation = min(raw.azimuth_elevation(point, s)[1] for s in satellites)
    return PairGeometry(*satellites, *los, geometric, clock, geometric + clock, elevation)


def _sd(first, second, geometry):
    code = second.pr_mes_m - first.pr_mes_m - geometry.known_sd_m
    phase = (raw.integer_compatible_carrier_cycles(second)
             - raw.integer_compatible_carrier_cycles(first)) * raw.wavelength_m(first.identity)
    return code, phase - geometry.known_sd_m


def _geometry_audit(geometries):
    return [{"signal": raw.identity_text(identity),
             "known_sd_m": g.known_sd_m, "satellite_motion_sd_m": g.geometric_sd_m,
             "satellite_clock_sd_m": g.satellite_clock_sd_m,
             "los_receiver_difference_norm": float(np.linalg.norm(g.los2-g.los1)),
             "elevation_rad": g.elevation_rad}
            for identity, g in geometries.items()]


def build_gps_l1_model(receiver1, receiver2, provider, anchor,
                       min_cno_dbhz=20, minimum_elevation_rad=math.radians(10)):
    """Reuse frozen validity, covariance and integer conventions with own timing."""
    if (receiver1.gps_week, receiver1.gps_tow_seconds) != (receiver2.gps_week, receiver2.gps_tow_seconds):
        raise raw.RawBackendError("expected exact receiver-local epoch pairing")
    accounting = raw.gps_l1_epoch_accounting(receiver1, receiver2)
    for attribute, token in (
        ("common_raw_identities", "COMMON_RAW"),
        ("common_pr_valid_identities", "PR_VALID"),
        ("common_cp_valid_identities", "CP_VALID"),
        ("common_pr_cp_valid_identities", "PR_CP_VALID"),
        ("common_half_cycle_valid_identities", "HALF_CYCLE_VALID"),
        ("common_integer_compatible_identities", "INTEGER_COMPATIBLE_PHASE"),
    ):
        raw._require_dd_stage(accounting, attribute, "INSUFFICIENT_"+token, token)
    groups = [raw._gps_l1_measurement_groups(e) for e in (receiver1, receiver2)]
    first, second = [{i: g[i][0] for i in accounting.common_integer_compatible_identities} for g in groups]
    geometries = {}
    for identity in accounting.common_integer_compatible_identities:
        try:
            geometries[identity] = pair_geometry(receiver1, receiver2, first[identity],
                                                 second[identity], provider, anchor)
        except raw.RawBackendError:
            continue
    elevations = {i: g.elevation_rad for i, g in geometries.items() if g.elevation_rad >= minimum_elevation_rad}
    eligible = tuple(i for i in sorted(elevations)
                     if raw.strict_raw_tracking_eligible(first[i], min_cno_dbhz)
                     and raw.strict_raw_tracking_eligible(second[i], min_cno_dbhz))
    accounting = replace(accounting, satellite_state_available_identities=tuple(sorted(geometries)),
                         elevation_eligible_identities=tuple(sorted(elevations)), dd_eligible_identities=eligible)
    for attribute, token in (("satellite_state_available_identities", "SATELLITE_STATES"),
                             ("elevation_eligible_identities", "ELEVATION_ELIGIBLE"),
                             ("dd_eligible_identities", "DD_DIMENSION")):
        raw._require_dd_stage(accounting, attribute, "INSUFFICIENT_"+token, token)
    pivot, _ = raw.select_reference([first[i] for i in eligible], elevations)
    satellites = tuple(i for i in eligible if i != pivot)
    sd = {i: _sd(first[i], second[i], geometries[i]) for i in eligible}
    code = np.array([sd[i][0]-sd[pivot][0] for i in satellites])
    phase = np.array([sd[i][1]-sd[pivot][1] for i in satellites])
    h = np.array([-(geometries[i].los2-geometries[pivot].los2) for i in satellites])
    n = len(satellites)
    a = np.zeros((2*n, n)); a[n:] = np.diag([raw.wavelength_m(i) for i in satellites])
    def variances(i):
        p1, l1, _ = raw.rawx_standard_deviations(first[i])
        p2, l2, _ = raw.rawx_standard_deviations(second[i])
        return p1*p1+p2*p2, (l1*l1+l2*l2)*raw.wavelength_m(i)**2
    variance = {i: variances(i) for i in eligible}
    covariances = [raw.correlated_dd_covariance([variance[i][k] for i in satellites], variance[pivot][k]) for k in (0, 1)]
    q = np.block([[covariances[0], np.zeros((n, n))], [np.zeros((n, n)), covariances[1]]])
    model = raw.DoubleDifferenceModel(pivot, satellites, np.r_[code, phase], a,
                                      np.vstack((h, h)), q, elevations, accounting)
    condition = raw.dd_matrix_condition_diagnostics(model)
    if condition.whitened_design_rank < condition.unknown_count:
        raise raw.DoubleDifferenceStageError("NORMAL_MATRIX_RANK_DEFICIENT", "DD rank deficient", accounting)
    return model, _geometry_audit({i: geometries[i] for i in eligible})


def common_signal_epochs(receiver1, receiver2):
    """Choose one common signal component per satellite/frequency deterministically.

    Independent strongest-signal selection can pair different components as if
    they shared an ambiguity.  Selection uses only raw validity and minimum
    receiver C/N0, then the exact identity as tie breaker.  Tracking must use
    these same epochs and reset an ambiguity on a subsequent component change.
    """
    from .phase3_signal_inventory import SIGNAL_GROUPS, integer_compatible
    if (receiver1.gps_week, receiver1.gps_tow_seconds) != (receiver2.gps_week, receiver2.gps_tow_seconds):
        raise raw.RawBackendError("expected exact receiver-local epoch pairing")
    maps = []
    for epoch in (receiver1, receiver2):
        mapping = {}
        for measurement in epoch.measurements:
            if integer_compatible(measurement):
                if measurement.identity in mapping:
                    raise raw.RawBackendError("duplicate exact SignalIdentity in RAWX epoch")
                mapping[measurement.identity] = measurement
        maps.append(mapping)
    common = set(maps[0]) & set(maps[1])
    selected, audit = [], []
    for frequency, allowed in SIGNAL_GROUPS.items():
        candidates = [i for i in common if (i.gnss_id, i.sig_id, i.freq_id) in allowed]
        for sv in sorted({i.sv_id for i in candidates}):
            identity = min((i for i in candidates if i.sv_id == sv),
                           key=lambda i: (-min(m[i].cno_dbhz for m in maps), i))
            selected.append(identity)
            audit.append({"constellation": "GPS" if identity.gnss_id == 0 else "BDS",
                          "frequency": frequency, "sv": sv,
                          "raw_identity": {"gnss_id": identity.gnss_id, "sv_id": sv,
                                           "sig_id": identity.sig_id, "freq_id": identity.freq_id}})
    return (replace(receiver1, measurements=tuple(maps[0][i] for i in sorted(selected))),
            replace(receiver2, measurements=tuple(maps[1][i] for i in sorted(selected))), audit)


def build_dual_frequency_blocks(receiver1, receiver2, provider, spp1, spp2):
    """GPS L1/L2 + BDS B1/B2, within-system pivots, frozen Yang noise/defaults.

    Each frequency uses its own code for transmit time.  The same constellation
    pivot is retained across both frequencies.  No GPS-only fallback is relabeled.
    """
    from .phase3_runner import _best_by_sv, _ecef_vector_to_ned, _saastamoinen_m, Phase3ObservationError
    receiver1, receiver2, _ = common_signal_epochs(receiver1, receiver2)
    blocks, audit = [], []
    for system, frequencies in (("GPS", ("GPS_L1", "GPS_L2")), ("BDS", ("BDS_B1", "BDS_B2"))):
        maps = {(r, f): _best_by_sv(e, f) for r, e in ((1, receiver1), (2, receiver2)) for f in frequencies}
        common = set.intersection(*(set(maps[r, f]) for r in (1, 2) for f in frequencies))
        geometries = {}
        for sv in sorted(common):
            try:
                values = {f: pair_geometry(receiver1, receiver2, maps[1, f][sv], maps[2, f][sv], provider, spp1)
                          for f in frequencies}
                if min(g.elevation_rad for g in values.values()) >= math.radians(15):
                    geometries[sv] = values
            except raw.RawBackendError:
                continue
        if len(geometries) < 2:
            raise Phase3ObservationError("INSUFFICIENT_"+system+"_DUAL_FREQUENCY_SATELLITE_STATES", str(len(geometries)))
        elevation = {sv: min(g.elevation_rad for g in values.values()) for sv, values in geometries.items()}
        pivot = min(geometries, key=lambda sv: (-elevation[sv], -min(maps[r, f][sv].locktime_ms for r in (1, 2) for f in frequencies), sv))
        satellites = tuple(sv for sv in sorted(geometries) if sv != pivot)
        for frequency in frequencies:
            first, second = maps[1, frequency], maps[2, frequency]
            sd = {}
            for sv, values in geometries.items():
                g = values[frequency]
                code, phase = _sd(first[sv], second[sv], g)
                # Frozen short-baseline Saastamoinen engineering approximation;
                # no ionospheric term with an incorrect shared sign is inserted.
                dtrop = _saastamoinen_m(spp2, g.satellite2_ecef_m)-_saastamoinen_m(spp1, g.satellite1_ecef_m)
                sd[sv] = (code-dtrop, phase-dtrop)
            n = len(satellites)
            phase_variance = {sv: 2*(0.003**2+0.003**2/math.sin(elevation[sv])**2) for sv in geometries}
            qp = raw.correlated_dd_covariance([phase_variance[sv] for sv in satellites], phase_variance[pivot])
            q = np.block([[qp*100**2, np.zeros((n,n))], [np.zeros((n,n)), qp]])
            label = lambda sv: raw.rinex_satellite_id(first[sv].identity)
            los = {label(sv): _ecef_vector_to_ned(values[frequency].los2, spp1) for sv, values in geometries.items()}
            blocks.append(DDObservationBlock(system, frequency, label(pivot), tuple(label(sv) for sv in satellites),
                raw.wavelength_m(first[pivot].identity), los,
                np.array([sd[sv][0]-sd[pivot][0] for sv in satellites]),
                np.array([sd[sv][1]-sd[pivot][1] for sv in satellites]), q))
            audit.extend(_geometry_audit({first[sv].identity: values[frequency] for sv, values in geometries.items()}))
    return tuple(blocks), audit
