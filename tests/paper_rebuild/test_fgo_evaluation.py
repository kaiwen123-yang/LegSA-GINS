"""Only new FGO output/point/support adaptation; no real reference access."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.fgo_comparison.evaluation import reference_at, score_method, common_time_rows


def model():
    def xyz(lat,lon,h):
        a,b=np.deg2rad(lat),np.deg2rad(lon);n=6378137/np.sqrt(1-6.6943799901413165e-3*np.sin(a)**2)
        return ((n+h)*np.cos(a)*np.cos(b),(n+h)*np.cos(a)*np.sin(b),(n*(1-6.6943799901413165e-3)+h)*np.sin(a))
    return SimpleNamespace(lla_to_ecef=xyz,wrap_deg=lambda x:(x+180)%360-180)


def fixture():
    gt=pd.DataFrame({'time':[65.,69.],'lat':[0.,0.],'lon':[0.,0.],'alt':[0.,0.],
                     'roll':[0.,0.],'pitch':[0.,0.],'yaw':[90.,90.]})
    spec={'window_seconds':[66,68],'baseline_median_m':.4,'dataset_id':'SYNTHETIC','base_time':0}
    run={'terminal_status':'COMPLETED','solver_and_adapter_elapsed_s':0,'mode':'SYNTHETIC'}
    return gt,spec,run


def test_reference_midpoint_to_gnss1_fixed_frd_sign():
    gt,_,_=fixture()
    _,_,xyz=reference_at(model(),gt,np.array([66.]),.4,'GNSS1_ANTENNA')
    np.testing.assert_allclose(xyz,[[6378137,.2,0]],atol=1e-12)
    gt['yaw']=0. # ENU east -> NED 90: right is south
    _,_,xyz=reference_at(model(),gt,np.array([66.]),.4,'GNSS1_ANTENNA')
    np.testing.assert_allclose(xyz,[[6378137,0,-.2]],atol=1e-12)


def test_position_only_missing_epoch_has_no_fabricated_attitude_or_zero_error():
    gt,spec,run=fixture()
    states=pd.DataFrame({'time_rel_s':[66.,67.,68.],'x_ecef_m':[6378137,np.nan,6378137],
                         'y_ecef_m':[.2,np.nan,.2],'z_ecef_m':[0.,np.nan,0.],
                         'valid':[1,0,1],'status':['OK','MISSING','OK']})
    row,error,_=score_method(model(),gt,states,spec,'GNC',run)
    assert row['expected_epoch_count']==3 and row['matched_epoch_count']==2
    assert row['coverage_fraction']==2/3 and row['missing_or_invalid_count']==1
    assert row['horizontal_rmse_m']==0 and 'yaw_rmse_deg' not in row
    assert np.isnan(error.loc[1,'horizontal_err_m'])


def test_no_output_retains_denominator_and_empty_common_support():
    gt,spec,run=fixture()
    states=pd.DataFrame(columns=['time_rel_s','x_ecef_m','y_ecef_m','z_ecef_m','valid','status'])
    row,error,_=score_method(model(),gt,states,spec,'GNC',{**run,'terminal_status':'FAILED_EXCEPTION'})
    assert row['expected_epoch_count']==3 and row['matched_epoch_count']==0
    assert row['horizontal_rmse_m'] is None and row['maximum_gap_with_window_edges_s']==2
    common=common_time_rows([row],{'GNC':error})
    assert common[0]['matched_epoch_count']==0 and common[0]['position_3d_rmse_m'] is None


def test_duplicate_epoch_rejected_and_common_time_range_is_recomputed():
    gt,spec,run=fixture()
    states=pd.DataFrame({'time_rel_s':[66.,67.,68.],'x_ecef_m':[6378137]*3,
                         'y_ecef_m':[.2]*3,'z_ecef_m':[0.]*3,'valid':[1]*3,'status':['OK']*3})
    row,error,_=score_method(model(),gt,states,spec,'GNC',run)
    bad=pd.concat([states,states.iloc[[1]]]).sort_values('time_rel_s')
    with pytest.raises(ValueError): score_method(model(),gt,bad,spec,'GNC',run)
    other=error.copy();other.loc[[0,2],'valid']=0
    common=common_time_rows([row,{**row,'method_id':'WEN_TC'}],{'GNC':error,'WEN_TC':other})
    assert all(x['first_output_s']==67 and x['last_output_s']==67 for x in common)
