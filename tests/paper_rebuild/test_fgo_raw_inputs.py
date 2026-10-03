"""Scientific signs/units for the new undifferenced input adapter."""
import numpy as np
import pytest
from legsa_gins.paper_rebuild.fgo_comparison.raw_inputs import (
    C, OMEGA, code_sigma, doppler_wls, solve_code_wls,
    bootstrap_code, raw,
)


def geometry():
    p=np.array([-2178000.,4387000.,4078000.])
    directions=np.array([[1,1,1],[1,-1,1],[-1,1,1],[-1,-1,1],[1,0,-1],[0,1,-1],[0,-1,-1],[1,2,3]],float)
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    return p,p+directions*2.1e7


def test_code_wls_recovers_two_independent_clocks_without_prior():
    p,sat=geometry();system=np.array([0,0,0,0,1,1,1,1])
    clock=np.array([599584.916,599620.123])
    code=np.linalg.norm(sat-p,axis=1)+clock[system]
    out=solve_code_wls(sat,code,np.linspace(1,3,8),system,p+[100,-300,200])
    np.testing.assert_allclose(out[0],p,atol=2e-8,rtol=0)
    np.testing.assert_allclose(out[1],clock,atol=2e-8,rtol=0)


def test_rawx_doppler_negative_range_rate_with_satellite_clock_and_earth_rate():
    p,sat=geometry();v=np.array([1.2,-.4,.05]);drift=7.2
    sv=np.arange(24,dtype=float).reshape(8,3)*100-1100
    dts=np.linspace(-1e-10,2e-10,8);freq=np.full(8,1575.42e6)
    u=(sat-p)/np.linalg.norm(sat-p,axis=1)[:,None]
    rate=np.sum(u*(sv-v),axis=1)+OMEGA/C*(sv[:,1]*p[0]+sat[:,1]*v[0]-sat[:,0]*v[1]-sv[:,0]*p[1])+drift-C*dts
    raw_d=-rate*freq/C
    out=doppler_wls(sat,sv,dts,freq,raw_d,np.full(8,.1),p)
    np.testing.assert_allclose(out[0],v,atol=1e-9,rtol=0)
    np.testing.assert_allclose(out[2],drift,atol=1e-9,rtol=0)
    assert np.linalg.eigvalsh(out[1]).min()>0


def test_code_cofactor_has_correct_noise_direction_and_clock_rank_failure():
    pars={'T':45,'A':30,'a':30,'F':10}
    assert code_sigma(np.deg2rad(10),30,pars)>code_sigma(np.deg2rad(80),30,pars)
    assert code_sigma(np.deg2rad(45),20,pars)>code_sigma(np.deg2rad(45),45,pars)
    p,sat=geometry()
    assert solve_code_wls(sat[:3],np.full(3,2e7),np.ones(3),np.zeros(3,int),p) is None


def test_bootstrap_expected_missing_observations_are_distinct_from_abi_error():
    class Stub:
        def __init__(self, message): self.message=message
        def pntpos_rawx_epoch(self,*args): raise raw.PntPosBridgeError(self.message,-1)
    assert bootstrap_code(Stub('PNTPOS_NO_SUPPORTED_RAW_MEASUREMENTS'),None,{}) is None
    with pytest.raises(raw.PntPosBridgeError): bootstrap_code(Stub('ABI_MISMATCH'),None,{})
