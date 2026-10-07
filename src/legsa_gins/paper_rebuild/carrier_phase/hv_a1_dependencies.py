"""Dependencies of the frozen GNSS18-to-HV heading interpolation.

This is a read-only timing helper, not a velocity generator. Source times refer
only to the CALIBRATED_GNSS input rows used by correct_hv, not raw receiver
sampling times or actual arrival. No yaw, velocity, covariance or residual is
accepted. The caller retains the filtered-endpoint-index to input-row mapping.
"""
from __future__ import annotations

import math
import numpy as np


SCOPE = "CALIBRATED_GNSS18_INTERPOLATION_ENDPOINTS_ONLY"


def _times(values, name):
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(name + " must be a finite one-dimensional time array") from exc
    if result.ndim != 1 or not np.isfinite(result).all():
        raise ValueError(name + " must be a finite one-dimensional time array")
    return result


def dependencies(query_times, endpoint_source_times, *, round_to_ms=True,
                 maximum_gap_s=1.2):
    """Return one record per query, preserving unsupported queries.

    Reproduce correct_hv's float64 np.rint(t*1000)/1000 coordinates (unless
    timing-fault mode explicitly disables rounding), exact endpoint equality,
    np.interp's constant outside values and open-interior long-gap support mask.
    No epsilon snapping, sorting, deduplication or timestamp repair occurs.

    endpoint_indices are zero-based in the caller's already-valid GNSS18
    endpoint sequence. Unsupported outside/long-gap records still name the
    nonzero interpolation dependencies because the producer computed these
    values before setting update_flag false. NO_ENDPOINTS has no dependencies.

    An exact endpoint has only its own coefficient; a strict interior retains
    both endpoints without a small-weight cutoff. The two coefficients are
    calculated separately to avoid cancelling 1-alpha near an endpoint; they
    describe the linear interpolant, not np.interp's floating operation order.

    unwrap_prefix_last_index records that np.unwrap forms a prefix through the
    last named endpoint. Earlier endpoints can determine integer-2pi branches;
    common 2pi shifts cancel in downstream sin/cos mathematically, not as a
    promised bitwise identity. This helper does not certify upstream source or
    arrival causality and does not recompute unwrap or the heading value.
    """
    query = _times(query_times, "query_times")
    source = _times(endpoint_source_times, "endpoint_source_times")
    if type(round_to_ms) is not bool:
        raise ValueError("round_to_ms must be explicit bool")
    try:
        gap_limit = float(maximum_gap_s)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("maximum_gap_s must be finite and nonnegative") from exc
    if not math.isfinite(gap_limit) or gap_limit < 0:
        raise ValueError("maximum_gap_s must be finite and nonnegative")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            coordinates = np.rint(source * 1000) / 1000. if round_to_ms else source.copy()
            spans = np.diff(coordinates)
            if not np.isfinite(coordinates).all() or not np.isfinite(spans).all() or np.any(spans <= 0):
                raise ValueError("endpoint coordinates must be finite, ordered and unique after rounding")
            result = []
            for query_index, q in enumerate(query):
                indices, weights = [], []
                support, kind = False, "NO_ENDPOINTS"
                if len(coordinates):
                    right = int(np.searchsorted(coordinates, q, side="left"))
                    if right < len(coordinates) and q == coordinates[right]:
                        indices, weights = [right], [1.0]
                        support, kind = True, "EXACT_ENDPOINT"
                    elif right == 0:
                        indices, weights, kind = [0], [1.0], "OUTSIDE_LEFT"
                    elif right == len(coordinates):
                        indices, weights, kind = [right - 1], [1.0], "OUTSIDE_RIGHT"
                    else:
                        left = right - 1
                        span = spans[left]
                        weights = [float((coordinates[right] - q) / span),
                                   float((q - coordinates[left]) / span)]
                        if not all(math.isfinite(w) and 0 < w <= 1 for w in weights):
                            raise ValueError("strict interior coefficients unresolved; no dependency may be dropped")
                        indices = [left, right]
                        support = bool(span <= gap_limit)
                        kind = "INTERIOR" if support else "LONG_GAP_INTERIOR"
                source_times = [float(source[i]) for i in indices]
                result.append({
                    "scope": SCOPE,
                    "query_index": query_index,
                    "query_time": float(q),
                    "support": support,
                    "kind": kind,
                    "endpoint_indices": indices,
                    "weights": weights,
                    "endpoint_source_times": source_times,
                    "endpoint_coordinates": [float(coordinates[i]) for i in indices],
                    "latest_endpoint_source_time": max(source_times) if source_times else None,
                    "unwrap_prefix_last_index": max(indices) if indices else None,
                    "actual_arrival_qualified": False,
                })
            return result
    except FloatingPointError as exc:
        raise ValueError("nonfinite interpolation coordinate or coefficient arithmetic") from exc
