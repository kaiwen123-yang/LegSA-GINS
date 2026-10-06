"""Necessary geometric checks from qualified gravity and directed body rotation.

This research kernel checks one exact, fixed-length baseline pair, not an integer
class or a continuous confidence region. FEASIBLE means only that the tested
necessary invariants do not contradict the declared prior; it is not an SO(3)
existence certificate, ambiguity acceptance or a calibrated failure probability.

D maps the second body frame to the first. With a single common R in SO(3),
(b1,b2)=(R r,R D r), q=R.T g. g and q are signed unit gravity directions.
The exact mounting vector and length are explicit mathematical assumptions.
Real mounting/length/time errors require a separate bounded model before use.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


class DirectedMotionError(ValueError):
    """Malformed geometry or uncertainty declaration; never an acceptance."""


def _vector(value, name, *, unit=False):
    a = np.array(value, dtype=float, copy=True)
    if a.shape != (3,) or not np.isfinite(a).all():
        raise DirectedMotionError(f'{name}: finite three-vector required')
    length = float(np.linalg.norm(a))
    if not math.isfinite(length) or length <= 0:
        raise DirectedMotionError(f'{name}: nonzero finite norm required')
    if unit and abs(length - 1.) > 1e-12:
        raise DirectedMotionError(f'{name}: unit direction required; no implicit normalization')
    a.setflags(write=False)
    return a


def _text(value):
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class DirectedMotionPrior:
    body_baseline_m: np.ndarray
    relative_rotation: np.ndarray
    navigation_gravity_unit: np.ndarray | None
    body_gravity_unit: np.ndarray | None
    gravity_angle_error_rad: float | None
    rotation_angle_error_rad: float | None
    source_id: str
    uncertainty_source_id: str | None
    qualified: bool
    exact_geometry_justification: str
    zero_error_justification: str | None = None

    def __post_init__(self):
        r = _vector(self.body_baseline_m, 'body baseline')
        d = np.array(self.relative_rotation, dtype=float, copy=True)
        if (d.shape != (3, 3) or not np.isfinite(d).all()
                or np.max(abs(d.T @ d - np.eye(3))) > 1e-12
                or abs(np.linalg.det(d) - 1.) > 1e-12):
            raise DirectedMotionError('relative rotation must be proper SO(3)')
        d.setflags(write=False)
        object.__setattr__(self, 'body_baseline_m', r)
        object.__setattr__(self, 'relative_rotation', d)
        for field in ('navigation_gravity_unit', 'body_gravity_unit'):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _vector(value, field, unit=True))
        for field in ('gravity_angle_error_rad', 'rotation_angle_error_rad'):
            value = getattr(self, field)
            if value is not None and (isinstance(value, bool)
                    or not math.isfinite(value) or not 0 <= value <= math.pi):
                raise DirectedMotionError(f'{field}: explicit angle bound in [0,pi] required')
        if not _text(self.source_id):
            raise DirectedMotionError('prior source identity required')
        if not _text(self.exact_geometry_justification):
            raise DirectedMotionError('exact mounting/length assumption must be explicit')
        if not isinstance(self.qualified, bool):
            raise DirectedMotionError('qualified must be an explicit boolean')


@dataclass(frozen=True)
class InvariantCheck:
    name: str
    unit: str
    candidate_value: float
    nominal_value: float
    bound: float
    lower: float
    upper: float
    arithmetic_margin: float
    consistent: bool


@dataclass(frozen=True)
class DirectedMotionResult:
    status: str
    reason: str
    source_id: str
    checks: tuple[InvariantCheck, ...] = ()
    directed_sign_qualified: bool = False
    scope: str = 'NECESSARY_INVARIANTS_OF_ONE_EXACT_BASELINE_PAIR'
    integer_acceptance_defined: bool = False
    false_fix_probability: None = None
    physical_prior_certified: bool = False


def qualify_directed_pair(first_baseline_m, second_baseline_m,
                          prior: DirectedMotionPrior) -> DirectedMotionResult:
    """Return FEASIBLE, CONTRADICTION or UNQUALIFIED for this point pair only.

    No default physical error bounds exist. Missing bounds/source, unqualified
    prior, unknown gravity, or a signed-area interval touching zero is unresolved.
    Explicit zero bounds require a nonempty justification (e.g. a synthetic exact
    case); this does not certify a physical sensor. With an incorrect bound even
    the true pair can be contradicted. Withdrawing the prior must be handled by
    the caller against its retained, unfiltered candidate support.
    """
    if not isinstance(prior, DirectedMotionPrior):
        raise DirectedMotionError('DirectedMotionPrior required')
    a = _vector(first_baseline_m, 'first baseline')
    b = _vector(second_baseline_m, 'second baseline')
    length = float(np.linalg.norm(prior.body_baseline_m))
    # Roundoff tolerance is not measurement noise or a physical length allowance.
    length_margin = 256 * np.finfo(float).eps * length
    if any(abs(float(np.linalg.norm(v)) - length) > length_margin for v in (a, b)):
        raise DirectedMotionError('candidate must obey the declared exact baseline length')

    def unresolved(reason, checks=()):
        return DirectedMotionResult('UNQUALIFIED', reason, prior.source_id, checks)

    if not prior.qualified:
        return unresolved('PRIOR_NOT_QUALIFIED')
    if prior.navigation_gravity_unit is None or prior.body_gravity_unit is None:
        return unresolved('GRAVITY_UNKNOWN')
    if prior.gravity_angle_error_rad is None or prior.rotation_angle_error_rad is None:
        return unresolved('MISSING_DETERMINISTIC_ERROR_BOUND')
    if not _text(prior.uncertainty_source_id):
        return unresolved('MISSING_UNCERTAINTY_SOURCE')
    eq, ed = float(prior.gravity_angle_error_rad), float(prior.rotation_angle_error_rad)
    if (eq == 0. or ed == 0.) and not _text(prior.zero_error_justification):
        return unresolved('ZERO_ERROR_BOUND_UNJUSTIFIED')

    r, d = prior.body_baseline_m, prior.relative_rotation
    g, q = prior.navigation_gravity_unit, prior.body_gravity_unit
    dr = d @ r
    # q is assumed within eq of R.T@g; true D within geodesic ed of d.
    # ||q-qhat|| <= 2 sin(eq/2), ||(D-Dhat)r|| <= 2L sin(ed/2).
    # The bounds are necessary outer bounds, not independent probability tests.
    q_chord, d_chord = 2 * math.sin(eq / 2), 2 * math.sin(ed / 2)
    data = (
        ('first_gravity_projection', 'm', float(g @ a), float(q @ r), length*q_chord, length),
        ('second_gravity_projection', 'm', float(g @ b), float(q @ dr),
         length*(q_chord+d_chord), length),
        ('directed_gravity_area', 'm^2', float(g @ np.cross(a, b)),
         float(q @ np.cross(r, dr)), length**2*(q_chord+d_chord), length**2),
    )
    checks = []
    for name, unit, observed, nominal, bound, scale in data:
        # This is merely a floating-point guard; it is not part of sensor Q.
        # Include the admitted 1e-12 unit/SO(3) representation tolerance.
        margin = (512 * np.finfo(float).eps + 8e-12) * scale
        low, high = max(-scale, nominal-bound), min(scale, nominal+bound)
        checks.append(InvariantCheck(name, unit, observed, nominal, bound, low, high,
                                     margin, low-margin <= observed <= high+margin))
    checks = tuple(checks)
    area = checks[-1]
    if area.lower <= area.arithmetic_margin and area.upper >= -area.arithmetic_margin:
        return unresolved('DIRECTED_AREA_SIGN_UNRESOLVED', checks)
    failures = tuple(c.name for c in checks if not c.consistent)
    if failures:
        return DirectedMotionResult('CONTRADICTION', ','.join(failures), prior.source_id,
                                    checks, True)
    return DirectedMotionResult('FEASIBLE', 'TESTED_NECESSARY_INVARIANTS_CONSISTENT',
                                prior.source_id, checks, True)
