"""Temporary synthetic orchestration only; no solver/evaluator execution."""
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from legsa_gins.paper_rebuild.clean5_parity_p05 import evaluation as ev
from legsa_gins.paper_rebuild.clean5_parity_p05.runtime import GRID

@pytest.mark.parametrize('fail_first',[False,True])
def test_all_cells_reported_and_failure_stops_actual_evaluations(tmp_path,monkeypatch,fail_first):
    stage=tmp_path/'stage';stage.mkdir();nav=tmp_path/'nav';std=tmp_path/'std';source=tmp_path/'source'
    a=np.ones((2,11));a[:,1]=[66,67];b=np.ones((2,10));b[:,0]=[66,67]
    np.savetxt(nav,a);np.savetxt(std,b);source.write_text('fixture')
    cells=[{'cell_id':f'N{i:02d}','abstd_mGal':ab,'vrw_mps_sqrt_hour':vr} for i,(ab,vr) in enumerate(GRID)]
    records=[{**c,'run_id':c['cell_id'],'variant_id':c['cell_id'],'method_id':'A04','dataset_id':'BY2','terminal_status':'COMPLETED','nav_path':str(nav),'nav_sha256':ev.sha256_file(nav),'std_path':str(std),'std_sha256':ev.sha256_file(std),'classification':'SENSITIVITY_NOT_FROZEN','explicit_noise_sensitivity':True,'non_grid_parameter_hash':'same','actual_parameter_hash':str(i),'no_best_selection':True,'no_feedback':True,'no_adoption':True,'parameter_sweep':True,'frozen_parameter_contract':False,'parameter_selection_used':False} for i,c in enumerate(cells)]
    pin={'path':str(source),'sha256':ev.sha256_file(source)}
    contract={'p05':{'cells':cells,'evaluator':pin,'trace':pin,'baseline_median_m':.3,'base_time':123,'window_seconds':[66,340]}}
    registry=SimpleNamespace(code_root=tmp_path,raw_root=tmp_path,clean_root=tmp_path)
    monkeypatch.setattr(ev,'EVALUATOR_SHA256',pin['sha256'])
    monkeypatch.setattr(ev,'transform_nav',lambda array,baseline:array)
    monkeypatch.setattr(ev,'write_transformed_nav',lambda before,after,array:np.savetxt(after,array))
    errors=pd.DataFrame({'time':[66.,67.],**{k:[1.,2.] for k in ['err_u_m','err_n_m','err_e_m','yaw_err_deg']}})
    monkeypatch.setattr(ev.canonical,'_read_error_series',lambda path:errors)
    monkeypatch.setattr(ev,'metrics',lambda errors,nav,identity,window,count:{**identity,'evaluation_status':'COMPLETED','horizontal_rmse_m':1.,'position_3d_rmse_m':2.,'up_rmse_m':1.,'yaw_rmse_deg':2.,'yaw_p95_absolute_deg':3.})
    monkeypatch.setattr(ev,'body_frame_bias',lambda errors,nav:{'front_mean_m':1.})
    calls=[]
    def evaluate(**kwargs):
        calls.append(kwargs)
        if fail_first:raise RuntimeError('injected synthetic evaluation failure')
        return {'capture':{'consistency':{'passed':True},'selected_columns':{'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'},'reference_epoch_count':2}}
    monkeypatch.setattr(ev,'evaluate',evaluate)
    result=ev.evaluate_grid(registry=registry,contract=contract,stage_root=stage,records=records,code_commit='synthetic_fixture')
    assert len(result['rows']['v2'])==len(result['rows']['v3'])==9
    assert result['evaluator_invocation_count']==len(calls)==(1 if fail_first else 18)
    assert result['status']==('PARTIAL' if fail_first else 'COMPLETED')
    assert len(list((stage/'07_OFFLINE_EVALUATION').rglob('EVAL_TERMINAL.json')))==18
    if not fail_first:
        assert all(r['consistency_status']=='ORIGINAL_IMU_STD_DIAGNOSTIC_ONLY' and r['yaw_consistency_status']=='UNCHANGED_YAW_STATE_STD' for r in result['rows']['v3'])
        assert all(r['yaw_p95_deg']==3. for r in result['rows']['v2'])
    else:assert all(r['evaluation_status']=='UNAVAILABLE' for rr in result['rows'].values() for r in rr)
