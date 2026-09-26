import numpy as np
import pandas as pd
import pytest
from legsa_gins.paper_rebuild.clean5_parity_p04.diagnosis_math import spectrum,bands,phase_bins,consistency,classify
from legsa_gins.paper_rebuild.clean5_parity_p04.diagnosis import exact_indices,trace_velocity


def test_period_acf_known_sine():
    t=np.arange(0,100,.02);x=np.sin(2*np.pi*t/4)
    s,acf,fft=spectrum(t,x)
    assert s['dominant_period_s']==pytest.approx(4,abs=.01)
    assert s['first_acf_zero_s']==pytest.approx(1,abs=.03)
    assert acf.acf.iloc[0]==pytest.approx(1)


def test_bands_covariance_not_omitted():
    t=np.arange(0,40,.05);x=.04*t+np.sin(t)
    b,slow,fast=bands(t,x)
    assert np.allclose(slow+fast,x)
    assert abs(b['variance_closure_error'])<1e-12
    assert b['partial_edge_count']>0
    assert abs(b['sum_variances']-b['total_variance'])>1e-4


def test_phase_sawtooth_and_outside_support():
    t=np.arange(-.5,5.5,.01);x=t%1;p,rows=phase_bins(t,x,np.arange(6))
    assert p['phase_trend_r']>.99
    assert p['outside_complete_update_intervals']>0
    assert len(rows)==10
    assert classify(overconfident=False,phase=p,coupling={},slow_fraction=0,pvt_noise=0)=='UPDATE_SAWTOOTH'


def test_consistency_nonpositive_std_and_priority():
    s=consistency([.2,.4,.1,.3],[.01,.1,0,np.nan])
    assert s['valid_n']==2 and s['nonpositive_std_count']==1 and s['nonfinite_std_count']==1
    assert s['fraction_above_3sigma']==1
    assert classify(overconfident=True,phase={},coupling={'roll':.99},slow_fraction=.99,pvt_noise=2)=='FILTER_OVERCONFIDENT'


def test_exact_matching_and_native_trace_derivative(tmp_path):
    assert exact_indices([1,2,3],[1,3]).tolist()==[0,2]
    with pytest.raises(ValueError):exact_indices([1,2,3],[1.2])
    t=np.array([0,.1,.3,.4,1.]);p=tmp_path/'trace.csv'
    pd.DataFrame({'time':t+100,'lat':39+0*t,'lon':116+0*t,'height':2*t+40}).to_csv(p,index=False)
    tt,v,info=trace_velocity(p,100)
    assert np.allclose(v[:,2],2)
    assert np.allclose(v[:,:2],0,atol=1e-8)
    assert info['independent_velocity_truth'] is False
