"""Read completed saved acquisitions only; zero solver / evaluator / raw reads."""
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def certified(record):return record.get('search',{}).get('certificate',{}).get('global_optimum_certified') is True

def records(folder):
    result={}
    for path in sorted((folder/'cases').glob('*.json')):
        r=read(path);key=r['case_id']
        if key in result:raise ValueError('duplicate case ID')
        result[key]=r
    return result

def numeric_pair(a,b):
    fields=('reduced_cost','full_residual_cost','ambiguity_cost','length_constraint_cost','float_residual_cost')
    answer={'both_N_equal':True,'both_objectives_close':True,'both_baselines_close':True,
            'max_objective_abs_diff':0.,'max_objective_scaled_diff':0.,'max_baseline_component_diff_m':0.}
    for name in ('best','second'):
        x,y=a['search'][name],b['search'][name]
        answer['both_N_equal'] &= x['ambiguity']==y['ambiguity']
        for key in fields:
            v,w=float(x[key]),float(y[key]);assert np.isfinite([v,w]).all()
            difference=abs(v-w)
            answer['max_objective_abs_diff']=max(answer['max_objective_abs_diff'],difference)
            answer['max_objective_scaled_diff']=max(answer['max_objective_scaled_diff'],difference/max(1.,abs(v)))
            answer['both_objectives_close'] &= bool(np.isclose(v,w,rtol=1e-10,atol=1e-10))
        v,w=np.asarray(x['baselines']),np.asarray(y['baselines'])
        assert v.shape==w.shape==(5,3) and np.isfinite(v).all() and np.isfinite(w).all()
        answer['max_baseline_component_diff_m']=max(answer['max_baseline_component_diff_m'],float(np.max(abs(v-w))))
        answer['both_baselines_close'] &= bool(np.allclose(v,w,atol=1e-10,rtol=0.))
    return answer

def population(rows):
    values=list(rows.values());times=[]
    for r in values:
        c=r.get('search',{}).get('certificate',{})
        if 'elapsed_s' in c:
            t=c['elapsed_s'];assert np.isfinite(t) and t>=0;times.append(t)
    return {'opportunities':len(values),'actual_searches':sum(x['search_called'] for x in values),
        'presearch_unavailable':sum(x.get('presearch_unavailable',False) for x in values),
        'certified':sum(certified(x) for x in values),'valid_acquisition_measurements':sum(x['measurement']['valid'] for x in values),
        'statuses':dict(Counter(x['status'] for x in values)),
        'solver_times_recorded':len(times),
        'solver_runtime_quantiles_s':{str(p):float(np.quantile(times,p/100.)) for p in (0,50,90,95,99,100)} if times else {},
        'execution_commits':sorted(set(x['execution_commit'] for x in values))}

