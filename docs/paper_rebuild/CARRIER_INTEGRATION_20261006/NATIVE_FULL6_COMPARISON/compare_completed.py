"""Saved-result comparison only. No production, solver, RAW or evaluator imports."""
import argparse, csv, hashlib, json
from collections import Counter
from pathlib import Path
import numpy as np

OBJECTIVE_RTOL=1e-10
OBJECTIVE_ATOL=1e-10
BASELINE_ATOL_M=1e-10
EXPECTED_STARTS=list(range(100,340,2))

def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def cert(record):return record.get('search',{}).get('certificate',{})
def proven(record):return cert(record).get('global_optimum_certified') is True

def quantiles(values):
    values=np.asarray(values,float)
    if not len(values):return {'n':0,'status':'NO_FINITE_RECORDED_TIME'}
    assert np.isfinite(values).all() and np.all(values>=0)
    out={'n':len(values),'sum_s':float(values.sum()),'mean_s':float(values.mean()),'min_s':float(values.min()),'max_s':float(values.max())}
    for p in (25,50,75,90,95,99):out['p'+str(p)+'_s']=float(np.quantile(values,p/100.))
    for threshold in (.2,1.,2.,5.,10.,30.):out['above_'+str(threshold)+'s']=int(np.count_nonzero(values>threshold))
    return out

def case_map(directory):
    records={}
    for p in sorted((directory/'cases').glob('*.json')):
        record=load(p)
        key=record['case_id']
        if key in records:raise ValueError('duplicate case')
        records[key]=record
    assert len(records)==120
    assert sorted(x['window_start_s'] for x in records.values())==EXPECTED_STARTS
    assert all(x['mode']=='partial' for x in records.values())
    return records

def method_summary(records):
    rows=list(records.values());times=[cert(r)['elapsed_s'] for r in rows if 'elapsed_s' in cert(r)]
    return {'cases':len(rows),'search_called':sum(r['search_called'] for r in rows),
       'certified':sum(proven(r) for r in rows),'certified_fraction':sum(proven(r) for r in rows)/len(rows),
       'experimental_measurements_valid':sum(r['measurement']['valid'] for r in rows),
       'statuses':dict(Counter(r['status'] for r in rows)),
       'termination_reasons':dict(Counter(cert(r).get('termination_reason','NO_SEARCH_RESULT') for r in rows)),
       'backend_labels':dict(Counter(cert(r).get('sphere_backend','legacy_field_absent') for r in rows)),
       'solver_time_recorded':len(times),'solver_time_unavailable':len(rows)-len(times),
       'solver_runtime_s':quantiles(times),'whole_frontend_case_runtime_s':quantiles([r['elapsed_s'] for r in rows]),
       'execution_commits':sorted(set(r['execution_commit'] for r in rows))}

