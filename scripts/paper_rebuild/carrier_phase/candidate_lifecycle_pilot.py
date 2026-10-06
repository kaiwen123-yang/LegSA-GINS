#!/usr/bin/env python3
"""Registered 12-source x 5-current-slot lifecycle diagnostic; never searches N."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict,is_dataclass
import csv,gzip,hashlib,json,math,os
from pathlib import Path
import subprocess,sys,time,traceback
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
from legsa_gins.paper_rebuild.carrier_phase.candidate_lifecycle import (
    CompleteSourceSet,ConditionalCandidateSet,LifecycleConfig,LifecycleCalls)
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import ecef_to_geodetic
from trusted_heading_projected_fixed_n import load_model
from trusted_heading_arc_support_audit import physical_failures

PLAN_REL='docs/paper_rebuild/TRUSTED_HEADING_20261006/CANDIDATE_LIFECYCLE_PILOT_PLAN.json'
SCRIPT_REL='scripts/paper_rebuild/carrier_phase/candidate_lifecycle_pilot.py'
FAMILY='GPS_GAL_BDS_DUAL'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def clean(value):
    if is_dataclass(value):return clean(asdict(value))
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):
        raise ValueError('nonfinite lifecycle result must not be silently serialized')
    return value


def emit(path,value):
    Path(path).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def require(condition,reason):
    if not condition:raise RuntimeError(reason)


def check_file(path,expected):
    require(isinstance(expected,str) and len(expected)==64,'missing SHA256: '+str(path))
    require(digest(path)==expected,'SHA256 mismatch: '+str(path))


def check_registration(commit,plan):
    require(len(commit)==40 and all(c in '0123456789abcdef' for c in commit),'full frozen commit required')
    for rel in (PLAN_REL,SCRIPT_REL):
        require(subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)==(ROOT/rel).read_bytes(),
                'registered bytes differ: '+rel)
    require(bool(plan['source_pins']),'source pins absent')
    for rel,sha in plan['source_pins'].items():
        path=(ROOT/rel).resolve();require(path.is_relative_to(ROOT),'source pin outside repo')
        check_file(path,sha)
        require(hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)).hexdigest()==sha,
                'source not in registration commit: '+rel)
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        require(os.environ.get(name)=='1','explicit single thread environment required: '+name)


def axes(anchor):
    lat,lon,_=ecef_to_geodetic(anchor)
    return np.array([[-math.sin(lat)*math.cos(lon),-math.sin(lat)*math.sin(lon),math.cos(lat)],
                     [-math.sin(lon),math.cos(lon),0.]])


def write_csv(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def run(args):
    plan=json.loads((ROOT/PLAN_REL).read_text());check_registration(args.registration_commit,plan)
    source=Path(args.source).resolve();prepared=Path(args.prepared).resolve()
    audit_path=Path(args.input_audit).resolve();out=Path(args.output).resolve()
    require(not out.exists(),'new output required; no resume or retry')
    input_paths={str(source/'DETAILS.jsonl.gz'):plan['source_details_sha256'],
        str(source/'COMPLETE.json'):plan['input_pins']['source_complete_sha256'],
        str(source/'OUTPUT_SEAL.json'):plan['input_pins']['source_output_seal_sha256'],
        str(prepared/'PLAN.json'):plan['input_pins']['prepared_plan_sha256'],
        str(prepared/'ARC_EVENTS.json'):plan['input_pins']['arc_events_sha256'],
        str(audit_path):plan['input_pins']['model_pin_audit_sha256']}
    for path,sha in input_paths.items():check_file(path,sha)
    complete=json.loads((source/'COMPLETE.json').read_text())
    require(complete['status']=='COMPLETE_FIXED12_DIAGNOSTIC','source pilot not complete')
    seal=json.loads((source/'OUTPUT_SEAL.json').read_text())
    for relative,sha in seal.items():
        path=(source/relative).resolve();require(path.is_relative_to(source),'source seal path escape')
        check_file(path,sha);input_paths[str(path)]=sha
    require(complete['output_seal_sha256']==digest(source/'OUTPUT_SEAL.json'),'source completion/seal mismatch')
    require(complete['summary_sha256']==digest(source/'SUMMARY.json'),'source completion/summary mismatch')
    with gzip.open(source/'DETAILS.jsonl.gz','rt') as stream:details=[json.loads(line) for line in stream]
    require([d['start_index'] for d in details]==plan['start_indices']==list(range(0,1200,100)),
            'fixed source order mismatch')
    source_sets=[CompleteSourceSet.from_saved_record(d,source_id='fixed12:'+plan['source_details_sha256']+':'+str(d['start_index']),
                 registered_length_m=plan['length']['m']) for d in details]
    require([len(s.integers) for s in source_sets]==plan['source_candidates_per_window'],
            'complete source candidates mismatch')
    require(sum(len(s.integers) for s in source_sets)==plan['source_candidate_total']==23,'source budget changed')
    saved=json.loads((prepared/'PLAN.json').read_text());audit=json.loads(audit_path.read_text())
    records=saved['records'];require(len(records)==1200 and saved['sequence']=='BY2'
        and saved['window_s']==[100.,340.] and saved['baseline_length_m']==plan['length']['m'],'prepared contract mismatch')
    require(audit['plan_sha256']==plan['input_pins']['prepared_plan_sha256'],'model audit source mismatch')
    require(plan['future_offsets']==[5,6,7,8,9] and plan['selection_offsets']==[0,1,2,3,4],
            'fixed slot layout changed')
    chosen=[]
    for start,origin in zip(plan['start_indices'],source_sets):
        require(origin.selected_at==records[start+4]['time_s'],'source selected_at differs from original saved model')
        for j in plan['future_offsets']:
            record=records[start+j]
            require(abs(record['time_s']-origin.selected_at-.2*(j-4))<=.01,'future timing changed')
            chosen.append(record)
            entry=record['families'].get(FAMILY,{})
            if entry.get('status')=='BUILT':
                path=(prepared/entry['file']).resolve();require(path.is_relative_to(prepared),'model path escape')
                sha=audit['model_npz_sha256'][entry['file']];check_file(path,sha);input_paths[str(path)]=sha
    out.mkdir(parents=True,exist_ok=False)
    emit(out/'INPUT_IDENTITY.json',dict(registration_commit=args.registration_commit,
        source_pins=plan['source_pins'],input_pins=input_paths,source_fingerprints=[s.fingerprint for s in source_sets],
        source_counts=[len(s.integers) for s in source_sets],source_completeness_scope=source_sets[0].likelihood_scope))
    emit(out/'EXECUTION_PLAN.json',plan)
    started=time.monotonic();calls=LifecycleCalls(gls_limit=115,glrt_limit=115,
        deadline_monotonic=started+plan['budgets']['suggested_total_wall_limit_s'])
    rows=[];limited=False
    try:
        # This is saved causal metadata, not raw UBX or a solver. Only current-slot
        # entries can affect graphs; no lookahead decision consumes later events.
        wanted={float(r['time_s']) for r in chosen}
        event_index={}
        for event in json.loads((prepared/'ARC_EVENTS.json').read_text()):
            if float(event['time_s']) not in wanted:continue
            key=(float(event['time_s']),int(event['rx']),event['signal'])
            require(key not in event_index,'duplicate current arc event')
            event_index[key]=event
        cfg=LifecycleConfig(length_m=plan['length']['m'],
            working_raw_coverage=plan['current_raw_cost']['working_coverage'],
            phase_family_alpha=plan['phase_quality']['family_alpha'],
            min_phase_rows=plan['geometry']['minimum_phase_rows'])
        with gzip.open(out/'DETAILS.jsonl.gz','wt',encoding='utf-8',newline='\n') as stream:
            for start,origin in zip(plan['start_indices'],source_sets):
                track=ConditionalCandidateSet(origin,cfg)
                for offset in plan['future_offsets']:
                    record=records[start+offset];t=float(record['time_s']);slot_started=time.monotonic()
                    row=dict(start_index=start,slot=offset-5,time_s=t,source_selected_at_s=origin.selected_at,
                        source_origin_count=len(origin.integers),status='NOT_EXECUTED',quality_status='NOT_EXECUTED',
                        physically_ended=False,retired_nodes=0,projected_classes=None,compatible_classes=None,
                        phase_rows=None,phase_rank=None,union_width_deg=None,full_circle=None,
                        direction_domain_qualified=False,significant_classes=None,dangerous_unobservable_classes=None,
                        no_effect_columns=None,aliased_columns=None,GLS_calls=0,GLRT_calls=0,reason='',wall_s=0.)
                    detail=dict(start_index=start,slot=offset-5,source_fingerprint=origin.fingerprint)
                    before=(calls.fixed_integer_gls_calls,calls.single_fault_glrt_calls)
                    if limited or time.monotonic()>calls.deadline_monotonic:
                        limited=True;row.update(status='NOT_EXECUTED_PROCESSING_LIMIT',reason='cooperative total processing bound')
                    else:
                        try:
                            alive={(n.signal,n.arc) for n in track.alive_nodes}
                            losses=physical_failures(alive,t,event_index)
                            qualified=[SdArcNode(*v) for v in sorted(alive-set(losses))]
                            detail['physical_arc_losses']=[dict(node=node,reasons=reasons) for node,reasons in sorted(losses.items())]
                            entry=record['families'].get(FAMILY,{})
                            model=load_model(prepared,record,audit['model_npz_sha256']) if entry.get('status')=='BUILT' else None
                            current_axes=axes(record['anchor_ecef_m']) if model is not None else None
                            result=track.advance(model,time_s=t,qualified_nodes=qualified,horizontal_axes=current_axes,calls=calls)
                            detail['current_set_domain']=result
                            detail['current_NE_axes_ecef']=current_axes
                            row.update(status=result.status,quality_status=result.quality_status,
                                physically_ended=result.physically_ended,retired_nodes=len(result.retired_nodes),
                                projected_classes=len(result.classes),compatible_classes=result.compatible_class_count,
                                phase_rows=result.phase_rows,phase_rank=result.phase_rank,
                                union_width_deg=None if result.azimuth_outer_arc is None else math.degrees(result.azimuth_outer_arc.width_rad),
                                full_circle=None if result.azimuth_outer_arc is None else result.azimuth_outer_arc.full_circle,
                                direction_domain_qualified=result.direction_domain_qualified,
                                significant_classes=sum(any(e.significant for e in c.phase_effects) for c in result.classes),
                                dangerous_unobservable_classes=sum(any(e.classification=='DANGEROUS_UNOBSERVABLE_BASELINE_EFFECT' for e in c.phase_effects) for c in result.classes),
                                no_effect_columns=sum(e.classification=='NA_NO_CURRENT_EFFECT' for c in result.classes for e in c.phase_effects),
                                aliased_columns=sum(e.classification=='OBSERVABLE_ALIAS' for c in result.classes for e in c.phase_effects))
                        except Exception as exc:
                            row.update(status='CURRENT_SLOT_EXCEPTION_NO_PUBLICATION',quality_status='UNQUALIFIED_CURRENT_NUMERICS',
                                reason=type(exc).__name__+': '+str(exc),physically_ended=track.physically_ended)
                            detail['exception_traceback']=traceback.format_exc()
                            if time.monotonic()>calls.deadline_monotonic:limited=True
                    row.update(GLS_calls=calls.fixed_integer_gls_calls-before[0],
                        GLRT_calls=calls.single_fault_glrt_calls-before[1],wall_s=time.monotonic()-slot_started)
                    rows.append(row);stream.write(json.dumps(clean(dict(row=row,**detail)),ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
                write_csv(out/'RESULTS.csv',rows)
                emit(out/'PROGRESS.json',dict(terminal_slots=len(rows),expected_slots=60,calls=calls,limited=limited))
                print(json.dumps(clean(dict(terminal_slots=len(rows),last=row,calls=calls)),ensure_ascii=False),flush=True)
        check_registration(args.registration_commit,plan)
        for path,sha in input_paths.items():check_file(path,sha)
        require(len(rows)==60 and calls.fixed_integer_gls_calls<=115 and calls.single_fault_glrt_calls<=115,
                'final lifecycle slots/calls mismatch')
        summary=dict(status='PARTIAL_PROCESSING_LIMIT' if limited else 'COMPLETE_FIXED12_FIVE_SLOT_DIAGNOSTIC',
            registration_commit=args.registration_commit,expected_slots=60,terminal_rows=len(rows),
            processed_slots=sum(r['status']!='NOT_EXECUTED_PROCESSING_LIMIT' for r in rows),
            source_windows=12,nonempty_source_windows=9,empty_source_windows=3,source_candidates=23,
            status_counts=dict(Counter(r['status'] for r in rows)),quality_counts=dict(Counter(r['quality_status'] for r in rows)),
            direction_domain_qualified_slots=sum(r['direction_domain_qualified'] for r in rows),
            calls=asdict(calls),integer_enumeration_calls=0,LAMBDA_calls=0,CILS_calls=0,sphere_optimization_calls=0,
            raw_UBX_reads=0,reference_reads=0,navigation_calls=0,evaluator_calls=0,retries=0,
            total_processing_wall_s=time.monotonic()-started,accepted_integer_measurement=False,
            all_global_current_alternatives_covered=False,false_fix_probability=None,
            scope='conditional complete-source set; current raw domains and per-class diagnostic only; no cumulative statistical pruning')
        emit(out/'SUMMARY.json',summary)
        emit(out/'OUTPUT_SEAL.json',{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()})
        emit(out/'COMPLETE.json',dict(status=summary['status'],summary_sha256=digest(out/'SUMMARY.json'),output_seal_sha256=digest(out/'OUTPUT_SEAL.json')))
    except BaseException as exc:
        emit(out/'ABORTED.json',dict(error=repr(exc),calls=calls,terminal_rows=len(rows),traceback=traceback.format_exc()))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','prepared','input-audit','output','registration-commit'):p.add_argument('--'+key,required=True)
    run(p.parse_args())


if __name__=='__main__':main()
