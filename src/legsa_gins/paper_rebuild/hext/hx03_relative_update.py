"""HX-03 LC01-BR: modified LC01, relative measurement only during A2."""
from __future__ import annotations

import numpy as np

from ..horizontal_literature.ext05_pavlasek import (
    UpdateDiagnostics, _covariance, _vec3, skew,
)


def relative_update(filter_, p1, R1, *, receiver2_position_ned_m,
                    receiver2_covariance_ned_m2):
    """Project to the baseline marginal; retain Joseph and right correction."""
    p1 = _vec3(p1, "receiver-1 position")
    p2 = _vec3(receiver2_position_ned_m, "receiver-2 position")
    R1 = _covariance(R1, (3, 3), "receiver-1 covariance")
    R2 = _covariance(receiver2_covariance_ned_m2, (3, 3), "receiver-2 covariance")
    C = filter_.pose.C_nb.copy()
    predicted = C @ filter_.baseline
    residual = (p2 - p1) - predicted
    z = C.T @ residual
    H = np.zeros((3, 9))
    H[:, :3] = skew(filter_.baseline)
    R = C.T @ (R1 + R2) @ C
    P = filter_.covariance
    S = H @ P @ H.T + R
    S = 0.5 * (S + S.T)
    gain = np.linalg.solve(S, H @ P).T
    solved = np.linalg.solve(S, z)
    correction = gain @ z
    joseph = np.eye(9) - gain @ H
    posterior = joseph @ P @ joseph.T + gain @ R @ gain.T
    predicted_p1 = filter_.pose.position_ned_m + C @ filter_.lever
    filter_.pose.right_correct(correction)
    filter_.covariance = _covariance(0.5 * (posterior + posterior.T), (9, 9), "posterior covariance")
    filter_.update_count += 1
    return UpdateDiagnostics(
        innovation=z, predicted_receiver1_ned_m=predicted_p1,
        predicted_relative_ned_m=predicted, receiver1_residual_ned_m=np.zeros(3),
        relative_residual_ned_m=residual, innovation_covariance=S, gain=gain,
        nis=float(z @ solved), correction=correction,
    )


def scheduled_update(filter_, p1, R1, *, relative_only=False, **kwargs):
    if relative_only:
        return relative_update(filter_, p1, R1, **kwargs)
    return filter_.update(p1, R1, **kwargs)
