"""Meaningful boundary tests; synthetic data never enters real-data products."""
import numpy as np
import pytest
from legsa_gins.paper_rebuild.hext.readonly_closeout import associate_omega, region_masks, yaw_metrics


def test_occlusion_closed_endpoints_and_exact_complement():
    times=np.array([3185.99,3186,3369.939,3369.94,3411.95,3411.951,3495.94,3508.94,3508.941,3563,3563.01])
    masks=region_masks(times,'BY2O',(3186,3563))
    assert np.flatnonzero(masks['inside_union']).tolist()==[3,4,6,7]
    assert np.flatnonzero(masks['outside']).tolist()==[1,2,5,8,9]
    assert np.array_equal(masks['inside_union']|masks['outside'],masks['full'])
    assert not (masks['inside_union']&masks['outside']).any()


def test_controls_do_not_invent_occlusion():
    masks=region_masks([65,66,100,340,341],'BY2',(66,340))
    assert 'inside_union' not in masks
    assert np.array_equal(masks['full'],masks['outside'])


def test_increment_interval_association_preserves_gap_unknown():
    imu=np.zeros((4,7));imu[:,0]=[0,.01,.02,.5];imu[:,3]=np.deg2rad([0,.04,.06,99])
    omega,valid=associate_omega(imu,[-.01,0,.001,.01,.015,.02,.03,.5,.501])
    assert valid.tolist()==[False,False,True,True,True,True,False,False,False]
    np.testing.assert_allclose(omega[valid],[4,4,6,6])
    assert np.isnan(omega[~valid]).all()


def test_absolute_median_not_signed_median_and_no_nonfinite_deletion():
    values=yaw_metrics([-9,-1,1,3])
    assert values['yaw_median_absolute_deg']==2
    assert values['yaw_rmse_deg']==pytest.approx(np.sqrt(23))
    with pytest.raises(ValueError):yaw_metrics([1,np.nan])
    assert yaw_metrics([])['yaw_rmse_deg']=='UNAVAILABLE'
