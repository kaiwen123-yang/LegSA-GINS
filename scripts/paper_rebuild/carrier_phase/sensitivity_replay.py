#!/usr/bin/env python3
"""Geometry/working-Q sensitivity on saved frozen-integer shadow windows."""
from pathlib import Path
from dataclasses import asdict
import argparse,csv,json,os
from collections import Counter
from shadow_replay import load_model
from real_trial import revision,source_snapshot,digest,emit
from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs
from legsa_gins.paper_rebuild.carrier_phase.faults import build_phase_fault_map,stack_phase_fault_maps,fixed_integer_gls
from legsa_gins.paper_rebuild.carrier_phase.sensitivity import analyze_phase_fault_sensitivity

def run(args):
    args.output.mkdir(parents=True,exist_ok=False)
    saved=json.loads(args.results.read_text())
    plan=json.loads((args.trial/'PLAN.json').read_text())
    cases=[];rows=[]
    for record in saved['records']:
        result={'case_id':record['case_id'],'original_admission_status':record['status'],
                'status':'UNAVAILABLE','does_not_change_admission':True}
        try:
            times=record['decision']['observed_future_times']
            selected=[row for row in plan['records'] if row['time_s'] in times]
            if len(selected)!=len(times):raise ValueError('SAVED_FUTURE_TIMES_NOT_FOUND')
            models=[load_model(args.trial,row,record['family_requested']) for row in selected]
            problem=assemble_epochs(models,length_m=plan['baseline_length_m'])
            source=record['selection']
            if len(source['ambiguity_labels'])!=len(source['best']['ambiguity']):
                raise ValueError('CANDIDATE_DIMENSION_MISMATCH')
            integers=dict(zip(source['ambiguity_labels'],source['best']['ambiguity']))
            fit=fixed_integer_gls(problem,integers)
            fault_map=stack_phase_fault_maps([build_phase_fault_map(m) for m in models],persistent=True)
            analysis=analyze_phase_fault_sensitivity(fit,fault_map,family_alpha=.01,miss_probability=.05)
            result.update(status='DIAGNOSTIC_ONLY',analysis=asdict(analysis))
            for item in analysis.scores:
                rows.append({'case_id':record['case_id'],'family':record['family_requested'],
                  'original_admission_status':record['status'],'signal_arc_key':item.key,
                  'sensitivity_status':item.status,'information_cycles_inverse2':item.information_cycles_inverse2,
                  'mdb_cycles':item.mdb_cycles,'mdb_max_epoch_bias_norm_m':item.mdb_max_epoch_bias_norm_m,
                  'mdb_joint_bias_norm_m':item.mdb_joint_bias_norm_m,'family_hypotheses':analysis.family_hypotheses,
                  'unbounded':item.detectable_amplitude_unbounded,'alias_count':len(item.observational_aliases)})
        except (ValueError,KeyError) as ex:
            result['reason']=type(ex).__name__+':'+str(ex)
        emit(args.output/(record['case_id']+'.json'),result);cases.append(result)
    pins=source_snapshot(args.code)
    pins[str(Path(__file__).relative_to(args.code))]=digest(Path(__file__))
    emit(args.output/'RESULTS.json',{'execution_commit':revision(args.code),'source_sha256':pins,
      'saved_admission_sha256':digest(args.results),'plan_sha256':digest(args.trial/'PLAN.json'),
      'new_solver_calls':0,'threshold_changes':0,'integer_truth_reads':0,'records':cases,
      'counts':dict(Counter(c['status'] for c in cases)),
      'scope':'reused geometry and working-Q sensitivity; no validated error bound or false-fix probability'})
    if rows:
        with (args.output/'SENSITIVITY.csv').open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
    print(json.dumps({'cases':len(cases),'physical_fault_profiles':len(rows),'counts':dict(Counter(c['status'] for c in cases))}))

def main():
    parser=argparse.ArgumentParser()
    for name in ('trial','results','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--code',type=Path,default=Path(__file__).resolve().parents[3])
    args=parser.parse_args()
    if os.uname().sysname!='Linux':raise RuntimeError('run algorithms in Ubuntu WSL')
    run(args)
if __name__=='__main__':main()