def main(a):
    if not a.completion.is_file() or read(a.completion).get('status')!='COMPLETE':
        raise RuntimeError('completed dense frontend/tracking/serial marker required')
    old,new=records(a.original),records(a.dense)
    assert len(old)==120 and len(new)==1191
    assert sorted(x['window_start_s'] for x in old.values())==list(range(100,340,2))
    assert sorted(x['window_start_s'] for x in new.values())==[round(100+i/5,2) for i in range(1191)]
    assert set(old)<=set(new)
    ca,cb=read(a.original/'INPUT_CONTRACT.json'),read(a.dense/'INPUT_CONTRACT.json')
    keys=('model_plan_sha256','family','length_m','partial_policy','nodes','timeout_s','alpha','angular_floor_deg','data_mode','trace_used_online','likelihood')
    matches={k:ca.get(k)==cb.get(k) for k in keys}
    assert all(matches.values()) and cb['likelihood']=='selected-support'
    rows=[];differences=[]
    for key,x in sorted(old.items()):
        y=new[key];sx=x.get('search',{});sy=y.get('search',{})
        row={'case_id':key,'window_start_s':x['window_start_s'],
            'original_certified':certified(x),'dense_certified':certified(y),
            'selection_equal':x.get('subset_selection')==y.get('subset_selection'),
            'support_equal':x.get('selection_support')==y.get('selection_support'),
            'reduced_plan_fingerprint_equal':x.get('selected_likelihood_plan_fingerprint')==y.get('selected_likelihood_plan_fingerprint'),
            'search_labels_equal':sx.get('all_labels')==sy.get('all_labels'),
            'status_equal':x['status']==y['status'],'original_status':x['status'],'dense_status':y['status'],
            'valid_equal':x['measurement']['valid']==y['measurement']['valid'],
            'frozen_candidates_equal':x.get('frozen_candidates')==y.get('frozen_candidates'),
            'admission_status_equal':x.get('admission',{}).get('status')==y.get('admission',{}).get('status'),
            'measurement_equal':x['measurement']==y['measurement'],
            'original_solver_s':sx.get('certificate',{}).get('elapsed_s'),
            'dense_solver_s':sy.get('certificate',{}).get('elapsed_s'),
            'both_N_equal':None,'both_objectives_close':None,'both_baselines_close':None,
            'max_objective_abs_diff':None,'max_objective_scaled_diff':None,'max_baseline_component_diff_m':None}
        if certified(x) and certified(y):row.update(numeric_pair(x,y))
        # Preserve all disagreements, including unresolved/certificate outcomes;
        # do not silently treat a recovered timeout as numerical equivalence.
        checks=['selection_equal','support_equal','reduced_plan_fingerprint_equal','search_labels_equal',
                'status_equal','valid_equal','frozen_candidates_equal','admission_status_equal','measurement_equal']
        failed=[k for k in checks if not row[k]]
        if certified(x)!=certified(y):failed.append('certification_changed')
        if certified(x) and certified(y):failed += [k for k in ('both_N_equal','both_objectives_close','both_baselines_close') if not row[k]]
        if failed:differences.append({'case_id':key,'failed_checks':failed})
        rows.append(row)
    both=[r for r in rows if r['original_certified'] and r['dense_certified']]
    summary={'scope':'saved common120 acquisition equivalence only; dense tracking ownership intentionally differs',
        'scientific_contract_matches':matches,'common_start_count':120,'both_certified_count':len(both),
        'original':population(old),'dense_total':population(new),'dense_common120':population({k:new[k] for k in old}),
        'match_counts':{k:sum(r[k] is True for r in rows) for k in ('selection_equal','support_equal','reduced_plan_fingerprint_equal',
            'search_labels_equal','status_equal','valid_equal','frozen_candidates_equal','admission_status_equal','measurement_equal')},
        'common_certified_match_counts':{k:sum(r[k] is True for r in both) for k in ('both_N_equal','both_objectives_close','both_baselines_close')},
        'maximum_objective_abs_diff':max((r['max_objective_abs_diff'] for r in both),default=None),
        'maximum_baseline_component_diff_m':max((r['max_baseline_component_diff_m'] for r in both),default=None),
        'differences':differences,'solver_calls':0,'evaluator_calls':0,'raw_or_reference_reads':0,
        'tolerances':{'objective_atol':1e-10,'objective_rtol':1e-10,'baseline_atol_m':1e-10},
        'receipts':{'completion_sha256':sha(a.completion),'original_contract_sha256':sha(a.original/'INPUT_CONTRACT.json'),
                    'dense_contract_sha256':sha(a.dense/'INPUT_CONTRACT.json'),'script_sha256':sha(Path(__file__))},
        'timing_boundary':'Original is selected-support Python; dense uses native sphere and different opportunity cadence. Acquisitions are independently solved; timings are recorded actual durations, not an isolated randomized speed comparison.'}
    a.output.mkdir(parents=True,exist_ok=False)
    with (a.output/'COMMON120.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    (a.output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    (a.output/'SUMMARY.md').write_text('# Dense acquisition common120只读等价核对\n\n'
        +f"共同起点120；共同取得证书{len(both)}；记录到不一致{len(differences)}窗。\n\n"
        +'候选、目标、基线、reduced plan指纹、前5选择和后5验收及测量身份逐窗见COMMON120.csv。\n\n'
        +'本核对只涉及独立acquisition；密集机会会改变tracking/serial owner，不要求整条owner状态与2秒机会相同。所有1191窗保留2秒数据支持，未缩为单历元。\n\n'
        +'运行分位来自实际保存字段。未运行求解、验收或参考评估；全局证书与同值仍不证明实测整数真值。\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('original','dense','completion','output'):p.add_argument('--'+key,type=Path,required=True)
    main(p.parse_args())
