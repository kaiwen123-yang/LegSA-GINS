#!/usr/bin/env python3
"""Bounded full-window conditional-set frontend; offline event replay, no reference."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,subprocess,sys,time,traceback
from collections import Counter,deque
from dataclasses import asdict,is_dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
from scipy.stats import chi2
from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import enumerate_candidate_envelope,filter_length_necessary_support
from legsa_gins.paper_rebuild.carrier_phase.candidate_lifecycle import CompleteSourceSet,LifecycleCalls
from legsa_gins.paper_rebuild.carrier_phase.set_provider import CompleteSetPointProvider,SetProviderPolicy,SetProviderCalls
from legsa_gins.paper_rebuild.carrier_phase.partial import PartialPolicy
from legsa_gins.paper_rebuild.carrier_phase.selected_likelihood import prepare_selected_likelihood
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode
from legsa_gins.paper_rebuild.carrier_phase.measurement import CSV_FIELDS,unavailable_measurement
from candidate_lifecycle_pilot import axes
from shadow_replay import load_model
from trusted_heading_arc_support_audit import physical_failures
PLAN_REL='docs/paper_rebuild/TRUSTED_HEADING_20261006/FULL_WINDOW_FRONTEND_PLAN.json'
SCRIPT_REL='scripts/paper_rebuild/carrier_phase/full_window_frontend.py'
FAMILY='GPS_GAL_BDS_DUAL'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def require(ok,reason):
 if not ok:raise RuntimeError(reason)
def clean(v):
 if is_dataclass(v):return clean(asdict(v))
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [clean(x) for x in v]
 if isinstance(v,float) and not math.isfinite(v):raise ValueError('nonfinite serialized result')
 return v
def emit(p,v):Path(p).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def read(p):return json.loads(Path(p).read_text())
def checked(p,h):require(sha(p)==h,'input/source hash mismatch: '+str(p))
def registered(commit,plan):
 for rel in (PLAN_REL,SCRIPT_REL,*plan['source_pins']):
  payload=(ROOT/rel).read_bytes()
  require(payload==subprocess.check_output(['git','show',commit+':'+rel],cwd=ROOT),'unregistered source '+rel)
  if rel in plan['source_pins']:require(hashlib.sha256(payload).hexdigest()==plan['source_pins'][rel],'source pin '+rel)
 for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
  require(os.environ.get(k)=='1','one numerical thread required: '+k)
def saved_table(path,rows):
 with Path(path).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def load_inputs(prepared,spec):
 seq=prepared/spec['sequence'];models=seq/'MODELS'
 checked(seq/'MODEL_OUTPUT_SEAL.json',spec['seal_sha256'])
 seal=read(seq/'MODEL_OUTPUT_SEAL.json')
 require(seal['complete_preparation'] is True,'incomplete prepared input')
 checked(models/'PLAN.json',seal['files']['PLAN.json']['sha256'])
 saved=read(models/'PLAN.json')
 require(saved['sequence']==spec['sequence'] and saved['window_s']==spec['window_s']
  and len(saved['records'])==spec['paired_epochs'] and saved['baseline_length_m']==.35,'original V3 window contract')
 checked(models/'ARC_EVENTS.json',seal['files']['ARC_EVENTS.json']['sha256'])
 events={}
 for e in read(models/'ARC_EVENTS.json'):
  k=(float(e['time_s']),int(e['rx']),e['signal']);require(k not in events,'duplicate arc event');events[k]=e
 return models,saved,seal,events
def current_nodes(provider,t,events):
 alive={(n.signal,n.arc) for n in provider.alive_nodes}
 losses=physical_failures(alive,t,events)
 return [SdArcNode(*x) for x in sorted(alive-set(losses))],losses
def source_acquire(block,library,source_id,counts,limits):
 """Exactly one fixed five-slot source opportunity, never replacement/tuning."""
 models=[x[1] for x in block]
 if len(models)!=5 or any(x is None for x in models):return None,dict(status='SELECTION_INPUT_UNAVAILABLE')
 selected=prepare_selected_likelihood(tuple(models),length_m=.35,
  policy=PartialPolicy(selection_epochs=5,min_ambiguities=4,max_ambiguities=6,epoch_interval_s=.2,time_tolerance_s=.01))
 detail=dict(selection=selected.selection,supports=selected.supports,status=selected.selection.status)
 if not selected.ready:return None,detail
 problem=selected.problem;counts['enumeration_calls']+=1
 require(counts['enumeration_calls']<=limits['enumeration_calls'],'enumeration budget exhausted')
 result=enumerate_candidate_envelope(problem,float(chi2.ppf(.99,len(problem.y))),
  lambda_library=library,horizontal_axes=axes(block[-1][0]['anchor_ecef_m']),target_epoch=-1,
  node_limit=100000,candidate_limit=10000,timeout_s=30.,
  max_condition_number=1e12,absolute_cost_guard=1e-9,relative_numerical_guard=1e-10)
 counts['enumeration_nodes']+=result.expanded_nodes;counts['enumeration_leaves']+=result.integer_leaves
 counts['length_filter_calls']+=1
 length=filter_length_necessary_support(problem,result)
 detail.update(raw_envelope=result,length_necessary_support=length,status=result.status)
 if not (result.numerical_support_complete and length.necessary_support_complete):return None,detail
 origin=CompleteSourceSet.from_saved_record(clean(detail),source_id=source_id,registered_length_m=.35)
 return origin,detail
def run(a):
 plan=read(ROOT/PLAN_REL);registered(a.registration_commit,plan)
 out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
 prepared=Path(a.prepared).resolve()
 checked(prepared/'COMPLETE.json',plan['prepared_complete_sha256'])
 checked(prepared/'SUMMARY.json',plan['prepared_summary_sha256'])
 require(read(prepared/'COMPLETE.json')['status']=='COMPLETE','preparation did not complete')
 emit(out/'REGISTERED_PLAN.json',plan)
 begin=time.monotonic();deadline=begin+plan['budgets']['total_processing_s']
 calls=SetProviderCalls(lifecycle=LifecycleCalls(gls_limit=400000,glrt_limit=400000,deadline_monotonic=deadline),
  geometry_limit=400000,sphere_limit=9210)
 counts=dict(enumeration_calls=0,enumeration_nodes=0,enumeration_leaves=0,length_filter_calls=0,
  acquisition_opportunities=0,acquisition_skipped_pending=0,acquisition_skipped_busy=0,
  actual_model_npz_reads=0,pending_providers_constructed=0,source_promotions=0,source_exception_count=0,slot_exception_count=0)
 summaries=[];limited=False
 try:
  for spec in plan['sequences']:
   modeldir,saved,seal,events=load_inputs(prepared,spec)
   library=Path(saved['lambda_library']);checked(library,plan['lambda_library_sha256'])
   seqout=out/spec['sequence'];seqout.mkdir()
   block=deque(maxlen=5);owner=None;pending=None;worker_free=-math.inf
   rows=[];source_rows=[];previous=None
   with gzip.open(seqout/'SOURCE_DETAILS.jsonl.gz','wt') as sources, gzip.open(seqout/'SLOT_DETAILS.jsonl.gz','wt') as slots, (seqout/'CARRIER.csv').open('w',newline='') as cf:
    cw=csv.DictWriter(cf,fieldnames=CSV_FIELDS,lineterminator='\n');cw.writeheader()
    for i,rec in enumerate(saved['records']):
     t=float(rec['time_s']);slot_start=time.monotonic()
     row=dict(index=i,time_s=t,status='NO_ACTIVE_SOURCE',valid=0,owner_source=None,pending_source=None,
      owner_status='',pending_status='',owner_compatible_classes=None,owner_phase_rows=None,owner_phase_rank=None,
      acquisition_status='',acquisition_available_s=None,worker_free_s=None,processing_wall_s=0.,
      current_result_runtime_available_s=None,source_change=False,reason='')
     detail=dict(index=i,time_s=t);measurement=unavailable_measurement(t,row['status'])
     limited=(limited or time.monotonic()>deadline
      or calls.lifecycle.fixed_integer_gls_calls>=calls.lifecycle.gls_limit
      or calls.lifecycle.single_fault_glrt_calls>=calls.lifecycle.glrt_limit
      or calls.geometry_calls>=calls.geometry_limit or calls.python_sphere_calls>=calls.sphere_limit)
     model=None
     if not limited and rec.get('families',{}).get(FAMILY,{}).get('status')=='BUILT':
      name=rec['families'][FAMILY]['file'];checked(modeldir/name,seal['files'][name]['sha256'])
      model=load_model(modeldir,rec,FAMILY);counts['actual_model_npz_reads']+=1
     block.append((rec,model))
     # A missing paired epoch is a temporal break, never a fabricated observation.
     if previous is not None and abs(t-previous-.2)>.01:
      detail['temporal_break_s']=t-previous;owner=None;pending=None;row['source_change']=True
     previous=t
     for role,obj in [('owner',owner),('pending',pending)]:
      if obj is not None and (t-obj['provider'].source.selected_at>(10. if role=='owner' else 3.)
                             or obj['provider'].terminal):
       detail[role+'_retired']='TTL_OR_PHYSICAL_TERMINAL'
       if role=='owner':owner=None;row['source_change']=True
       else:pending=None
     results={}
     busy=t<worker_free
     if limited:row['status']='NOT_EXECUTED_PROCESSING_LIMIT'
     elif busy:row['status']='WORKER_BUSY_NO_CURRENT_EXPORT'
     else:
      # Catch up only physical arc metadata with model=None: skipped slots cannot
      # gain validation retroactively and cannot export old measurements.
      for role,obj in [('owner',owner),('pending',pending)]:
       if obj is None:continue
       p=obj['provider']
       try:
        for past in range(obj['last_index']+1,i):
         pt=float(saved['records'][past]['time_s']);qn,_=current_nodes(p,pt,events)
         p.advance(None,time_s=pt,qualified_nodes=qn,horizontal_axes=None,decision_time_s=t,calls=calls)
         obj['last_index']=past
         if p.terminal:break
        qn,losses=current_nodes(p,t,events)
        step=p.advance(model,time_s=t,qualified_nodes=qn,
         horizontal_axes=None if model is None else axes(rec['anchor_ecef_m']),decision_time_s=t,calls=calls)
        obj['last_index']=i;results[role]=step
        detail[role]=dict(step=step,physical_losses=[dict(node=x,reasons=v) for x,v in sorted(losses.items())])
        row[role+'_status']=step.status
        if role=='owner' and step.domain is not None:
         row.update(owner_compatible_classes=step.domain.compatible_class_count,
          owner_phase_rows=step.domain.phase_rows,owner_phase_rank=step.domain.phase_rank)
        # Lost physical support cannot be restored by rediscovering the same name.
        if p.terminal or (step.domain is not None and step.domain.retired_nodes
          and (step.domain.phase_rows<4 or step.domain.phase_rank!=3)):
         detail[role+'_retired']='PHYSICAL_SUPPORT_INSUFFICIENT'
         if role=='owner':owner=None;row['source_change']=True
         else:pending=None
       except Exception as exc:
        counts['slot_exception_count']+=1;row['reason']+=role+':'+repr(exc)+';'
        detail[role+'_exception']=traceback.format_exc()
        if role=='owner':owner=None;row['source_change']=True
        else:pending=None
      if owner is not None and 'owner' in results:
       step=results['owner'];row['status']=step.status;measurement=step.measurement
      # Never rank owners by residual/width or fuse two source measurements.
      if owner is None and pending is not None and 'pending' in results and results['pending'].measurement.valid:
       owner=pending;pending=None;counts['source_promotions']+=1
       row['source_change']=True;row['status']='PROMOTED_OWNER_NEXT_SLOT_ONLY'
       measurement=unavailable_measurement(t,row['status'])
      current_service=time.monotonic()-slot_start
      worker_free=t+current_service
      if measurement.valid:row['current_result_runtime_available_s']=worker_free
     if (i+1)%5==0:
      counts['acquisition_opportunities']+=1
      ar=dict(end_index=i,selected_at_s=t,status='',source_candidates=None,available_at_s=None,wall_s=0.,reason='')
      if limited:ar['status']='NOT_EXECUTED_PROCESSING_LIMIT'
      elif busy:ar['status']='SKIPPED_WORKER_BUSY';counts['acquisition_skipped_busy']+=1
      elif pending is not None:ar['status']='SKIPPED_PENDING_OCCUPIED';counts['acquisition_skipped_pending']+=1
      else:
       acquisition_start=time.monotonic()
       sid=spec['sequence']+':fixed5:'+str(i)+':'+spec['seal_sha256']
       acquisition=dict(source_id=sid,end_index=i)
       try:
        origin,ad=source_acquire(tuple(block),library,sid,counts,plan['budgets'])
        acquisition.update(ad)
        ar['status']=ad['status']
        if origin is not None:
         ar['source_candidates']=len(origin.integers)
         if not origin.integers:ar['status']='COMPLETE_EMPTY_SOURCE'
         elif len(origin.integers)>64:ar['status']='COMPLETE_SOURCE_OVER_ACTIVATION_RESOURCE_CAP'
         else:
          # Whole acquisition follows current service on the one virtual worker.
          available=max(t,worker_free)+(time.monotonic()-acquisition_start)
          provider=CompleteSetPointProvider(origin,source_available_at_s=available,policy=SetProviderPolicy())
          pending=dict(provider=provider,last_index=i);counts['pending_providers_constructed']+=1
          ar.update(status='COMPLETE_SOURCE_PENDING',available_at_s=available)
          acquisition['source_fingerprint']=origin.fingerprint
       except Exception as exc:
        counts['source_exception_count']+=1;ar.update(status='SOURCE_EXCEPTION_NO_RETRY',reason=repr(exc))
        acquisition['exception']=traceback.format_exc()
       ar['wall_s']=time.monotonic()-acquisition_start
       worker_free=max(t,worker_free)+ar['wall_s']
       # Include serialization/activation overhead in the source's public availability.
       if pending is not None and pending['last_index']==i and ar['status']=='COMPLETE_SOURCE_PENDING':
        pending['provider'].source_available_at_s=worker_free
        ar['available_at_s']=worker_free
       sources.write(json.dumps(clean(dict(row=ar,**acquisition)),allow_nan=False)+'\n');sources.flush()
      source_rows.append(ar);row['acquisition_status']=ar['status'];row['acquisition_available_s']=ar['available_at_s']
     row['owner_source']=None if owner is None else owner['provider'].source.source_id
     row['pending_source']=None if pending is None else pending['provider'].source.source_id
     row['worker_free_s']=None if not math.isfinite(worker_free) else worker_free
     row['valid']=int(measurement.valid);row['processing_wall_s']=time.monotonic()-slot_start
     if not measurement.valid:measurement=unavailable_measurement(t,row['status'])
     cw.writerow(measurement.csv_row());rows.append(row)
     slots.write(json.dumps(clean(dict(row=row,**detail)),allow_nan=False)+'\n')
     if (i+1)%100==0:
      cf.flush();slots.flush()
      emit(out/'PROGRESS.json',dict(sequence=spec['sequence'],rows=i+1,counts=counts,calls=calls,
       elapsed_s=time.monotonic()-begin))
      print(json.dumps(dict(sequence=spec['sequence'],rows=i+1,total=len(saved['records']),valid=sum(x['valid'] for x in rows))),flush=True)
   saved_table(seqout/'EPOCHS.csv',rows);saved_table(seqout/'ACQUISITIONS.csv',source_rows)
   summary=dict(sequence=spec['sequence'],window_s=spec['window_s'],rows=len(rows),
    valid_research_points=sum(x['valid'] for x in rows),status_counts=dict(Counter(x['status'] for x in rows)),
    acquisition_status_counts=dict(Counter(x['status'] for x in source_rows)),source_changes=sum(x['source_change'] for x in rows))
   emit(seqout/'SUMMARY.json',summary)
   emit(seqout/'OUTPUT_SEAL.json',{p.name:sha(p) for p in sorted(seqout.iterdir()) if p.is_file()})
   summaries.append(summary)
  registered(a.registration_commit,plan)
  emit(out/'SUMMARY.json',dict(status='PARTIAL_PROCESSING_LIMIT' if limited else 'COMPLETE',
   registration_commit=a.registration_commit,counts=counts,calls=calls,sequences=summaries,
   wall_s=time.monotonic()-begin,integer_truth_available=False,reference_reads=0,navigation_calls=0,
   offline_event_replay_not_hardware_realtime=True))
  emit(out/'COMPLETE.json',dict(status='TERMINAL_ALL_FULL_WINDOW_ROWS',summary_sha256=sha(out/'SUMMARY.json'),
   sequence_seals={x['sequence']:sha(out/x['sequence']/'OUTPUT_SEAL.json') for x in summaries}))
 except BaseException as exc:
  emit(out/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),counts=counts,calls=calls))
  raise
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ('prepared','output','registration-commit'):p.add_argument('--'+key,required=True)
 run(p.parse_args())
