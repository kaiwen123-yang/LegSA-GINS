"""Analytic continuous-domain azimuth covers, without integer search or refits.

The domain is (b-c)' C^-1 (b-c) <= rho intersect ||b|| in [lo, hi].
Exact horizontal ellipse tangents and a length/3D-outer-ball spherical cap
supply necessary azimuth covers. Their intersection is retained componentwise.
This is a guarded floating-point outer cover, NOT an interval certificate,
integer acceptance, physical coverage probability, or a new fault diagnosis.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from .candidate_envelope import CircularArc, enclosing_arc

TAU = 2*math.pi


def _wrap(x):
    return (float(x)+math.pi) % TAU-math.pi


@dataclass(frozen=True)
class CircularCover:
    components: tuple[CircularArc, ...]

    @property
    def empty(self):
        return not self.components

    @property
    def full_circle(self):
        return any(a.full_circle for a in self.components)

    @property
    def total_width_rad(self):
        return sum(a.width_rad for a in self.components)

    @property
    def enclosing_arc(self):
        return enclosing_arc(self.components)

    def contains(self, angle_rad, *, tolerance=0.):
        if not math.isfinite(angle_rad) or not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError('finite angle and nonnegative tolerance required')
        return any(a.full_circle or (angle_rad-a.start_rad+tolerance) % TAU
                   <= a.width_rad+2*tolerance for a in self.components)


def _pieces(cover):
    pieces=[]
    for a in cover.components:
        if not math.isfinite(a.start_rad) or not math.isfinite(a.width_rad) or not 0 <= a.width_rad <= TAU:
            raise ValueError('invalid circular arc')
        if a.full_circle:
            return [(0., TAU)]
        lo=a.start_rad % TAU
        hi=lo+a.width_rad
        if hi <= TAU:
            pieces.append((lo, hi))
        else:
            pieces.extend(((lo, TAU), (0., hi-TAU)))
        # Zero and 2pi are the same closed endpoint.
        if lo == 0.:
            pieces.append((TAU, TAU))
        if hi == TAU:
            pieces.append((0., 0.))
    return pieces


def _cover(pieces):
    merged=[]
    for lo,hi in sorted(pieces):
        if not (0 <= lo <= hi <= TAU):
            raise ValueError('invalid linearized circle interval')
        if merged and lo <= merged[-1][1]:
            merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
        else:
            merged.append((lo,hi))
    if not merged:
        return CircularCover(())
    if merged == [(0.,TAU)]:
        return CircularCover((CircularArc(-math.pi,TAU),))
    if len(merged)>1 and merged[0][0]==0. and merged[-1][1]==TAU:
        first,last=merged.pop(0),merged.pop(-1)
        merged.append((last[0],TAU+first[1]))
    return CircularCover(tuple(CircularArc(_wrap(lo),hi-lo) for lo,hi in merged))


def cover_from_arcs(arcs):
    return _cover(_pieces(CircularCover(tuple(arcs))))


def _arc(center, halfwidth, guard):
    width=min(TAU,2*(halfwidth+guard))
    return cover_from_arcs((CircularArc(_wrap(center-width/2),width),))


def intersect_covers(*covers, angular_guard_rad=1e-10):
    """Intersection preserving wrap components and guarded near-touch endpoints.

    A near-empty pair within the declared guard retains a small interval rather
    than claiming a numerically established empty domain. This can widen by the
    explicit guard; it never selects just one connected component.
    """
    if not math.isfinite(angular_guard_rad) or not 0 < angular_guard_rad < 1e-3:
        raise ValueError('positive small angular guard required')
    result=cover_from_arcs((CircularArc(-math.pi,TAU),))
    for cover in covers:
        pieces=[]
        # Shift the right cover across the circle seam before intersections.
        for a,b in _pieces(result):
            for c,d in _pieces(cover):
                for shift in (-TAU,0.,TAU):
                    lo,hi=max(a,c+shift),min(b,d+shift)
                    if lo<=hi:
                        pieces.append((lo,hi))
                    elif lo-hi<=angular_guard_rad:
                        pieces.append((max(0.,hi-angular_guard_rad),min(TAU,lo+angular_guard_rad)))
        result=_cover(pieces)
    return result


@dataclass(frozen=True)
class SphereDirectionEnvelope:
    status: str
    cover: CircularCover
    ellipse_cover: CircularCover
    sphere_cap_cover: CircularCover
    raw_budget: float
    length_interval_m: tuple[float,float]
    three_dimensional_outer_radius_m: float | None
    cap_cosine_lower_bound: float | None
    horizontal_ellipse_origin_included: bool | None
    sphere_cap_contains_pole: bool | None
    numerical_guard_rad: float
    rigorous_interval_certificate: bool = False
    integer_acceptance_defined: bool = False
    physical_coverage_probability: None = None
    false_fix_probability: None = None


def sphere_direction_envelope(center_m,covariance_m2,raw_budget,*,horizontal_axes,
        length_interval_m,recorded_outer_radius_m=None,legacy_cover=None,
        relative_guard=1e-10,angular_guard_rad=1e-10,max_condition_number=1e12):
    """Cover the WHOLE ellipsoid/length intersection, not its optimum or center.

    All arrays are in the same Cartesian frame. Horizontal rows must be explicit
    orthonormal axes. A shell is supported algebraically, but must be externally
    registered: this function never invents length uncertainty. Quality/fault
    labels are not inputs and cannot influence geometry.

    Invalid numerical inputs raise; callers must preserve the old cover and mark
    the new computation unqualified, never convert an exception to an empty set.
    Negative raw_budget proves the supplied raw domain empty without refitting.
    """
    c=np.array(center_m,float,copy=True)
    C=np.array(covariance_m2,float,copy=True)
    P=np.array(horizontal_axes,float,copy=True)
    rho=float(raw_budget)
    lo,hi=map(float,length_interval_m)
    if (c.shape!=(3,) or C.shape!=(3,3) or P.shape!=(2,3)
            or not np.isfinite(c).all() or not np.isfinite(C).all() or not np.isfinite(P).all()
            or not math.isfinite(rho) or not 0<lo<=hi or not math.isfinite(hi)):
        raise ValueError('finite 3D mean/covariance, axes, raw budget and positive length interval required')
    if (not math.isfinite(relative_guard) or not 0<relative_guard<1e-3
            or not math.isfinite(angular_guard_rad) or not 0<angular_guard_rad<1e-3
            or not math.isfinite(max_condition_number) or max_condition_number<=1):
        raise ValueError('explicit finite numerical guards required')
    if np.max(abs(P@P.T-np.eye(2)))>1e-12:
        raise ValueError('horizontal axes must be orthonormal')
    normC=float(np.max(abs(C)))
    if normC<=0 or np.max(abs(C-C.T))>1e-12*normC:
        raise ValueError('symmetric positive covariance required')
    C=(C+C.T)/2
    eigen=np.linalg.eigvalsh(C)
    if not np.isfinite(eigen).all() or eigen[0]<=0 or eigen[-1]/eigen[0]>max_condition_number:
        raise ValueError('unqualified covariance spectrum')
    empty=CircularCover(())
    full=cover_from_arcs((CircularArc(-math.pi,TAU),))
    if rho<0:
        return SphereDirectionEnvelope('EMPTY_RAW_DOMAIN',empty,empty,empty,rho,(lo,hi),None,None,None,None,angular_guard_rad)
    radius=math.sqrt(rho)*math.sqrt(float(eigen[-1]))
    s=float(np.linalg.norm(c))
    scale=max(s,hi,radius,np.finfo(float).tiny)
    epsilon=relative_guard*scale
    r=radius*math.sqrt(1+relative_guard)+epsilon
    if recorded_outer_radius_m is not None:
        old=float(recorded_outer_radius_m)
        if not math.isfinite(old) or old<0:
            raise ValueError('finite nonnegative recorded outer radius required')
        r=max(r,old)
    if not all(math.isfinite(v) for v in (s,scale,epsilon,r)):
        raise ValueError('nonfinite radius/scale')

    # E_h is exact before explicit outward floating guards. A coordinate error
    # ball epsilon is enclosed by enlarging whitened radius by epsilon/sqrt(lmin).
    ch=P@c
    C2=P@C@P.T
    e2=np.linalg.eigvalsh(C2)
    if not np.isfinite(e2).all() or e2[0]<=0 or e2[-1]/e2[0]>max_condition_number:
        raise ValueError('unqualified horizontal covariance spectrum')
    L2=np.linalg.cholesky(C2)
    u=np.linalg.solve(L2,ch)
    n2=float(u@u)
    rho2=(math.sqrt(rho)*math.sqrt(1+relative_guard)+epsilon/math.sqrt(float(e2[0])))**2
    if not all(math.isfinite(v) for v in (n2,rho2)):
        raise ValueError('nonfinite horizontal tangent inputs')
    origin=n2<=rho2*(1+relative_guard)
    if origin:
        ellipse=full
    else:
        a=min(1.,rho2/n2)
        perp=np.array([-u[1],u[0]])
        t0=u*(1-a)
        delta=perp*math.sqrt(a*(1-a))
        hminus,hplus=L2@(t0-delta),L2@(t0+delta)
        center=math.atan2(ch[1],ch[0])
        angles=[_wrap(math.atan2(h[1],h[0])-center) for h in (hminus,hplus)]
        amin,amax=min(angles),max(angles)
        if amax-amin>=math.pi or not amin<=0<=amax:
            raise ValueError('unqualified ellipse tangent orientation')
        ellipse=_arc(center+(amin+amax)/2,(amax-amin)/2,angular_guard_rad)

    # The minimum k over a shell is attained at endpoints or sqrt(s^2-r^2).
    # Scale-free expressions avoid cancellation/overflow in lengths squared.
    cap_k=None
    pole=None
    if s<=epsilon:
        if lo>s+r+epsilon:
            cap=empty
        else:
            cap=full
            pole=True
    else:
        sn,rn=s/scale,r/scale
        lengths=[lo/scale,hi/scale]
        stationary2=sn*sn-rn*rn
        if stationary2>0:
            stationary=math.sqrt(stationary2)
            if lengths[0]<=stationary<=lengths[1]:lengths.append(stationary)
        k=min((ell*ell+sn*sn-rn*rn)/(2*ell*sn) for ell in lengths)
        # Lowering k enlarges the cap. This guard is numerical, not covariance.
        k-=relative_guard*max(1.,abs(k))
        if not math.isfinite(k):
            raise ValueError('nonfinite cap cosine')
        cap_k=k
        if k>1+relative_guard:
            cap=empty
            pole=False
        elif k<=-1:
            cap=full
            pole=True
        else:
            # Values indistinguishable from the tangent k=1 remain nonempty.
            k=min(k,1.)
            unit=c/s
            horizontal=P@unit
            p=float(np.linalg.norm(horizontal))
            vertical=abs(float(np.cross(P[0],P[1])@unit))
            pole=k<=vertical+relative_guard
            if pole or p<=relative_guard:
                cap=full
                pole=True
            else:
                ratio=math.sqrt(max(0.,(1-k)*(1+k)))/p
                if not math.isfinite(ratio):
                    raise ValueError('nonfinite cap azimuth extent')
                half=math.asin(min(1.,ratio))
                cap=_arc(math.atan2(horizontal[1],horizontal[0]),half,angular_guard_rad)
    covers=[ellipse,cap]
    if legacy_cover is not None:covers.append(legacy_cover)
    combined=intersect_covers(*covers,angular_guard_rad=angular_guard_rad)
    status='EMPTY_NECESSARY_GEOMETRY' if combined.empty else 'NUMERICAL_OUTER_COVER'
    return SphereDirectionEnvelope(status,combined,ellipse,cap,rho,(lo,hi),r,cap_k,origin,pole,angular_guard_rad)
