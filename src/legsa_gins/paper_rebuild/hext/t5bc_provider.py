"""Pure T5bc provider transforms; calibration choices are explicit caller inputs.

No source files are opened and no artifacts are written by this module's builders.
The re-exported raw adapter is the unchanged T5a adapter, to be invoked separately
by an authorized controller. Its zero accuracy placeholders are never used here.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from decimal import Decimal
from dataclasses import asdict, dataclass

import numpy as np

from . import heading_provider as hp
from .t5a_provider import carr_soln, raw_yaw_from_ned  # unchanged frozen-function adapter


class T5BCProviderError(hp.HeadingProviderError):
    def __init__(self, message, *, audit=None):
        super().__init__(message)
        self.audit = audit or {}


def _number(value):
    if isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _key(value):
    number = _number(value)
    if isinstance(value, (str, bytes, bool)) or number is None or int(number) != number or not 0 <= number < hp.WEEK_SECONDS * 1000:
        raise T5BCProviderError("Expected integer within-week iTOW milliseconds")
    return int(number)


def _mapping(values):
    result = {}
    for key, value in values.items():
        key = _key(key)
        if key in result:
            raise T5BCProviderError("Duplicate iTOW mapping")
        result[key] = value
    return result


@dataclass(frozen=True)
class HeadingEpoch:
    itow_ms: int
    yaw_ned_deg: float | None
    baseline_ned_m: tuple[float, float, float] | None
    pacc1_m: float | None
    pacc2_m: float | None
    receiver1_carr_soln: int | None
    receiver2_carr_soln: int | None
    r5_valid: bool
    nominal_variance_rad2: float | None
    r5w_std_deg: float | None
    issues: tuple[str, ...]


@dataclass(frozen=True)
class HeadingWeights:
    baseline_m: float
    k: float
    sigma_deg: float
    epochs: tuple[HeadingEpoch, ...]

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, allow_nan=False,
                                        separators=(",", ":")).encode()).hexdigest()


def prepare_heading_weights(*, raw_yaw_rows, pacc1_m, pacc2_m, pvt_flags1,
                            pvt_flags2, baseline_m, k, sigma_deg):
    """Freeze reusable exact-iTOW weights, without selecting any calibration.

    ``raw_yaw_rows`` are the unchanged T5a adapter's output. Separate pAcc maps
    contain decoded HPPOSECEF metres, not status hAcc or adapter placeholders.
    The T5bc caller fixes L=0.35 m, never a per-epoch baseline norm.
    No standard-deviation floor, cap, fallback scale, or interpolation is used.
    """
    values = [_number(value) for value in (baseline_m, k, sigma_deg)]
    if any(value is None for value in values) or values[0] <= 0 or min(values[1:]) < 0:
        raise T5BCProviderError("Explicit finite L > 0, k >= 0 and sigma_deg >= 0 required")
    baseline_m, k, sigma_deg = values
    raw = {}
    for row in raw_yaw_rows:
        key = _key(row["itow_ms"])
        if key in raw:
            raise T5BCProviderError("Duplicate raw yaw iTOW")
        if _number(row.get("yaw_ned_deg")) is None:
            raise T5BCProviderError("Nonfinite raw heading")
        raw[key] = row
    pa1, pa2, flags1, flags2 = map(_mapping, (pacc1_m, pacc2_m, pvt_flags1, pvt_flags2))
    epochs = []
    for key in sorted(raw.keys() | pa1.keys() | pa2.keys() | flags1.keys() | flags2.keys()):
        row, issues = raw.get(key), []
        states = tuple(carr_soln(flags[key]) if key in flags else None for flags in (flags1, flags2))
        if row is None:
            issues.append("MISSING_RAW_HEADING")
        if None in states:
            issues.append("MISSING_PVT")
        elif states != (2, 2):
            issues.append("NOT_BOTH_FIXED")
        accuracy = []
        for index, mapping in enumerate((pa1, pa2), 1):
            value = _number(mapping.get(key))
            if value is None or value < 0:
                issues.append(f"UNAVAILABLE_PACC{index}_M")
                value = None
            accuracy.append(value)
        vector = tuple(_number(row.get(name)) for name in ("rel_n", "rel_e", "rel_d")) if row is not None else (None,) * 3
        if None in vector:
            issues.append("UNAVAILABLE_BASELINE_NED")
            vector = None
        nominal = sum(value * value for value in accuracy) / baseline_m ** 2 if None not in accuracy else None
        std = math.degrees(k * math.sqrt(nominal)) if nominal is not None else None
        if nominal is not None and (not math.isfinite(nominal) or not math.isfinite(std)):
            raise T5BCProviderError("Nonfinite computed nominal variance or R5W standard deviation")
        epochs.append(HeadingEpoch(key, float(row["yaw_ned_deg"]) if row else None,
                                   vector, *accuracy, *states, row is not None and states == (2, 2),
                                   nominal, std, tuple(issues)))
    if not epochs:
        raise T5BCProviderError("Empty heading weight source")
    return HeadingWeights(baseline_m, k, sigma_deg, tuple(epochs))


def _unmatched_policy(allow_unmatched_times, subset_case_id):
    if type(allow_unmatched_times) is not bool or (allow_unmatched_times and
            (not isinstance(subset_case_id, str) or not re.fullmatch(r'D57(?:_[A-Za-z0-9_-]+)?', subset_case_id))):
        raise T5BCProviderError('Unmatched times require explicit D57-only authorization')


def _table(payload, expected_sha256, gps_week, base_time, *, allow_unmatched_times=False,
           subset_case_id=None):
    _unmatched_policy(allow_unmatched_times, subset_case_id)
    hp._check_sha(payload, expected_sha256, "T5bc input table")
    rows, width = hp._rows(payload)
    if width != 18:
        raise T5BCProviderError("T5bc requires 18-column GNSS tables")
    times = [Decimal(row['tokens'][0].decode()) for row in rows]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise T5BCProviderError('Table time must be unique and chronological')
    keys = []
    for row in rows:
        try:
            key = hp.time_to_itow_ms(row['tokens'][0], gps_week=gps_week, base_time=base_time)
        except hp.HeadingProviderError:
            if not allow_unmatched_times: raise
            key = None
        keys.append(key)
    matched = [key for key in keys if key is not None]
    if any(right <= left for left, right in zip(matched, matched[1:])):
        raise T5BCProviderError('Table iTOW must be unique and chronological')
    return rows, keys


def _token(value):
    return format(value, ".17g").encode("ascii")


def _yaw_token(value):
    token = f"{value % 360.:.6f}".encode("ascii")
    return b"0.000000" if token == b"360.000000" else token


def validate_variant_byte_gate(base_bytes, candidate_bytes, *, r5_reference_bytes,
                               allow_unmatched_times=False, subset_case_id=None):
    """Require non-yaw byte identity and exactly the T5a R5 yaw/valid source."""
    _unmatched_policy(allow_unmatched_times, subset_case_id)
    gate = hp.validate_heading_byte_gate(base_bytes, candidate_bytes)
    after, width = hp._rows(candidate_bytes)
    reference, reference_width = hp._rows(r5_reference_bytes)
    if width != 18 or reference_width != 18 or (not allow_unmatched_times and len(after) != len(reference)):
        raise T5BCProviderError("R5 reference row/column mismatch")
    reference_map = {Decimal(r['tokens'][0].decode()): r for r in reference}
    if len(reference_map) != len(reference):
        raise T5BCProviderError('Duplicate R5 reference time')
    paired = ((row, reference_map.get(Decimal(row['tokens'][0].decode()))) for row in after) if allow_unmatched_times else zip(after, reference)
    unmatched = []
    for row, ref in paired:
        if ref is None:
            if row['tokens'][17] != b'0': raise T5BCProviderError('Unmatched D57 time must have yaw_valid=0')
            unmatched.append(row['tokens'][0].decode())
            continue
        if not allow_unmatched_times and row["tokens"][0] != ref["tokens"][0]:
            raise T5BCProviderError("R5 reference time token mismatch")
        if row["tokens"][17] != ref["tokens"][17]:
            raise T5BCProviderError("R5 validity token mismatch")
        if float(ref["tokens"][17]) == 1 and row["tokens"][13] != ref["tokens"][13]:
            raise T5BCProviderError("R5 valid heading token mismatch")
    return {**gate, 'r5_valid_tokens_byte_equal': True, 'r5_valid_yaw_tokens_byte_equal': True,
            'r5_reference_join': 'EXACT_TIME' if allow_unmatched_times else 'EXACT_ROW_AND_TIME',
            'unmatched_time_tokens': unmatched}


def _std_statistics(rows, f04_yaw_std_min_deg):
    values = [float(row["tokens"][14]) for row in rows]
    valid = [float(row["tokens"][14]) for row in rows if float(row["tokens"][17]) == 1]
    def stats(selected):
        return {"count": len(selected), "minimum_deg": min(selected) if selected else None,
                "maximum_deg": max(selected) if selected else None,
                "loader_below_0p001_deg_count": sum(value < .001 for value in selected),
                "loader_effective_minimum_deg": max(min(selected), .001) if selected else None,
                "loader_effective_maximum_deg": max(max(selected), .001) if selected else None,
                "f04_below_explicit_std_min_count": sum(max(value, .001) < f04_yaw_std_min_deg for value in selected)
                if f04_yaw_std_min_deg is not None else None}
    return {"all_rows": stats(values), "yaw_valid_rows": stats(valid)}


def prepared_raw_rows(base_bytes, *, expected_sha256, gps_week, base_time, weights,
                      r5_reference_bytes, r5_reference_sha256,
                      allow_unmatched_times=False, subset_case_id=None):
    """Exact D2 map for independent runtime checks, including every frozen row."""
    rows, keys = _table(base_bytes, expected_sha256, gps_week, base_time,
                        allow_unmatched_times=allow_unmatched_times, subset_case_id=subset_case_id)
    reference, reference_keys = _table(r5_reference_bytes, r5_reference_sha256, gps_week, base_time)
    if not allow_unmatched_times and keys != reference_keys:
        raise T5BCProviderError('R5 reference iTOW identity mismatch')
    by_time = {Decimal(row['tokens'][0].decode()): row for row in reference}
    epochs = {epoch.itow_ms: epoch for epoch in weights.epochs}
    result = []
    for index, (record, key) in enumerate(zip(rows, keys)):
        ref = by_time.get(Decimal(record['tokens'][0].decode())) if allow_unmatched_times else reference[index]
        epoch = epochs.get(key) if key is not None and ref is not None else None
        valid = bool(epoch and epoch.r5_valid)
        if ref is not None and valid != bool(float(ref['tokens'][17])):
            raise T5BCProviderError('Raw both-fixed validity differs from T5a R5', audit={'itow_ms': key})
        yaw = _yaw_token(epoch.yaw_ned_deg).decode() if epoch and epoch.yaw_ned_deg is not None else None
        if valid and yaw.encode() != ref['tokens'][13]:
            raise T5BCProviderError('R5 valid heading token mismatch')
        vector = epoch.baseline_ned_m if epoch else None
        accuracy = (epoch.pacc1_m, epoch.pacc2_m) if epoch else (None, None)
        reasons = (['V2_ITOW_ROUNDTRIP_UNMATCHED_1US'] if key is None else
                   ['NO_EXACT_R5_REFERENCE_TIME'] if ref is None else
                   list(epoch.issues) if epoch else ['MISSING_EXACT_ITOW_SOURCE'])
        result.append(dict(time_token=record['tokens'][0].decode(), itow_ms=key,
            raw_yaw_token=yaw, std_R5W_token=_token(epoch.r5w_std_deg).decode() if epoch and epoch.r5w_std_deg is not None else None,
            std_R5SIGMA_token=_token(weights.sigma_deg).decode(), raw_valid=valid,
            b_n=vector[0] if vector else None, b_e=vector[1] if vector else None, b_d=vector[2] if vector else None,
            pAcc1=accuracy[0], pAcc2=accuracy[1], reasons=reasons))
    return result


def build_heading_variants(base_bytes, *, expected_sha256, gps_week, base_time,
                           weights: HeadingWeights, r5_reference_bytes,
                           r5_reference_sha256, window, data_mode,
                           f04_yaw_std_min_deg, allow_unmatched_times=False,
                           subset_case_id=None):
    """Apply the same weights to a pinned original or pinned degraded table.

    The R5 reference is independently pinned. Every supported heading and every
    validity token must match it. Missing pAcc on a valid row fails closed rather
    than changing the validity mask. Inactive R5W rows lacking pAcc retain the
    input standard-deviation token, explicitly listed as unavailable.
    """
    if data_mode not in ("real_raw", "real_clean", "synthetic", "semisynthetic"):
        raise T5BCProviderError("Explicit supported data_mode required")
    if len(window) != 2 or any(_number(value) is None for value in window) or window[0] > window[1]:
        raise T5BCProviderError("Finite closed audit window required")
    if f04_yaw_std_min_deg is not None and (_number(f04_yaw_std_min_deg) is None or f04_yaw_std_min_deg < 0):
        raise T5BCProviderError("F04 audit minimum must be explicit finite nonnegative or None")
    rows, keys = _table(base_bytes, expected_sha256, gps_week, base_time,
                        allow_unmatched_times=allow_unmatched_times, subset_case_id=subset_case_id)
    prepared = prepared_raw_rows(base_bytes, expected_sha256=expected_sha256, gps_week=gps_week,
        base_time=base_time, weights=weights, r5_reference_bytes=r5_reference_bytes,
        r5_reference_sha256=r5_reference_sha256, allow_unmatched_times=allow_unmatched_times,
        subset_case_id=subset_case_id)
    epochs = {row.itow_ms: row for row in weights.epochs}
    outputs, audits = {}, {}
    unsupported = []
    for variant in ('R5', "R5W", "R5SIGMA"):
        lines = base_bytes.splitlines(keepends=True)
        for record, mapped, key in zip(rows, prepared, keys):
            epoch = epochs.get(key)
            valid = mapped['raw_valid']
            replacements = {17: b'1' if valid else b'0',
                            13: (mapped['raw_yaw_token'] or '0.000000').encode()}
            std_token = ('2.933193' if variant == 'R5' else mapped['std_R5SIGMA_token']
                         if variant == 'R5SIGMA' else mapped['std_R5W_token'])
            if std_token is None and valid:
                raise T5BCProviderError("R5W valid row lacks pAcc; R5 validity cannot be changed",
                                        audit={"itow_ms": key, "issues": list(epoch.issues)})
            if std_token is not None:
                replacements[14] = std_token.encode()
            elif variant == "R5W":
                unsupported.append(key)
            lines[record["line_index"]] = hp._replace_tokens(record, replacements)
        payload = b"".join(lines)
        gate = validate_variant_byte_gate(base_bytes, payload, r5_reference_bytes=r5_reference_bytes,
                    allow_unmatched_times=allow_unmatched_times, subset_case_id=subset_case_id)
        after, _ = hp._rows(payload)
        outputs[variant] = payload
        audits[variant] = {"sha256": hashlib.sha256(payload).hexdigest(), "byte_gate": gate,
                           "std": {"all_provider": _std_statistics(after, f04_yaw_std_min_deg),
                                   "closed_window": _std_statistics([row for row in after if window[0] <= float(row["tokens"][0]) <= window[1]], f04_yaw_std_min_deg)}}
    return outputs, {"status": "PASS_T5BC_PROVIDER_BYTE_AND_R5_SOURCE_GATES", "data_mode": data_mode,
                     "synthetic_data_used": data_mode == "synthetic", "semisynthetic_data_used": data_mode == "semisynthetic",
                     "weights_sha256": weights.sha256, "explicit_baseline_m": weights.baseline_m,
                     "explicit_k": weights.k, "explicit_sigma_deg": weights.sigma_deg,
                     "source_sha256": expected_sha256, "r5_reference_sha256": r5_reference_sha256,
                     "provider_std_clipping": False, "window": list(window), "provider_cropped": False,
                     "inactive_r5w_std_retained_missing_pacc_itow_ms": unsupported,
                     "f04_yaw_std_min_deg_audit_only": f04_yaw_std_min_deg,
                     "basic_dual_yaw_uses_config_fixed_std_not_provider_std": True,
                     'allow_unmatched_times': allow_unmatched_times, 'subset_case_id': subset_case_id,
                     'unmatched_epochs': [r for r in prepared if r['itow_ms'] is None or
                         'NO_EXACT_R5_REFERENCE_TIME' in r['reasons'] or 'MISSING_EXACT_ITOW_SOURCE' in r['reasons']],
                     "variants": audits, "trace_payload_reads": 0}


def build_baseline3d_sidecar(base_bytes, *, expected_sha256, gps_week, base_time,
                            weights: HeadingWeights, data_mode, prepared_rows=None,
                            allow_unmatched_times=False, subset_case_id=None):
    """Return seven-column CSV bytes; missing observations are empty, valid=0.

    Time text is copied verbatim from GNSS column zero, never reserialized. The
    companion row audit distinguishes absent data, float and reserved carriers.
    The caller/solver must honor valid before interpreting empty numeric cells.
    """
    if data_mode not in ("real_raw", "real_clean", "synthetic", "semisynthetic"):
        raise T5BCProviderError("Explicit supported data_mode required")
    rows, keys = _table(base_bytes, expected_sha256, gps_week, base_time,
                       allow_unmatched_times=allow_unmatched_times, subset_case_id=subset_case_id)
    if allow_unmatched_times and prepared_rows is None:
        raise T5BCProviderError('D57 sidecar requires the exact-time prepared D2 map')
    if prepared_rows is not None and (len(prepared_rows) != len(rows) or
            any(r['time_token'].encode() != row['tokens'][0] for r, row in zip(prepared_rows, rows))):
        raise T5BCProviderError('Prepared D2 map does not match sidecar times')
    epochs = {row.itow_ms: row for row in weights.epochs}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("time", "b_n", "b_e", "b_d", "pAcc1", "pAcc2", "valid"))
    audit_rows = []
    for index, (record, key) in enumerate(zip(rows, keys)):
        epoch = epochs.get(key)
        vector = epoch.baseline_ned_m if epoch else None
        accuracy = (epoch.pacc1_m, epoch.pacc2_m) if epoch else (None, None)
        valid = bool(epoch and epoch.r5_valid and vector is not None and None not in accuracy)
        if prepared_rows is not None:
            mapped = prepared_rows[index]
            vector = tuple(mapped[k] for k in ('b_n', 'b_e', 'b_d'))
            accuracy = tuple(mapped[k] for k in ('pAcc1', 'pAcc2'))
            valid = mapped['raw_valid'] and None not in vector and None not in accuracy
        time_token = record["tokens"][0].decode("ascii")
        values = (*(vector if vector is not None else (None,) * 3), *accuracy)
        writer.writerow((time_token, *(format(value, ".17g") if value is not None else "" for value in values), int(valid)))
        audit_rows.append({"itow_ms": key, "time_token": time_token, "valid": valid,
                           "reasons": prepared_rows[index]['reasons'] if prepared_rows is not None else
                           list(epoch.issues) if epoch else ["MISSING_EXACT_ITOW_SOURCE"]})
    payload = stream.getvalue().encode("ascii")
    return payload, {"data_mode": data_mode, "synthetic_data_used": data_mode == "synthetic",
                     "semisynthetic_data_used": data_mode == "semisynthetic", "sha256": hashlib.sha256(payload).hexdigest(),
                     "source_sha256": expected_sha256, "weights_sha256": weights.sha256,
                     "columns": ["time", "b_n", "b_e", "b_d", "pAcc1", "pAcc2", "valid"],
                     "time_tokens_byte_equal_to_gnss": True, "baseline_and_accuracy_units": "m",
                     "missing_numeric_cells": "EMPTY_WITH_VALID_0_NOT_ZERO_OBSERVATIONS",
                     "interpolation_used": False, "rows": audit_rows,
                     "valid_count": sum(row["valid"] for row in audit_rows), "trace_payload_reads": 0}


def build_baseline3d_gnss(base_bytes, *, expected_sha256):
    """Disable the scalar A1 channel; preserve every non-yaw byte exactly."""
    hp._check_sha(base_bytes, expected_sha256, 'B3 frozen GNSS18')
    rows, width = hp._rows(base_bytes)
    if width != 18: raise T5BCProviderError('B3 requires GNSS18')
    lines = base_bytes.splitlines(keepends=True)
    for row in rows:
        lines[row['line_index']] = hp._replace_tokens(row, {13: b'0.000000', 14: b'2.933193', 17: b'0'})
    payload = b''.join(lines)
    return payload, {**hp.validate_heading_byte_gate(base_bytes, payload),
                     'scalar_yaw_valid_count': 0, 'scalar_yaw_observation_used': False}
