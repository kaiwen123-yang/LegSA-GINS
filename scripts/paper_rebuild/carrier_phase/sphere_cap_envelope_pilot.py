#!/usr/bin/env python3
"""One registered read-only geometry pass over 60 sealed slots / 115 classes."""
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
from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import CircularArc
from legsa_gins.paper_rebuild.carrier_phase.sphere_cap_envelope import (
    sphere_direction_envelope,cover_from_arcs)

PLAN_REL='docs/paper_rebuild/TRUSTED_HEADING_20261006/SPHERE_CAP_ENVELOPE_PLAN.json'
SCRIPT_REL='scripts/paper_rebuild/carrier_phase/sphere_cap_envelope_pilot.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition,reason):
    if not condition:raise RuntimeError(reason)


def clean(v):
    if is_dataclass(v):return clean(asdict(v))
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,float) and not math.isfinite(v):raise ValueError('nonfinite output')
    return v


def emit(path,value):
    Path(path).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def csv_write(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def arc(value):
    return None if value is None else CircularArc(**value)


def widths(cover):
    hull=cover.enclosing_arc
    return (math.degrees(cover.total_width_rad),None if hull is None else math.degrees(hull.width_rad))


def registration(commit,plan):
    require(len(commit)==40 and all(c in '0123456789abcdef' for c in commit),'full registration commit required')
    for rel in (PLAN_REL,SCRIPT_REL):
        require(subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)==(ROOT/rel).read_bytes(),
            'registration bytes mismatch: '+rel)
    for rel,sha in plan['source_pins'].items():
        path=(ROOT/rel).resolve();require(path.is_relative_to(ROOT),'source pin path escape')
        require(digest(path)==sha,'source SHA mismatch: '+rel)
        require(hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT)).hexdigest()==sha,
            'source absent from registration: '+rel)
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        require(os.environ.get(name)=='1','explicit one-thread environment required: '+name)
    require(str(ROOT/'src') in os.environ.get('PYTHONPATH','').split(os.pathsep),'explicit repo PYTHONPATH required')


