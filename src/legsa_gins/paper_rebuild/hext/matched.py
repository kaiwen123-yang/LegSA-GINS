"""H-EXT-04 external update scheduling and the relative-N/E diagnostic adapter.

The frozen Pavlasek filter source is imported unchanged. All-three-component
updates delegate to it directly; the N/E adapter only projects the original
measurement system before applying the same Kalman/Joseph/SE_2(3) equations.
NOT_AUTHORIZED_FOR_EXECUTION: library-only reuse; T5 requires preregistration.
No data provider, trace, native process or evaluator is invoked by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Iterable

import numpy as np

from ..horizontal_literature.ext05_pavlasek import (
    PavlasekFilterError, PavlasekIEKF, UpdateDiagnostics,
    _covariance, _vec3, measurement_jacobian, stacked_position_covariance,
)

EXECUTION_STATUS = "NOT_AUTHORIZED_FOR_EXECUTION"

NED_COMPONENTS = ("N", "E", "D")
NE_COMPONENTS = ("N", "E")


def _components(value):
    value = tuple(value)
    if value not in (NED_COMPONENTS, NE_COMPONENTS):
        raise ValueError("H-EXT-04 relative components must be N/E or N/E/D in fixed NED order")
    return value


def relative_projection(rotation, components=NE_COMPONENTS):
    """Map frozen invariant-body relative residuals to the selected NED rows.

    The first position residual remains in its original invariant-body frame.
    Relative N/E selection requires P = blockdiag(I3, S_NE @ C_nb), rather
    than dropping the invariant-body z component. For all three components
    the original representation is retained exactly, with no rotation roundtrip.
    """
    components = _components(components)
    rotation = np.asarray(rotation, dtype=float)
    if rotation.shape != (3, 3) or not np.isfinite(rotation).all():
        raise PavlasekFilterError("relative projection requires a finite 3x3 C_nb")
    if components == NED_COMPONENTS:
        return np.eye(6)
    projection = np.zeros((5, 6))
    projection[:3, :3] = np.eye(3)
    projection[3:, 3:] = np.eye(3)[:2] @ rotation
    return projection


@dataclass(frozen=True)
class ProjectedMeasurement:
    innovation: np.ndarray
    jacobian: np.ndarray
    covariance: np.ndarray
    projection: np.ndarray
    predicted_receiver1_ned_m: np.ndarray
    predicted_relative_ned_m: np.ndarray
    receiver1_residual_ned_m: np.ndarray
    relative_residual_ned_m: np.ndarray


def relative_measurement_system(filter_: PavlasekIEKF, receiver1_position_ned_m,
                                receiver1_covariance_ned_m2, *, receiver2_position_ned_m,
                                receiver2_covariance_ned_m2, components=NE_COMPONENTS):
    """Build the frozen correlated [p1,p2-p1] system and project z, H and R."""
    if not filter_.two_receiver or filter_.H.shape != (6, 9):
        raise PavlasekFilterError("relative projection requires the original dual-receiver system")
    components = _components(components)
    p1 = _vec3(receiver1_position_ned_m, "receiver-1 position")
    R1 = _covariance(receiver1_covariance_ned_m2, (3, 3), "receiver-1 covariance")
    p2 = _vec3(receiver2_position_ned_m, "receiver-2 position")
    R2 = _covariance(receiver2_covariance_ned_m2, (3, 3), "receiver-2 covariance")
    rotation_before = filter_.pose.C_nb.copy()
    predicted_p1 = filter_.pose.position_ned_m + rotation_before @ filter_.lever
    residual1 = p1 - predicted_p1
    predicted_relative = rotation_before @ filter_.baseline
    residual_relative = (p2 - p1) - predicted_relative
    innovation = np.concatenate((rotation_before.T @ residual1, rotation_before.T @ residual_relative))
    measurement_covariance = stacked_position_covariance(R1, R2)
    transform = np.zeros((6, 6))
    transform[:3, :3] = rotation_before.T
    transform[3:6, 3:6] = rotation_before.T
    invariant_covariance = transform @ measurement_covariance @ transform.T
    projection = relative_projection(rotation_before, components)
    if components == NED_COMPONENTS:
        return ProjectedMeasurement(innovation, filter_.H, invariant_covariance, projection,
                                    predicted_p1, predicted_relative, residual1, residual_relative)
    return ProjectedMeasurement(projection @ innovation, projection @ filter_.H,
                                projection @ invariant_covariance @ projection.T, projection,
                                predicted_p1, predicted_relative, residual1, residual_relative)


def update_relative_components(filter_: PavlasekIEKF, receiver1_position_ned_m,
                                receiver1_covariance_ned_m2, *, receiver2_position_ned_m,
                                receiver2_covariance_ned_m2, components=NE_COMPONENTS):
    """Apply unchanged update equations after relative N/E row projection.

    N/E/D delegates directly, so the all-component equivalence gate has exactly
    the original operation ordering and serialization. The projection does not
    alter propagation, initialization, covariance parameters or correction side.
    """
    components = _components(components)
    if components == NED_COMPONENTS:
        return filter_.update(receiver1_position_ned_m, receiver1_covariance_ned_m2,
            receiver2_position_ned_m=receiver2_position_ned_m,
            receiver2_covariance_ned_m2=receiver2_covariance_ned_m2)
    system = relative_measurement_system(filter_, receiver1_position_ned_m,
        receiver1_covariance_ned_m2, receiver2_position_ned_m=receiver2_position_ned_m,
        receiver2_covariance_ned_m2=receiver2_covariance_ned_m2, components=components)
    innovation, H, R = system.innovation, system.jacobian, system.covariance
    S = H @ filter_.covariance @ H.T + R
    S = 0.5 * (S + S.T)
    try:
        gain = np.linalg.solve(S, H @ filter_.covariance).T
        solved_innovation = np.linalg.solve(S, innovation)
    except np.linalg.LinAlgError as exc:
        raise PavlasekFilterError("innovation covariance is singular") from exc
    correction = gain @ innovation
    identity = np.eye(9)
    joseph = identity - gain @ H
    posterior = joseph @ filter_.covariance @ joseph.T + gain @ R @ gain.T
    filter_.pose.right_correct(correction)
    filter_.covariance = _covariance(0.5 * (posterior + posterior.T), (9, 9), "posterior covariance")
    filter_.update_count += 1
    return UpdateDiagnostics(
        innovation=innovation, predicted_receiver1_ned_m=system.predicted_receiver1_ned_m,
        predicted_relative_ned_m=system.predicted_relative_ned_m,
        receiver1_residual_ned_m=system.receiver1_residual_ned_m,
        relative_residual_ned_m=system.relative_residual_ned_m,
        innovation_covariance=S, gain=gain,
        nis=float(innovation @ solved_innovation), correction=correction,
    )


def _itow(value):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("iTOW must be an integer millisecond value")
    number = float(value)
    if not np.isfinite(number) or number != int(number) or not 0 <= number < 604800000:
        raise ValueError("iTOW must be an integer millisecond value within a GPS week")
    return int(number)


class MatchedEpochUpdate:
    """Drop-in GNSS-event callback for the unchanged H02 chronological loop.

    ``epoch_itow_ms=None`` selects native 5 Hz scheduling (the 2D diagnostic).
    A finite set selects the D1 matched epochs; outside it the existing p1-only
    update is applied, retaining exactly the original single-receiver arithmetic.
    Initialization is untouched, including its dual-baseline yaw source.
    """

    def __init__(self, epoch_itow_ms: Iterable[int] | None, *, components=NED_COMPONENTS):
        self.components = _components(components)
        self.epochs = None if epoch_itow_ms is None else frozenset(_itow(value) for value in epoch_itow_ms)
        if self.epochs is not None and self.components != NED_COMPONENTS:
            raise ValueError("H-EXT-04 authorizes N/E projection only with native 5 Hz scheduling")
        self.events: list[dict[str, Any]] = []

    def __call__(self, filter_, arrays, index, *, state_time, base_time,
                 two_receiver, method_id, innovation_rows, nis_rows):
        from .ext05_sequence_runner import _h02_gnss_update

        if not two_receiver or not filter_.two_receiver or filter_.H.shape != (6, 9):
            raise ValueError("H-EXT-04 matched/2D callback requires an LC01 dual-receiver filter")
        itow = _itow(arrays["solution_itow"][index])
        dual = self.epochs is None or itow in self.epochs
        kwargs = dict(state_time=state_time, base_time=base_time, two_receiver=dual,
                      method_id=method_id, innovation_rows=innovation_rows, nis_rows=nis_rows)
        if dual:
            if self.components == NED_COMPONENTS:
                accepted = _h02_gnss_update(filter_, arrays, index, **kwargs)
            else:
                accepted = _h02_gnss_update(filter_, arrays, index, **kwargs,
                    measurement_update=partial(update_relative_components, filter_, components=self.components))
        else:
            original_H, original_two_receiver = filter_.H, filter_.two_receiver
            try:
                filter_.two_receiver = False
                filter_.H = measurement_jacobian(filter_.lever, filter_.baseline, two_receiver=False)
                accepted = _h02_gnss_update(filter_, arrays, index, **kwargs)
            finally:
                filter_.H, filter_.two_receiver = original_H, original_two_receiver
        self.events.append({"provider_epoch_index": int(index), "itow_ms": itow,
                            "absolute_time_unix_seconds": float(state_time),
                            "time_seconds": float(state_time - base_time),
                            "update_path": "ORIGINAL_DUAL" if dual and self.components == NED_COMPONENTS
                                           else "RELATIVE_NE" if dual else "ORIGINAL_SINGLE_P1",
                            "requested_relative_components": list(self.components) if dual else [],
                            "accepted": bool(accepted)})
        return accepted

    def audit(self):
        accepted = [row for row in self.events if row["accepted"]]
        observed = {row["itow_ms"] for row in self.events}
        return {"update_schedule": "NATIVE_5HZ" if self.epochs is None else "MATCHED_1HZ_RELATIVE",
                "relative_measurement_dims": len(self.components), "relative_components": list(self.components),
                "epoch_set_size": "NOT_APPLICABLE" if self.epochs is None else len(self.epochs),
                "epoch_itow_ms": None if self.epochs is None else sorted(self.epochs),
                "epoch_set_not_observed_after_initialization": None if self.epochs is None else sorted(self.epochs - observed),
                "attempted_update_count": len(self.events), "accepted_update_count": len(accepted),
                "invalid_update_count": len(self.events) - len(accepted),
                "dual_update_count": sum(row["update_path"] != "ORIGINAL_SINGLE_P1" for row in accepted),
                "single_receiver_update_count": sum(row["update_path"] == "ORIGINAL_SINGLE_P1" for row in accepted),
                "initialization_unchanged_independent_of_schedule": True,
                "time_matching": "EXACT_INTEGER_ITOW_MILLISECONDS_NO_TOLERANCE_OR_SEARCH",
                "events": list(self.events)}
