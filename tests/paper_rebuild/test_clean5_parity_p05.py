import numpy as np
import pandas as pd
import pytest
from legsa_gins.paper_rebuild.clean5_parity_p05.runtime import patch_noise,grid_cells,GRID
from legsa_gins.paper_rebuild.clean5_parity_p05.evaluation import consistency,directional_endpoints

SOURCE='abstd: [77.8, 77.8, 77.8]\nvrw: [0.077, 0.077, 0.077]\ninitbastd: [77.8, 77.8, 77.8]\narw: [0.985, 0.985, 0.985]\ngbstd: [9.38, 9.38, 9.38]\ninitpos: [1, 2, 3]\n'

def test_noise_patch_keeps_initial_prior_and_other_bytes():
    outputs=[patch_noise(SOURCE,a,v) for a,v in GRID]
    assert outputs[0][0]==SOURCE
    assert len({audit['non_grid_parameter_hash'] for text,audit in outputs})==1
    assert len({audit['actual_parameter_hash'] for text,audit in outputs})==9
    for text,audit in outputs:
        assert text.splitlines()[2:]==SOURCE.splitlines()[2:]
        assert audit['initbastd_unchanged'] and audit['arw_unchanged'] and audit['gbstd_unchanged']
    with pytest.raises(ValueError):patch_noise(SOURCE,77.8,1.)
    with pytest.raises(ValueError):patch_noise(SOURCE+'abstd: [1,1,1]\n',77.8,.077)


def test_grid_rejects_reordering_and_missing_cells():
    cells=[{'cell_id':str(i),'abstd_mGal':a,'vrw_mps_sqrt_hour':v} for i,(a,v) in enumerate(GRID)]
    assert len(grid_cells({'p05':{'cells':cells}}))==9
    with pytest.raises(ValueError):grid_cells({'p05':{'cells':list(reversed(cells))}})
    with pytest.raises(ValueError):grid_cells({'p05':{'cells':cells[:-1]}})


def test_consistency_component_columns_and_epoch_gate():
    errors=pd.DataFrame({'time':[1.,2.],'err_u_m':[6.,12.],'err_n_m':[2.,4.],'err_e_m':[4.,8.],'yaw_err_deg':[-9.,18.]})
    std=np.ones((2,10));std[:,0]=[1,2];std[:,1]=2;std[:,2]=4;std[:,3]=3;std[:,9]=9
    out=consistency(errors,std)
    assert {k:v for k,v in out.items() if k.endswith('_median')}=={'height_abs_error_over_std_median':3.,'north_abs_error_over_std_median':1.5,'east_abs_error_over_std_median':1.5,'yaw_abs_error_over_std_median':1.5}
    std[1,0]+=1e-3
    with pytest.raises(ValueError):consistency(errors,std)


def test_endpoint_report_all_six_without_best_selection():
    rows=[{'abstd_mGal':a,'vrw_mps_sqrt_hour':v,'source_row':str(i),'height_abs_error_over_std_median':i,'up_rmse_m':9-i,'yaw_rmse_deg':i+2} for i,(a,v) in enumerate(GRID)]
    out=directional_endpoints(rows)
    assert len(out)==6
    assert out[0]['from_source_row']=='0' and out[0]['to_source_row']=='6'
    assert out[3]['from_source_row']=='0' and out[3]['to_source_row']=='2'
    with pytest.raises(ValueError):directional_endpoints(rows[:-1])