def run(args):
    plan=json.loads((ROOT/PLAN_REL).read_text());registration(args.registration_commit,plan)
    source=Path(args.source).resolve();out=Path(args.output).resolve()
    require(not out.exists(),'fresh attempt directory required; no retry/resume')
    for rel,sha in plan['input_pins'].items():
        path=(source/rel).resolve();require(path.is_relative_to(source),'input path escape')
        require(digest(path)==sha,'input SHA mismatch: '+rel)
    seal=json.loads((source/'OUTPUT_SEAL.json').read_text())
    for rel,sha in seal.items():
        path=(source/rel).resolve();require(path.is_relative_to(source),'seal path escape')
        require(digest(path)==sha,'sealed input mismatch: '+rel)
    complete=json.loads((source/'COMPLETE.json').read_text())
    require(complete['status']=='COMPLETE_FIXED12_FIVE_SLOT_DIAGNOSTIC'
        and complete['output_seal_sha256']==digest(source/'OUTPUT_SEAL.json')
        and complete['summary_sha256']==digest(source/'SUMMARY.json'),'input not sealed complete')
    oldplan=json.loads((source/'EXECUTION_PLAN.json').read_text())
    require(oldplan['length']['m']==plan['length_interval_m'][0]==plan['length_interval_m'][1]==.35,
        'exact original length contract mismatch')
    with gzip.open(source/'DETAILS.jsonl.gz','rt') as stream:records=[json.loads(line) for line in stream]
    require([(r['start_index'],r['slot']) for r in records]==[(i,j) for i in range(0,1200,100) for j in range(5)],
        'fixed 60 ordered slot identities differ')
    require(sum(len(r['current_set_domain']['classes']) for r in records)==plan['budgets']['geometry_calls']==115,
        'all-class input budget differs')
    require(all(r['current_set_domain']['accepted_integer_measurement'] is False for r in records),
        'source unexpectedly claims accepted measurements')
    out.mkdir(parents=True,exist_ok=False)
    emit(out/'EXECUTION_PLAN.json',plan)
    emit(out/'INPUT_IDENTITY.json',dict(registration_commit=args.registration_commit,source=str(source),
        input_pins=plan['input_pins'],source_pins=plan['source_pins'],numpy_version=np.__version__,
        source_registration_commit=json.loads((source/'SUMMARY.json').read_text())['registration_commit']))
    started=time.monotonic();calls=0;exceptions=0;rows=[];classrows=[]
    try:
        with gzip.open(out/'DETAILS.jsonl.gz','wt',encoding='utf-8',newline='\n') as stream:
            for record in records:
                old=record['current_set_domain'];r0=record['row'];classdetails=[]
                old_arcs=[];new_arcs=[];new_count=0;geometry_empty=0;slot_exceptions=0
                for index,c in enumerate(old['classes']):
                    require(calls<115,'geometry call budget exceeded')
                    old_arc=arc(c['azimuth_outer_arc'])
                    require((old_arc is not None)==c['cost_compatible'],'old compatibility/arc mismatch')
                    old_cover=cover_from_arcs(()) if old_arc is None else cover_from_arcs((old_arc,))
                    if c['cost_compatible']:old_arcs.extend(old_cover.components)
                    calls+=1;error='';result=None
                    try:
                        # Quality fields do not select inputs, alter cost, or enter geometry.
                        result=sphere_direction_envelope(c['baseline_center_m'],c['baseline_covariance_m2'],
                            c['raw_budget'],horizontal_axes=record['current_NE_axes_ecef'],
                            length_interval_m=plan['length_interval_m'],
                            recorded_outer_radius_m=c['baseline_outer_radius_m'],
                            legacy_cover=old_cover if c['cost_compatible'] else None,
                            **plan['numerics'])
                        retained=c['cost_compatible'] and not result.cover.empty
                        cover=result.cover if retained else cover_from_arcs(())
                        status=result.status
                        newly_empty=c['cost_compatible'] and result.cover.empty
                    except Exception as exc:
                        exceptions+=1;slot_exceptions+=1
                        error=type(exc).__name__+': '+str(exc)
                        # Never convert an unsupported numerical calculation to deletion.
                        retained=c['cost_compatible'];cover=old_cover;newly_empty=False
                        status='UNQUALIFIED_NUMERICS_OLD_COVER_RETAINED'
                    if retained:new_count+=1;new_arcs.extend(cover.components)
                    geometry_empty+=newly_empty
                    total,hull=widths(cover)
                    cr=dict(start_index=record['start_index'],slot=record['slot'],time_s=r0['time_s'],class_index=index,
                        origin_count=len(c['origins']),original_raw_compatible=c['raw_compatible'],
                        original_length_compatible=c['cost_compatible'],original_quality_reasons='|'.join(c['quality_reasons']),
                        original_significant_phase=any(x['significant'] for x in c['phase_effects']),
                        geometry_status=status,new_geometry_empty=newly_empty,retained_geometry_class=retained,
                        old_arc_width_deg=None if old_arc is None else math.degrees(old_arc.width_rad),
                        new_component_count=len(cover.components),new_total_width_deg=total,new_hull_width_deg=hull,error=error)
                    classrows.append(cr)
                    classdetails.append(dict(row=cr,origins=c['origins'],integer_items=c['integer_items'],
                        original_quality_reasons=c['quality_reasons'],geometry=result,effective_cover=cover))
                old_cover=cover_from_arcs(old_arcs);new_cover=cover_from_arcs(new_arcs)
                old_total,old_hull=widths(old_cover);new_total,new_hull=widths(new_cover)
                row=dict(start_index=record['start_index'],slot=record['slot'],time_s=r0['time_s'],
                    source_origin_count=r0['source_origin_count'],original_status=r0['status'],
                    original_quality_status=r0['quality_status'],original_direction_domain_qualified=r0['direction_domain_qualified'],
                    original_classes=len(old['classes']),original_compatible_classes=old['compatible_class_count'],
                    new_geometry_classes=new_count,new_geometry_empty_classes=geometry_empty,
                    geometry_processing_qualified=slot_exceptions==0,geometry_exceptions=slot_exceptions,
                    old_total_width_deg=old_total,old_hull_width_deg=old_hull,
                    new_component_count=len(new_cover.components),new_total_width_deg=new_total,new_hull_width_deg=new_hull,
                    new_full_circle=new_cover.full_circle,original_phase_veto_classes=r0['significant_classes'],
                    original_dangerous_classes=r0['dangerous_unobservable_classes'],
                    original_retired_nodes=r0['retired_nodes'],accepted_integer_measurement=False,
                    phase_quality_reclassified=False,all_global_current_alternatives_covered=False)
                rows.append(row)
                stream.write(json.dumps(clean(dict(row=row,source_fingerprint=record['source_fingerprint'],
                    current_model_fingerprint=old['current_model_fingerprint'],
                    transformed_model_fingerprint=old['transformed_model_fingerprint'],
                    classes=classdetails,cover=new_cover)),ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
        require(calls==115 and len(rows)==60 and len(classrows)==115,'terminal budget mismatch')
        registration(args.registration_commit,plan)
        for rel,sha in plan['input_pins'].items():require(digest(source/rel)==sha,'input changed during pass')
        for rel,sha in seal.items():require(digest(source/rel)==sha,'sealed input changed during pass')
        csv_write(out/'RESULTS.csv',rows);csv_write(out/'CLASS_RESULTS.csv',classrows)
        summary=dict(status='COMPLETE_GEOMETRY_ONLY_POSTPROCESS',registration_commit=args.registration_commit,
            slots=60,classes=115,geometry_calls=calls,geometry_exceptions=exceptions,
            original_quality_counts=dict(Counter(r['original_quality_status'] for r in rows)),
            original_compatible_classes=sum(r['original_compatible_classes'] for r in rows),
            retained_geometry_classes=sum(r['new_geometry_classes'] for r in rows),
            new_geometry_empty_classes=sum(r['new_geometry_empty_classes'] for r in rows),
            geometry_class_status_counts=dict(Counter(r['geometry_status'] for r in classrows)),
            geometry_empty_slots=sum(r['new_geometry_classes']==0 for r in rows),
            disconnected_cover_slots=sum(r['new_component_count']>1 for r in rows),
            original_ready_slots=sum(r['original_direction_domain_qualified'] for r in rows),
            phase_quality_reclassified=False,accepted_integer_measurement=False,false_fix_probability=None,
            all_global_current_alternatives_covered=False,GLS_calls=0,GLRT_calls=0,integer_enumeration_calls=0,
            LAMBDA_calls=0,CILS_calls=0,sphere_optimization_calls=0,navigation_calls=0,evaluator_calls=0,
            raw_UBX_reads=0,reference_reads=0,retries=0,total_processing_wall_s=time.monotonic()-started,
            scope='same sealed conditional source sets / same raw Q and tau / exact registered length; numerical outer covers only')
        emit(out/'SUMMARY.json',summary)
        emit(out/'OUTPUT_SEAL.json',{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()})
        emit(out/'COMPLETE.json',dict(status=summary['status'],summary_sha256=digest(out/'SUMMARY.json'),
            output_seal_sha256=digest(out/'OUTPUT_SEAL.json')))
        print(json.dumps(clean(summary),ensure_ascii=False),flush=True)
    except BaseException as exc:
        emit(out/'ABORTED.json',dict(error=repr(exc),geometry_calls=calls,slots=len(rows),classes=len(classrows),traceback=traceback.format_exc()))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','registration-commit'):parser.add_argument('--'+name,required=True)
    run(parser.parse_args())


if __name__=='__main__':main()
