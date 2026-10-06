"""Grouped CDMA code/carrier DDs for a moving, short dual-antenna baseline.

Reuses the source-backed UBX parser, wavelengths and own-transmit-time geometry.
No receiver PVT baseline, clock solution or reference trajectory is consumed.
Groups are exact (gnssId, sigId, freqId), never a cross-system clock difference.
Signal sources: UBX-18053584 R02 Appendix B; RTKLIB 180043ee ublox.c:ubx_sig.
The statistical default is independent receiver/signal/code-phase noise BEFORE
differencing, not an assertion of physical independence. Supply full SD Q to
retain measured cross-frequency/code-phase correlation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
from typing import Mapping, Sequence

import numpy as np

from ..horizontal_literature import shared_raw_backend as raw
from ..horizontal_literature.reproduction_backend import pair_geometry

GroupKey = tuple[int, int, int]
SignalIdentity = raw.SignalIdentity


@dataclass(frozen=True)
class SignalSpec:
    name: str
    rinex_suffix: str
    frequency_hz: float

    @property
    def wavelength_m(self) -> float:
        return 299792458.0 / self.frequency_hz


# Components at the same frequency remain separate ambiguity/bias groups.
_COMPONENTS = {
    (0, 0): ("GPS_L1_CA", "1C"),
    (0, 3): ("GPS_L2_CL", "2L"),
    (0, 4): ("GPS_L2_CM", "2S"),
    (2, 0): ("GAL_E1_C", "1C"),
    (2, 1): ("GAL_E1_B", "1B"),
    (2, 5): ("GAL_E5B_I", "7I"),
    (2, 6): ("GAL_E5B_Q", "7Q"),
    (3, 0): ("BDS_B1I_D1", "2I"),
    (3, 1): ("BDS_B1I_D2", "2I"),
    (3, 2): ("BDS_B2I_D1", "7I"),
    (3, 3): ("BDS_B2I_D2", "7I"),
}
SUPPORTED_GROUPS = tuple((gnss, sig, 0) for gnss, sig in _COMPONENTS)


def signal_spec(identity: SignalIdentity) -> SignalSpec:
    if identity.gnss_id == 6:
        raise raw.RawBackendError("GLONASS_FDMA_INTEGER_MODEL_NOT_IMPLEMENTED")
    if (identity.gnss_id, identity.sig_id) not in _COMPONENTS or identity.freq_id != 0:
        raise raw.RawBackendError(f"UNSUPPORTED_SIGNAL: {identity}")
    if not 1 <= identity.sv_id <= {0: 32, 2: 36, 3: 63}[identity.gnss_id]:
        raise raw.RawBackendError(f"INVALID_SATELLITE: {identity}")
    name, suffix = _COMPONENTS[identity.gnss_id, identity.sig_id]
    return SignalSpec(name, suffix, raw.signal_frequency_hz(identity))


def group_key(identity: SignalIdentity) -> GroupKey:
    signal_spec(identity)
    return identity.gnss_id, identity.sig_id, identity.freq_id


@dataclass(frozen=True)
class SingleDifferenceCovariance:
    """Q in metres squared, ordered [all code SD, all phase SD].

    Both receiver variances and any receiver covariance must already be
    propagated to SD here. Identities may be a superset of admitted signals.
    """
    identities: tuple[SignalIdentity, ...]
    covariance_m2: np.ndarray


@dataclass(frozen=True)
class GroupDD:
    key: GroupKey
    pivot: SignalIdentity
    satellites: tuple[SignalIdentity, ...]
    y: np.ndarray
    A: np.ndarray
    B: np.ndarray
    Q: np.ndarray
    ambiguity_labels: tuple[str, ...]
    row_indices: tuple[int, ...]
    ambiguity_indices: tuple[int, ...]


@dataclass(frozen=True)
class MultiGnssEpoch:
    time_s: float
    y: np.ndarray
    A: np.ndarray
    B: np.ndarray
    Q: np.ndarray
    ambiguity_labels: tuple[str, ...]
    groups: tuple[GroupDD, ...]
    metadata: dict

    @property
    def ambiguity_design(self): return self.A

    @property
    def baseline_design(self): return self.B

    @property
    def covariance(self): return self.Q


def _positive_covariance(matrix: np.ndarray, size: int) -> np.ndarray:
    q = np.asarray(matrix, float)
    if q.shape != (size, size) or not np.isfinite(q).all():
        raise raw.RawBackendError("INVALID_SD_COVARIANCE_DIMENSION_OR_VALUES")
    if not np.allclose(q, q.T, rtol=1e-12, atol=1e-14):
        raise raw.RawBackendError("NONSYMMETRIC_SD_COVARIANCE")
    try:
        np.linalg.cholesky(q)
    except np.linalg.LinAlgError as exc:
        raise raw.RawBackendError("SD_COVARIANCE_NOT_POSITIVE_DEFINITE") from exc
    return q


def pivot_transform(satellites: Sequence[SignalIdentity],
                    old_pivot: SignalIdentity, new_pivot: SignalIdentity) -> np.ndarray:
    """Exact integer basis transform N_new = T N_old for one unchanged group.

    Input/output columns/rows are sorted satellites excluding the corresponding
    pivot. Callers must propagate covariance as T Q T.T and transform both code
    and phase rows; no arc continuity is inferred by this algebra.
    """
    ids = tuple(sorted(satellites))
    if len(ids) != len(set(ids)) or old_pivot not in ids or new_pivot not in ids:
        raise raw.RawBackendError("INVALID_PIVOT_SET")
    if len({group_key(i) for i in ids}) != 1:
        raise raw.RawBackendError("CROSS_GROUP_PIVOT_FORBIDDEN")
    old = tuple(i for i in ids if i != old_pivot)
    new = tuple(i for i in ids if i != new_pivot)
    vectors = {old_pivot: np.zeros(len(old), dtype=np.int64)}
    vectors.update({i: np.eye(len(old), dtype=np.int64)[k] for k, i in enumerate(old)})
    return np.asarray([vectors[i] - vectors[new_pivot] for i in new], dtype=np.int64)


def build_multignss_epoch(receiver1: raw.RawxEpoch, receiver2: raw.RawxEpoch,
                         provider: raw.SatelliteStateProvider,
                         anchor: Sequence[float], *,
                         groups: Sequence[GroupKey] | None = None,
                         pivots: Mapping[GroupKey, SignalIdentity] | None = None,
                         arc_ids: Mapping[SignalIdentity, str] | None = None,
                         min_cno_dbhz: int = 20,
                         minimum_elevation_rad: float = math.radians(10),
                         sd_covariance: SingleDifferenceCovariance | None = None
                         ) -> MultiGnssEpoch:
    """Build y = A N + B b + noise, b = rx2-rx1 in ECEF, all y in metres.

    Exact receiver-tag pairing is required, not asserted as physical timing
    calibration. Own-code transmit geometry is evaluated at ONE anchor.
    Atmospheric differential terms are a short-baseline approximation, not a
    difference between two independently estimated multi-metre SPP positions.
    Missing/unqualified groups remain explicit in metadata. Individual groups
    need two SVs; full baseline rank is a downstream joint-solver requirement.
    Without arc_ids, labels are epoch-local and MUST NOT imply temporal sharing.
    A supplied pivot never silently switches when missing.
    """
    epoch = (receiver1.gps_week, receiver1.gps_tow_seconds)
    if epoch != (receiver2.gps_week, receiver2.gps_tow_seconds):
        raise raw.RawBackendError("ASYNCHRONOUS_EPOCHS_REQUIRE_EXPLICIT_TIME_MODEL")
    if receiver1.version != 1 or receiver2.version != 1:
        raise raw.RawBackendError("RAWX_SIGNAL_ID_VERSION_NOT_QUALIFIED")
    if receiver1.receiver_status & 2 or receiver2.receiver_status & 2:
        raise raw.RawBackendError("RECEIVER_CLOCK_RESET_EPOCH")
    if epoch[0] < 0 or not math.isfinite(epoch[1]) or not 0 <= epoch[1] < 604800:
        raise raw.RawBackendError("INVALID_GPS_TIME")
    point = np.asarray(anchor, float)
    if point.shape != (3,) or not np.isfinite(point).all():
        raise raw.RawBackendError("INVALID_ANCHOR")
    if not 0 <= min_cno_dbhz <= 255 or not 0 <= minimum_elevation_rad < math.pi / 2:
        raise raw.RawBackendError("INVALID_QUALITY_CONFIGURATION")
    requested = tuple(sorted(tuple(key) for key in (SUPPORTED_GROUPS if groups is None else groups)))
    if not requested or len(set(requested)) != len(requested):
        raise raw.RawBackendError("EMPTY_OR_DUPLICATE_GROUP_REQUEST")
    for key in requested:
        if len(key) != 3:
            raise raw.RawBackendError("INVALID_GROUP_KEY")
        signal_spec(SignalIdentity(key[0], 1, key[1], key[2]))
    first, second = {}, {}
    for target, source in ((first, receiver1), (second, receiver2)):
        counts = Counter(m.identity for m in source.measurements)
        for m in source.measurements:
            if counts[m.identity] > 1:
                raise raw.RawBackendError(f"DUPLICATE_RAWX_IDENTITY: {m.identity}")
            target[m.identity] = m
    common = set(first) & set(second)
    qualified, rejected, selected = {}, [], []
    for key in requested:
        candidates = sorted(i for i in common if (i.gnss_id, i.sig_id, i.freq_id) == key)
        usable = {}
        for identity in candidates:
            try:
                signal_spec(identity)
                for m in (first[identity], second[identity]):
                    if (not m.pseudorange_valid or not math.isfinite(m.pr_mes_m)
                            or not 1e6 < m.pr_mes_m < 1e8 or m.locktime_ms <= 0
                            or m.cno_dbhz < min_cno_dbhz):
                        raise raw.RawBackendError("RAW_CODE_LOCK_OR_CNO_INELIGIBLE")
                    raw.integer_compatible_carrier_cycles(m)
                    raw.rawx_standard_deviations(m)
                if arc_ids is not None and (identity not in arc_ids or
                                             not isinstance(arc_ids[identity], str) or
                                             not arc_ids[identity]):
                    raise raw.RawBackendError("MISSING_CONTINUOUS_SD_ARC_ID")
                geometry = pair_geometry(receiver1, receiver2, first[identity],
                                         second[identity], provider, point)
                if (not math.isfinite(geometry.known_sd_m)
                        or not math.isfinite(geometry.elevation_rad)
                        or np.asarray(geometry.los2).shape != (3,)
                        or not np.isfinite(geometry.los2).all()):
                    raise raw.RawBackendError("NONFINITE_SATELLITE_GEOMETRY")
                if geometry.elevation_rad < minimum_elevation_rad:
                    raise raw.RawBackendError("BELOW_ELEVATION_MASK")
                usable[identity] = geometry
            except raw.RawBackendError as exc:
                rejected.append({"signal": raw.identity_text(identity), "reason": str(exc)})
        if len(usable) < 2:
            selected.append({"group": key, "status": "INSUFFICIENT_QUALIFIED_SATELLITES",
                             "common": len(candidates), "qualified": len(usable)})
            continue
        if pivots and key in pivots:
            pivot = pivots[key]
            if pivot not in usable:
                selected.append({"group": key, "status": "REQUESTED_PIVOT_UNAVAILABLE"})
                continue
        else:
            pivot = min(usable, key=lambda i: (-usable[i].elevation_rad,
                        -min(first[i].locktime_ms, second[i].locktime_ms), i))
        qualified.update(usable)
        selected.append({"group": key, "status": "BUILT", "pivot": raw.identity_text(pivot),
                         "identities": tuple(sorted(usable))})
    built = [g for g in selected if g["status"] == "BUILT"]
    if not built:
        error = raw.RawBackendError("NO_QUALIFIED_DD_GROUP")
        error.qualification = {"groups": selected, "rejected": rejected}
        raise error
    ids = tuple(sorted(qualified))
    index = {i: k for k, i in enumerate(ids)}
    # Remove geometry from rejected-pivot groups, if any, by construction.
    rows, targets, labels, slices = [], [], [], []
    epoch_token = f"epoch:{epoch[0]}:{float(epoch[1]).hex()}"
    for group in built:
        group_ids = group["identities"]
        pivot = next(i for i in group_ids if raw.identity_text(i) == group["pivot"])
        start = len(rows)
        for identity in group_ids:
            if identity == pivot:
                continue
            row = np.zeros(len(ids)); row[index[identity]] = 1; row[index[pivot]] = -1
            rows.append(row); targets.append(identity)
            tokens = (epoch_token, epoch_token) if arc_ids is None else (
                arc_ids[identity], arc_ids[pivot])
            labels.append(json.dumps([raw.identity_text(identity), tokens[0],
                                      raw.identity_text(pivot), tokens[1]], separators=(",", ":")))
        slices.append((group, pivot, start, len(rows)))
    d = np.asarray(rows)
    m, n = d.shape
    code_sd, phase_sd, los, variance = [], [], [], []
    for identity in ids:
        left, right, geom = first[identity], second[identity], qualified[identity]
        wave = signal_spec(identity).wavelength_m
        code_sd.append(right.pr_mes_m - left.pr_mes_m - geom.known_sd_m)
        phase_sd.append((raw.integer_compatible_carrier_cycles(right)
                         - raw.integer_compatible_carrier_cycles(left)) * wave - geom.known_sd_m)
        los.append(geom.los2)
        p1, l1, _ = raw.rawx_standard_deviations(left)
        p2, l2, _ = raw.rawx_standard_deviations(right)
        variance.append((p1*p1+p2*p2, wave*wave*(l1*l1+l2*l2)))
    if sd_covariance is None:
        qsd = np.diag(np.asarray(variance).T.reshape(-1))
        covariance_policy = "INDEPENDENT_RAW_SD_WORKING_MODEL"
    else:
        supplied = tuple(sd_covariance.identities)
        if len(set(supplied)) != len(supplied) or not set(ids) <= set(supplied):
            raise raw.RawBackendError("SD_COVARIANCE_IDENTITY_MISMATCH")
        full = _positive_covariance(sd_covariance.covariance_m2, 2*len(supplied))
        take = [supplied.index(i) for i in ids]
        qsd = full[np.ix_(take + [i+len(supplied) for i in take],
                         take + [i+len(supplied) for i in take])]
        covariance_policy = "SUPPLIED_FULL_SD_COVARIANCE"
    transform = np.block([[d, np.zeros_like(d)], [np.zeros_like(d), d]])
    q = transform @ qsd @ transform.T
    _positive_covariance(q, 2*m)
    y = np.r_[d @ np.asarray(code_sd), d @ np.asarray(phase_sd)]
    if not np.isfinite(y).all():
        raise raw.RawBackendError("NONFINITE_DD_OBSERVATION")
    b = np.vstack((-d @ np.asarray(los), -d @ np.asarray(los)))
    a = np.vstack((np.zeros((m, m)), np.diag([signal_spec(i).wavelength_m for i in targets])))
    group_models = []
    for group, pivot, start, end in slices:
        cols = tuple(range(start, end))
        r = cols + tuple(i+m for i in cols)
        group_models.append(GroupDD(group["group"], pivot, tuple(targets[start:end]),
                            y[list(r)], a[np.ix_(r, cols)], b[list(r)],
                            q[np.ix_(r, r)], tuple(labels[start:end]), r, cols))
    metadata = {"receiver_order": "GNSS2_MINUS_GNSS1", "baseline_frame": "ECEF",
                "dd_sign": "SATELLITE_MINUS_PIVOT", "groups": selected,
                "rejected": rejected, "covariance_policy": covariance_policy,
                "phase_policy": raw.HALF_CYCLE_CONTRACT.phase_value_policy,
                "sd_identities": tuple(raw.identity_text(i) for i in ids),
                "geometry": [{"signal": raw.identity_text(i),
                              "known_sd_m": qualified[i].known_sd_m,
                              "elevation_rad": qualified[i].elevation_rad} for i in ids],
                "arc_label_policy": "EXPLICIT_SD_ARCS" if arc_ids is not None else "EPOCH_LOCAL",
                "timing_policy": "EXACT_RECEIVER_TAG_PAIR_NOT_PHYSICAL_SYNC_CALIBRATION",
                "atmosphere_policy": "SHORT_BASELINE_DIFFERENTIAL_TERMS_UNMODELLED"}
    # Keep metadata JSON serializable, without losing exact signal identities.
    for group in metadata["groups"]:
        if "identities" in group:
            group["identities"] = tuple(raw.identity_text(i) for i in group["identities"])
    return MultiGnssEpoch(epoch[0]*604800.0+epoch[1], y, a, b, q, tuple(labels),
                         tuple(group_models), metadata)
