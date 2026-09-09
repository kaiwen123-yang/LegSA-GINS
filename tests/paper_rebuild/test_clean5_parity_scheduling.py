import csv
import numpy as np
import pytest
from legsa_gins.paper_rebuild.clean5_parity.scheduling import (
    select_last_nearest,build_scheduling_ledger,audit_scheduling,_provider)


def provider(times, *, eligible=None, static=None, enabled=True):
    return {'enabled':enabled,'solver_enabled':enabled,'times':np.array(times,float),'path':'frozen.csv',
            'tolerance':.25,'eligible':np.ones(len(times),bool) if eligible is None else eligible,
            'static':[True]*len(times) if static is None else static,'rows':[{'time':str(t)} for t in times]}


def test_tie_is_last_file_row_not_earlier_epoch_and_skip_precedes_search():
    assert select_last_nearest([1.25,.75],1.,.25)==1
    assert select_last_nearest([.75,1.25],1.,.25)==1
    assert select_last_nearest([.75,1.,1.25],1.,.25,[True,False,True])==2
    assert select_last_nearest([1.5],1.,.25) is None
    assert select_last_nearest([1.,1.],1.,0)==1


def test_reuse_and_static_reject_are_not_assumed_updates():
    gnss=np.zeros((2,18));gnss[:,0]=[1.,1.125];gnss[:,15:]=1
    native=[{'update_index':str(i),'gnss_time':str(t)} for i,t in enumerate(gnss[:,0])]
    providers={'RD':provider([1.],static=[False]),'RP':provider([1.]),'HV':provider([1.],enabled=False)}
    rows=build_scheduling_ledger(config={},gnss=gnss,native_rows=native,providers=providers)
    assert len(rows)==6
    rd=[r for r in rows if r['module']=='RD'];rp=[r for r in rows if r['module']=='RP']
    assert rd[1]['source_selected_previously'] and rd[1]['previous_selection_same_source']
    assert rd[1]['source_selection_occurrence']==2
    assert rd[0]['final_update_acceptance']=='REJECTED_STATIC_PROVIDER_GATE'
    assert rp[0]['final_update_acceptance']=='UNAVAILABLE_STATE_DEPENDENT'
    assert all(r['selection_status']=='DISABLED_BY_PROFILE' for r in rows if r['module']=='HV')


def test_native_decimal_token_match_is_not_time_search():
    gnss=np.zeros((1,18));gnss[0,0]=1.0000000004;gnss[:,15:]=1
    native=[{'update_index':'0','gnss_time':'1.000000000'}]
    rows=build_scheduling_ledger(config={},gnss=gnss,native_rows=native,providers={'RD':provider([1.])})
    assert rows[0]['update_time']==1.0000000004
    native[0]['gnss_time']='1.000000010'
    with pytest.raises(ValueError,match='no unique'):build_scheduling_ledger(config={},gnss=gnss,native_rows=native,providers={})


def test_disabled_profile_never_opens_provider_and_missing_trace_report(tmp_path):
    p=_provider('RD',{'enable_raw_doppler':False,'raw_doppler_factor_path':str(tmp_path/'missing.csv')})
    assert not p['solver_enabled']
    result=audit_scheduling(config={},output_root=tmp_path/'audit')
    assert result['status']=='UNAVAILABLE_NATIVE_CALL_TRACE'
    assert result['trace_reference_read_count']==result['nav_read_count']==0
    with pytest.raises(FileExistsError):audit_scheduling(config={},output_root=tmp_path/'audit')


def test_hv_loader_filters_update_flag_before_nearest(tmp_path):
    p=tmp_path/'hv.csv'
    with p.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['time','source_status','update_flag','go2_velocity_truth_claim'])
        writer.writeheader();writer.writerows([
            {'time':1.,'source_status':'active','update_flag':'false','go2_velocity_truth_claim':'false'},
            {'time':1.125,'source_status':'active','update_flag':'true','go2_velocity_truth_claim':'false'}])
    parsed=_provider('HV',{'enable_go2_horizontal_velocity_prior':True,'go2_horizontal_velocity_prior_path':str(p),
                          'go2_velocity_prior_time_tolerance_sec':.25})
    assert select_last_nearest(parsed['times'],1.,parsed['tolerance'],parsed['eligible'])==1
