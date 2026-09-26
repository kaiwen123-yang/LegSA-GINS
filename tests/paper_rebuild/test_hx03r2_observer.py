"""Residual recording tests using arrays only, without any reference file."""
import sys

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.hext.hx03r2_observer import observe_arrays


def frames():
    nav = pd.DataFrame({'time': [0., .1, .2], 'lat': [30., 30., 30.],
        'lon': [110., 110., 110.], 'alt': [100., 100., 100.],
        'roll': [0., 0., 0.], 'pitch': [0., 0., 0.], 'yaw': [70., 70., 70.]})
    ref = nav.copy()
    ref['yaw'] = 20.
    errors = pd.DataFrame({'time': nav.time, 'err_e_m': 0., 'err_n_m': 0.,
        'err_u_m': 0., 'yaw_err_deg': 0., 'horizontal_err_m': 0.})
    return nav, errors, ref


def test_unchanged_observer_return_and_recorded_arrays_agree():
    nav, errors, ref = frames()
    before = [x.copy(deep=True) for x in (nav, errors, ref)]
    result, residuals, extrema, metrics = observe_arrays(nav, errors, ref)
    assert result['passed'] and result['horizontal_max_m'] <= 1e-9
    assert (residuals[['horizontal_vector_discrepancy_m', 'up_difference_m', 'yaw_difference_deg']] == 0).all().all()
    assert extrema['horizontal']['time_s'] == 0.
    assert metrics['horizontal_rmse_m'] == metrics['yaw_rmse_deg'] == 0.
    for a,b in zip((nav,errors,ref),before):
        pd.testing.assert_frame_equal(a,b)
    assert sys.getprofile() is None


def test_recorded_vector_residual_sign_argmax_and_original_gate():
    nav, errors, ref = frames()
    errors.loc[1, ['err_e_m','err_n_m','err_u_m','yaw_err_deg','horizontal_err_m']] = [3.,4.,2.,5.,5.]
    result, residuals, extrema, metrics = observe_arrays(nav, errors, ref)
    assert not result['passed'] and result['position_threshold_m'] == .01
    assert result['horizontal_max_m'] == 5.
    assert result['up_max_m'] == 2. and result['yaw_max_deg'] == 5.
    assert residuals.loc[1, 'horizontal_magnitude_difference_m'] == -5.
    assert residuals.loc[1, 'east_difference_m'] == -3.
    assert residuals.loc[1, 'up_difference_m'] == -2.
    assert residuals.loc[1, 'yaw_difference_deg'] == -5.
    assert all(x['index_zero_based']==1 and x['time_s']==.1 for x in extrema.values())
    assert metrics['horizontal_rmse_m']==0.


def test_original_epoch_identity_gate_still_rejects_misalignment():
    nav, errors, ref = frames()
    errors.loc[1, 'time'] += .001
    with pytest.raises(ValueError, match='Error epochs differ'):
        observe_arrays(nav, errors, ref)
    assert sys.getprofile() is None
