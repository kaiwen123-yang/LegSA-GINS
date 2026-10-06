"""Post-result projected-heading boundary contracts; no real-data solver/eval."""
from dataclasses import dataclass
import math
import numpy as np
import pytest
from legsa_gins.paper_rebuild.horizontal_literature import ext01_clambda as cl
from legsa_gins.paper_rebuild.horizontal_literature import ext03_yang2024 as yang
from legsa_gins.paper_rebuild.horizontal_literature import reproduction_runner as runner
from test_ext_reproduction_runner import setup_problem


@pytest.mark.parametrize('baseline', [
    [0.,0.,0.], [0.,0.,.35], [0.,0.,-.35], [1e-7,0.,1.], [0.,-1e-7,-1.],
])
def test_zero_vertical_and_numerically_singular_projection_has_no_heading(baseline):
    with pytest.raises(ValueError, match='heading'):
        cl.body_yaw_from_ned_baseline(baseline)
    with pytest.raises(yang.Yang2024Error, match='heading'):
        yang.ned_attitude(baseline)


@pytest.mark.parametrize('scale', [1e-150, .01, 1., 1e100])
def test_heading_guard_uses_dimensionless_fraction_not_metres_squared(scale):
    allowed=scale*np.array([1e-5,0.,1.])
    rejected=scale*np.array([1e-7,0.,1.])
    assert cl.body_yaw_from_ned_baseline(allowed)==90.
    assert yang.ned_attitude(allowed).body_yaw_deg==90.
    with pytest.raises(ValueError):cl.body_yaw_from_ned_baseline(rejected)
    with pytest.raises(yang.Yang2024Error):yang.ned_attitude(rejected)


@pytest.mark.parametrize('baseline', [[1.,0.,0.],[0.,1.,.2],[-1.,0.,-.3],[0.,-1.,0.],[.21,.28,.4]])
def test_defined_projection_preserves_existing_signed_convention(baseline):
    beta=math.degrees(math.atan2(baseline[1],baseline[0]))
    old=(beta+90.+180.)%360.-180.
    assert cl.body_yaw_from_ned_baseline(baseline)==old
    result=yang.ned_attitude(baseline)
    assert result.body_yaw_deg==(beta%360.+90.)%360.
    assert result.baseline_heading_deg==beta%360.
    assert result.pitch_deg==-math.degrees(math.atan2(baseline[2],math.hypot(*baseline[:2])))


@pytest.mark.parametrize('baseline', [[float('nan'),0.,1.],[0.,float('inf'),1.],[1.,2.]])
def test_malformed_projection_rejected(baseline):
    with pytest.raises(ValueError):cl.body_yaw_from_ned_baseline(baseline)
    with pytest.raises(yang.Yang2024Error):yang.ned_attitude(baseline)


@dataclass
class Candidate:
    baseline:object
    ambiguity:object
    objective:float=0.

@dataclass
class Certified:
    best:Candidate
    global_optimum_certified:bool=True

@dataclass
class Wrapped:
    baseline_vector_m:object
    integer_ambiguities:tuple=(1,1,1,1)
    objective:float=0.
    diagnostics:tuple=()

@pytest.mark.parametrize('method', ['EXT01','EXT02'])
def test_heading_failure_returns_invalid_null_yaw_but_keeps_solver_evidence(monkeypatch,method):
    setup_problem(monkeypatch)
    monkeypatch.setattr(runner,'_method',method)
    b=np.array([0.,0.,.35])
    monkeypatch.setattr(runner,'_ecef_vector_to_ned',lambda baseline,position:b.copy())
    if method=='EXT01':
        monkeypatch.setattr(cl,'solve_clambda',lambda *a,**k:Certified(Candidate(b,np.ones(4,dtype=int))))
    else:
        from legsa_gins.paper_rebuild.horizontal_literature import reproduction_ext02
        monkeypatch.setattr(reproduction_ext02,'solve_cwls',lambda *a,**k:Wrapped(b))
    output=runner.solve_independent(0)
    assert not output['valid'] and output['solution_state']=='INVALID'
    assert output['body_yaw_deg'] is None
    assert output['failure_code']=='BASELINE_HEADING_UNDEFINED'
    assert output['candidate_returned'] and output['search_complete']
    np.testing.assert_array_equal(output['baseline_ned_m'],b)
    np.testing.assert_array_equal(output['baseline_ecef_m'],b)
    assert output['solver'] is not None and output['epoch_index']==0