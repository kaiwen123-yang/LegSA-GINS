"""Finite world-frame common contact motion, in [s_x,s_y,s_z,u_x,u_y,u_z]."""
from __future__ import annotations

from math import exp, expm1, factorial, isfinite

import numpy as np


# 2*x - 3 + 4*exp(-x) - exp(-2*x) starts at order x**3.
# This series avoids subtracting its order-x and order-x**2 terms at short dt.
_DISPLACEMENT_VARIANCE_SERIES = tuple(
    (4*(-1)**n-(-2)**n)/factorial(n) for n in range(3, 21)
)


def support_motion_transition(dt: float, velocity_sigma_mps: float,
                              tau_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact integrated-OU transition and innovation covariance.

    ds=u*dt; du=-u/tau*dt+sqrt(2*sigma_u**2/tau)*dW.  Zero elapsed
    time or zero velocity variance returns exact zero process covariance;
    it is never approximated by a covariance floor.  A fixed-contact model
    omits s/u entirely, including its initial velocity coordinate.
    """
    dt, sigma, tau = float(dt), float(velocity_sigma_mps), float(tau_s)
    if not (isfinite(dt) and dt >= 0. and isfinite(sigma) and sigma >= 0.
            and isfinite(tau) and tau > 0.):
        raise ValueError("support motion requires dt>=0, sigma>=0 and tau>0, all finite")
    x = dt/tau
    rho, one_minus_rho = exp(-x), -expm1(-x)
    transition = np.eye(6)
    transition[:3, 3:] = tau*one_minus_rho*np.eye(3)
    transition[3:, 3:] = rho*np.eye(3)
    covariance = np.zeros((6, 6))
    if dt == 0. or sigma == 0.:
        return transition, covariance

    if x < .5:
        scaled_ss = np.polynomial.polynomial.polyval(x, _DISPLACEMENT_VARIANCE_SERIES)
        q_ss = sigma*sigma*dt*dt*x*scaled_ss
    else:
        q_ss = sigma*sigma*tau*tau*(2*x-2*one_minus_rho-one_minus_rho**2)
    q_su = sigma*sigma*tau*one_minus_rho**2
    q_uu = sigma*sigma*(-expm1(-2*x))
    covariance[:3, :3] = q_ss*np.eye(3)
    covariance[:3, 3:] = covariance[3:, :3] = q_su*np.eye(3)
    covariance[3:, 3:] = q_uu*np.eye(3)
    return transition, covariance