def main(root,output):
    marker=root/'NATIVE_FULL6_COMPLETE.json'
    if not marker.is_file() or load(marker).get('status')!='COMPLETE':
        raise RuntimeError('requires NATIVE_FULL6_COMPLETE.json before reading final population')
    olddir,newdir=root/'PARTIAL6_FRONTEND',root/'NATIVE_FULL6_FRONTEND'
    old,new=case_map(olddir),case_map(newdir)
    if set(old)!=set(new):raise ValueError('different complete case populations')
    old_contract,new_contract=load(olddir/'INPUT_CONTRACT.json'),load(newdir/'INPUT_CONTRACT.json')
    scientific_keys=('model_plan_sha256','family','length_m','partial_policy','nodes','timeout_s','alpha','angular_floor_deg','data_mode','trace_used_online')
    contract_matches={k:old_contract.get(k)==new_contract.get(k) for k in scientific_keys}
    contract_matches['original_likelihood']=old_contract.get('likelihood','original')==new_contract.get('likelihood','original')=='original'
    assert all(contract_matches.values()),contract_matches
    rows=[];failures=[];recovered=[];lost=[];common=[]
    for key in sorted(old):
        a,b=old[key],new[key];ca,cb=cert(a),cert(b)
        item={'case_id':key,'window_start_s':a['window_start_s'],'original_certified':proven(a),'native_certified':proven(b),
              'original_status':a['status'],'native_status':b['status'],'status_equal':a['status']==b['status'],
              'original_termination':ca.get('termination_reason'),'native_termination':cb.get('termination_reason'),
              'original_solver_s':ca.get('elapsed_s'),'native_solver_s':cb.get('elapsed_s'),
              'original_case_wall_s':a['elapsed_s'],'native_case_wall_s':b['elapsed_s'],
              'original_valid':a['measurement']['valid'],'native_valid':b['measurement']['valid'],
              'subset_selection_equal':a.get('subset_selection')==b.get('subset_selection'),
              'all_labels_equal':a.get('search',{}).get('all_labels')==b.get('search',{}).get('all_labels'),
              'pair_full_N_equal':None,'pair_selected_class_equal':None,'pair_objective_close':None,
              'pair_objective_bit_equal':None,'pair_baseline_close':None,'pair_baseline_bit_equal':None,
              'max_objective_abs_difference':None,'max_objective_scaled_difference':None,
              'max_baseline_component_difference_m':None,'frozen_candidates_equal':None,
              'admission_status_equal':a.get('admission',{}).get('status')==b.get('admission',{}).get('status'),
              'measurement_payload_equal':a['measurement']==b['measurement'],'paired_solver_speedup':None,
              'identity_match':a['input_contract']==b['input_contract']==old_contract['model_plan_sha256']}
        if not item['subset_selection_equal'] or not item['identity_match']:failures.append({'case':key,'reason':'selection/input identity mismatch'})
        if proven(a) and proven(b):
            common.append(key)
            full_equal=class_equal=obj_close=obj_exact=base_close=base_exact=True
            max_abs=max_scaled=max_baseline=0.
            labels=a['search']['all_labels']; selected=a['subset_selection']['selected_labels']
            assert labels==b['search']['all_labels']
            indices=[labels.index(s) for s in selected]
            assert tuple(selected)==tuple(ca['distinct_ambiguity_labels'])==tuple(cb['distinct_ambiguity_labels'])
            for rank in ('best','second'):
                left,right=a['search'][rank],b['search'][rank]
                n1,n2=left['ambiguity'],right['ambiguity']
                assert len(n1)==len(n2)==len(labels)
                full_equal &= n1==n2
                class_equal &= [n1[i] for i in indices]==[n2[i] for i in indices]
                for field in ('reduced_cost','full_residual_cost','ambiguity_cost','length_constraint_cost','float_residual_cost'):
                    x,y=float(left[field]),float(right[field]);assert np.isfinite([x,y]).all()
                    diff=abs(x-y);max_abs=max(max_abs,diff);max_scaled=max(max_scaled,diff/max(1.,abs(x)))
                    obj_exact &= x==y
                    obj_close &= bool(np.isclose(x,y,rtol=OBJECTIVE_RTOL,atol=OBJECTIVE_ATOL))
                u,v=np.asarray(left['baselines']),np.asarray(right['baselines'])
                assert u.shape==v.shape==(5,3) and np.isfinite(u).all() and np.isfinite(v).all()
                max_baseline=max(max_baseline,float(np.max(np.abs(u-v))))
                base_exact &= bool(np.array_equal(u,v));base_close &= bool(np.allclose(u,v,rtol=0.,atol=BASELINE_ATOL_M))
            item.update(pair_full_N_equal=full_equal,pair_selected_class_equal=class_equal,
                pair_objective_close=obj_close,pair_objective_bit_equal=obj_exact,pair_baseline_close=base_close,
                pair_baseline_bit_equal=base_exact,max_objective_abs_difference=max_abs,
                max_objective_scaled_difference=max_scaled,max_baseline_component_difference_m=max_baseline,
                frozen_candidates_equal=a['frozen_candidates']==b['frozen_candidates'],
                paired_solver_speedup=ca['elapsed_s']/cb['elapsed_s'])
            checks=('pair_full_N_equal','pair_selected_class_equal','pair_objective_close','pair_baseline_close',
                    'frozen_candidates_equal','status_equal','admission_status_equal','measurement_payload_equal')
            if not all(item[x] for x in checks):failures.append({'case':key,'failed_checks':[x for x in checks if not item[x]]})
        elif proven(b):
            recovered.append({'case_id':key,'window_start_s':a['window_start_s'],
                'original_termination':ca.get('termination_reason'),'native_termination':cb.get('termination_reason'),
                'was_timeout':'TIMEOUT' in ca.get('termination_reason',''),'native_status':b['status'],
                'native_valid':b['measurement']['valid']})
        elif proven(a):lost.append(key)
        rows.append(item)
    common_rows=[r for r in rows if r['original_certified'] and r['native_certified']]
    counts={field:sum(r[field] is True for r in common_rows) for field in (
        'pair_full_N_equal','pair_selected_class_equal','pair_objective_close','pair_objective_bit_equal',
        'pair_baseline_close','pair_baseline_bit_equal','frozen_candidates_equal','status_equal',
        'admission_status_equal','measurement_payload_equal')}
    speed=[r['paired_solver_speedup'] for r in common_rows]
    summary={'schema':'saved_native_full6_comparison.v1','no_new_solver_or_evaluator_calls':True,
      'reference_reads':0,'population':120,'same_input_and_scientific_contract':contract_matches,
      'original':method_summary(old),'native':method_summary(new),'common_certified_cases':len(common),
      'common_certified_match_counts':counts,'newly_certified_cases':recovered,'lost_certification_cases':lost,
      'common_certified_original_solver_runtime_s':quantiles([cert(old[k])['elapsed_s'] for k in common]),
      'common_certified_native_solver_runtime_s':quantiles([cert(new[k])['elapsed_s'] for k in common]),
      'common_certified_paired_speedup':{'n':len(speed),'median':float(np.median(speed)),
         'min':min(speed),'max':max(speed),'p10':float(np.quantile(speed,.1)),'p90':float(np.quantile(speed,.9))},
      'max_common_pair_baseline_difference_m':max(r['max_baseline_component_difference_m'] for r in common_rows),
      'max_common_pair_objective_abs_difference':max(r['max_objective_abs_difference'] for r in common_rows),
      'max_common_pair_objective_scaled_difference':max(r['max_objective_scaled_difference'] for r in common_rows),
      'mismatches':failures,'tolerances':{'objective_rtol':OBJECTIVE_RTOL,'objective_atol':OBJECTIVE_ATOL,'baseline_atol_m':BASELINE_ATOL_M},
      'source_hash_differences':[k for k in sorted(set(old_contract['source_files'])|set(new_contract['source_files']))
         if old_contract['source_files'].get(k)!=new_contract['source_files'].get(k)],
      'receipt':{'completion_sha256':sha(marker),'original_contract_sha256':sha(olddir/'INPUT_CONTRACT.json'),
                 'native_contract_sha256':sha(newdir/'INPUT_CONTRACT.json'),'script_sha256':sha(Path(__file__))},
      'qualification':'global certificate proves registered objective optimum, not correct integers or calibrated FIX',
      'timing_scope':'recorded current complete-run elapsed_s; original includes earlier Python implementation; native includes cache and scalar C++; not a scaled estimate or isolated kernel benchmark'}
    output.mkdir(parents=True,exist_ok=True)
    with (output/'CASE_COMPARISON.csv').open('x') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    with (output/'SUMMARY.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
    a,b=summary['original'],summary['native'];speed=summary['common_certified_paired_speedup']
    lines=['# 完整 120 窗原生后端对比（只读已完成结果）','',
        f"同一输入/科学配置：{all(contract_matches.values())}；完成窗口均为 120。比较脚本未调用 CILS、导航或参考评估。",'',
        '| 项目 | 原 PARTIAL6 Python | NATIVE_FULL6 |','|---|---:|---:|',
        f"| 有全局证书 | {a['certified']}/120 | {b['certified']}/120 |",
        f"| 有效实验测量 | {a['experimental_measurements_valid']} | {b['experimental_measurements_valid']} |"]
    for key,label in [('p50_s','求解耗时中位数 s'),('p90_s','求解耗时 P90 s'),('p95_s','求解耗时 P95 s'),('p99_s','求解耗时 P99 s'),('max_s','求解耗时最大值 s'),('sum_s','求解耗时总和 s')]:
        lines.append(f"| {label}（全部实际调用） | {a['solver_runtime_s'][key]:.6f} | {b['solver_runtime_s'][key]:.6f} |")
    lines+=['',f"共同有证书 {len(common)} 窗：两候选全整数、所选整数类、目标值容差、基线容差、冻结候选、后续状态及测量载荷的通过计数见 SUMMARY.json；实质不一致 {len(failures)} 窗。",
        f"其中目标值逐字段数值完全相等 {counts['pair_objective_bit_equal']} 窗，基线数组完全相等 {counts['pair_baseline_bit_equal']} 窗。最大目标绝对差 {summary['max_common_pair_objective_abs_difference']:.12g}，最大基线分量差 {summary['max_common_pair_baseline_difference_m']:.12g} m。",
        f"共同证书窗的逐窗求解时间比中位数 {speed['median']:.4f}，P10/P90 {speed['p10']:.4f}/{speed['p90']:.4f}。使用实际记录耗时，没有按旧耗时乘加速系数。",'',
        f"新增证书 {len(recovered)} 窗；原证书丢失 {len(lost)} 窗。新增窗逐项保留原终态、是否 timeout、当前验收状态，不以未证书候选冒充等价证书。",
        '']
    for r in recovered:lines.append(f"- {r['case_id']}: {r['original_termination']} → {r['native_termination']}; {r['native_status']}; valid={r['native_valid']}")
    lines+=['','当前对照包含原 Python 到缓存加原生标量内核的整体实现变化，不能把全部收益单独归于 C++。较早 Python 时序不是同时交替重复基准；系统负载波动及超时截断必须保留。',
        '全局证书只针对既定似然目标。整数正确性、风险校准、连续测量覆盖和真实时间融合效果仍需独立证据。','',
        '所有 120 窗见 CASE_COMPARISON.csv；全部状态分布、实际运行分位、源差异与小型身份回执见 SUMMARY.json。']
    (output/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:summary[k] for k in ('common_certified_cases','common_certified_match_counts','newly_certified_cases','lost_certification_cases','mismatches','common_certified_paired_speedup')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.root,a.output)
