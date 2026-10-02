#!/usr/bin/env python3
"""Independent conditional-innovation checks, using only new synthetic snapshots."""
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
def matrix(x):
    return np.asarray(x['data'], float).reshape(x['rows'], x['cols'])
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a, b, atol=1e-9, rtol=1e-8):
    a=np.asarray(a);b=np.asarray(b)  # first argument is recorded, as preregistered.
    return bool(np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and np.all(np.abs(a-b)<=atol+rtol*np.abs(a)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',type=Path,required=True);a=p.parse_args()
    roots=json.loads(a.roots.read_text())['aliases'];root=Path(roots['<VALIDATION_BUILD_ROOT>'])
    tests=root/'N12_tests_v1'; rows=[]; summaries={}
    names={'dx_zero','dz_equals_Hdx','sequential_general','correlated_S','fallback_no_S','sa_off','two_sequential_SA','yaw_hard_gate','rd_saoff_gate'}
    for v in ['candidate','baseline']:
        assert {x.name for x in (tests/v).iterdir()}==names, 'missing/extra scenario: '+v
    for case in sorted((tests/'candidate').iterdir()):
        name=case.name
        events={v:[json.loads(l) for l in (tests/v/name/'observer/events.jsonl').open()] for v in ['baseline','candidate']}
        states={v:json.loads((tests/v/name/'SCIENTIFIC_STATE.json').read_text()) for v in events}
        sa={v:[e['data']['snapshot'] for e in events[v] if e['event']=='SA_EVALUATION'] for v in events}
        def check(key, passed, detail=''):
            rows.append(dict(scenario=name,check=key,passed=bool(passed),detail=detail))
        expected_sa=0 if name in ['yaw_hard_gate','rd_saoff_gate'] else 2 if name=='two_sequential_SA' else 1
        for v in ['candidate','baseline']:
            es=events[v]
            check(v+'_continuous_event_seq',[e['event_seq'] for e in es]==list(range(1,len(es)+1)))
            check(v+'_expected_SA_count',len(sa[v])==expected_sa)
            check(v+'_ends_after_feedback',any(e['event']=='FEEDBACK_AFTER' for e in es[-3:]))
            check(v+'_log_complete',es[0]['event']=='OBSERVER_BEGIN' and es[-1]['event']=='OBSERVER_END')
        prev_p=None;last_sa=None; sa_count=0;paired_after=0;paired_before=0
        for event in events['candidate']:
            typ=event['event'];s=event['data'].get('snapshot')
            if s is None:continue  # configuration/initialization have no event snapshot.
            if typ=='EKF_AFTER':
                prev_p=matrix(s['P_after'])
                if last_sa is not None:
                    paired_after+=1
                    h=matrix(last_sa['H']);nu=np.asarray(last_sa['dz'])-h@np.asarray(last_sa['dx_before'])
                    check('EKF_uses_conditional_once_'+str(sa_count),close(s['actual_innovation'],nu))
                    last_sa=None
            if typ=='SA_EVALUATION':
                sa_count+=1;h=matrix(s['H']);cov=matrix(s['P_before']);r=matrix(s['base_R'])
                raw=np.asarray(s['dz']);nu=raw-h@np.asarray(s['dx_before']);S=h@cov@h.T+r;i=s['innovation']
                check('conditional_vector_'+str(sa_count),close(i['residual_vector'],nu))
                check('conditional_norm_'+str(sa_count),close(i['residual_norm'],np.linalg.norm(nu)))
                check('metadata_keeps_raw_norm_'+str(sa_count),close(s['metadata']['residual_norm'],np.linalg.norm(raw)))
                check('dof_unchanged_'+str(sa_count),i['dof']==len(raw))
                if prev_p is not None:check('sequential_P_stage_'+str(sa_count),np.array_equal(cov,prev_p))
                if i['used_innovation_covariance']:
                    nis=max(0.,float(nu@np.linalg.solve(S,nu)))
                    check('same_snapshot_NIS_'+str(sa_count),close(i['nis'],nis),repr(nis))
                    check('normalization_'+str(sa_count),close(i['normalized_innovation'],np.sqrt(nis/len(raw))))
                else:
                    expected=np.linalg.norm(nu)/np.sqrt(max(1e-12,np.trace(S)))
                    check('fallback_conditional_norm_'+str(sa_count),close(i['normalized_innovation'],expected))
                last_sa=s
            if typ=='EKF_BEFORE' and last_sa is not None:
                paired_before+=1
                check('EKF_receives_raw_dz_'+str(sa_count),s['dz']==last_sa['dz'])
                check('same_event_P_'+str(sa_count),s['P_before']==last_sa['P_before'])
        check('all_SA_EKF_pairings',paired_before==expected_sa and paired_after==expected_sa and last_sa is None)
        if name in ['dx_zero','sa_off','yaw_hard_gate','rd_saoff_gate']:
            check('scientific_state_baseline_exact',states['candidate']==states['baseline'])
        if name=='dz_equals_Hdx':
            check('zero_conditional_NIS_positive_old_NIS',sa['candidate'][0]['innovation']['nis']==0 and sa['baseline'][0]['innovation']['nis']>0)
        if name=='correlated_S':
            s=sa['candidate'][0];h=matrix(s['H']);S=h@matrix(s['P_before'])@h.T+matrix(s['base_R'])
            check('full_non_diagonal_S_tested',np.any(S-np.diag(np.diag(S))))
        if name in ['yaw_hard_gate','rd_saoff_gate']:
            check('yaw_hard_gate_not_replaced',states['candidate']['yaw_reject']==1 and states['candidate']['yaw_attempt']==1)
            check('no_SA_bypass_of_hard_gate',len(sa['candidate'])==0)
        if name=='rd_saoff_gate':check('RD_SAoff_gate_retained',states['candidate']['RD']==0 and states['candidate']['RD_reject']==1)
        summaries[name]={'SA_events':len(sa['candidate']),'state_exact':states['candidate']==states['baseline'],
            'NIS_baseline':[s['innovation']['nis'] for s in sa['baseline']],
            'NIS_candidate':[s['innovation']['nis'] for s in sa['candidate']],
            'R_scale_baseline':[s['result']['combined_R_scale'] for s in sa['baseline']],
            'R_scale_candidate':[s['result']['combined_R_scale'] for s in sa['candidate']]}
    with (HERE/'TEST_RESULTS.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
    passed=all(x['passed'] for x in rows)
    receipt={'candidate_id':'N12_ONLY','data_mode':'synthetic_fixture_only','synthetic_data_used':True,'semisynthetic_data_used':False,
        'new_native_fixture_processes':2,'scenarios_per_process':9,'real_native_calls':0,'evaluator_calls':0,
        'checks':len(rows),'all_passed':passed,'NIS_tolerance':'1e-9 + 1e-8 * abs(recorded)',
        'new_validation_calculation':True,'fixture_source_sha256':sha(HERE/'fixture.cpp'),'validator_sha256':sha(Path(__file__)),
        'output_root':'<VALIDATION_BUILD_ROOT>/N12_tests_v1','scenarios':summaries}
    (HERE/'TEST_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'checks':len(rows),'passed':passed,'failures':[x for x in rows if not x['passed']]}))
    if not passed:raise SystemExit(1)
if __name__=='__main__':main()
