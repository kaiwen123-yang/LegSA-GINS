"""Read existing records only; never import project runtime or evaluators."""
from pathlib import Path
import csv, json, gzip, hashlib

R=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
D=R/'docs/paper_rebuild'
G=Path('/mnt/g/LegSA-GINS-project')
O=G/'V3研究记录梳理_20261011/fusion'
S=G/'clean_rebuild_202607/stages'
sources=[]
def read(p, purpose, depth='full text / structured fields'):
    p=Path(p)
    if not p.exists():
        sources.append(dict(absolute_path=str(p),read_depth='not found',purpose=purpose,bytes='',sha256=''))
        return ''
    b=p.read_bytes()
    sources.append(dict(absolute_path=str(p),read_depth=depth,purpose=purpose,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    return (gzip.decompress(b) if p.suffix=='.gz' else b).decode('utf-8-sig',errors='replace')
def tab(p,purpose): return list(csv.DictReader(read(p,purpose).splitlines()))
def j(p,purpose): return json.loads(read(p,purpose))
def dump(name, obj): (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def save(name,rows):
    if rows:
        with (O/name).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

for n in ['AGENTS.md']:
    read(R/n,'active authority; skim terminal sections','full file acquired; selected semantic reading')
for n in ['ACTIVE_CONTEXT.md','DATA_ROLES.md','METHOD_SCOPE.md','EXPERIMENT_PROTOCOL.md','LEGACY_DENYLIST.md','CLAIM_BOUNDARY.md','NEXT_ACTIONS.md']:
    read(D/n,'active/obsolete status and allowed evidence','full file acquired; scope and precedence sections read')
docs=['hext/HX03_PREREG.md','hext/HX03/HX03_RESULTS.md','hext/HX03R/HX03R1_D12_DIAGNOSIS.md','hext/HX03R2/HX03R2_RESULTS.md','hext/HX02/HX02_RESULTS.md','hext/FGO_REPRODUCTION_FIX_20261004/README.md','hext/FGO_REPRODUCTION_FIX_20261004/REPRODUCTION_NOTES.md','hext/FGO_COMPARISON/README.md','hext/FGO_COMPARISON/REPRODUCTION_NOTES.md','FGO_COMPLETE_AUDIT_20261004/SEGMENTED_PROTOCOL.md','FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/RESULTS_AND_LIMITATIONS.md','V3_STORY_20261004/04_COMPARISON_INVENTORY_AND_FAIRNESS_STORY.md','hext/EXT_REPRODUCTION/CONTROL_AND_DEGRADATION_SCOPE.md','horizontal_literature/ginav2021/LC02_GINAV2021_FINAL_TERMINAL_REPORT.md']
for n in docs: read(D/n,'history, correction and scientific role','full text; main numeric and identity sections inspected')
for n in ['horizontal_literature/ext05_pavlasek.py','hext/hx03_native.py','hext/hx03_injection.py','hext/hx03_relative_update.py','hext/ext05_sequence_runner.py','hext/hx02_ginav.py','hext/hx02_ginav_nav.py','fgo_comparison/oisam.py','fgo_comparison/segmented_diagnostic.py','fgo_comparison/wen_tc.py','fgo_comparison/gnc.py']:
    read(R/'src/legsa_gins/paper_rebuild'/n,'static method identity; no import/execution','full file acquired; measurement/state/control branches inspected')
for n in ['OISAM_PAPER_CONTRACT_20261004.json','WEN_TC_PAPER_CONTRACT_20261004.json','GNC_PAPER_CONTRACT_20261004.json']:
    j(R/'configs/paper_rebuild/fgo_comparison'/n,'fixed actual FGO configuration')
main=tab(S/'CLEAN8_PROTOCOL_V3/07_AGGREGATE/MAIN_TABLE_V3.csv','formal full existing main table')
lc=[r for r in main if r['method_id'] in ['LC01','LC01-S','EXT05C','EXT05C-S']]
save('LC_NATIVE_TABLE_READ.csv',lc)
hx=tab(D/'hext/HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv','all 396 corrected results')
hxs=tab(D/'hext/HX03R2/DEGRADATION_EXTERNAL_SUMMARY_R2.csv','corrected family/type summaries')
hxp=tab(D/'hext/HX03R2/DEGRADATION_PAIRED_R2.csv','completed pairings against F04/F02')
save('HX03_R2_A2_AND_FAMILY_READ.csv',[r for r in hxs if r['level']=='family'])
save('HX03_R2_EXISTING_PAIRS_READ.csv',[r for r in hxp if r['level']=='family'])
strict=tab(D/'hext/FGO_REPRODUCTION_FIX_20261004/METRICS.csv','all strict FGO metrics')
sruns=tab(D/'hext/FGO_REPRODUCTION_FIX_20261004/RUNS.csv','all 9 strict FGO run identities')
froot=Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z')
strict_details=[]
for x in sruns:
    p=Path(x['run_path'].replace('<FGO_ROOT>',str(froot)))
    v=j(p,'actual native RUN.json / config and output identity')
    strict_details.append(dict(sequence=x['sequence_id'],method=x['method_id'],run_path=str(p),run=v))
dump('STRICT_RUN_RECORDS_READ.json',strict_details)
seg=S/'FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z'
segdetails=[]
for seq in ['BY2','BY2H','BY2O']:
    p=seg/f'runs/{seq}/OISAM/SEGMENTED_DIAGNOSTIC'
    segdetails.append(dict(sequence=seq,run=j(p/'RUN.json','actual segmented run'),blocks=j(p/'BLOCKS.json','11 preregistered gap blocks'),access=j(p/'ACCESS.json','actual native access receipt')))
    tab(D/f'FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/evaluation/{seq}/METRICS.csv','all segmented metric rows')
dump('SEGMENTED_RUN_RECORDS_READ.json',segdetails)
for n in ['BY2_NO_RESTART_CONTROL.json','PREREGISTRATION.json','ALL_NATIVE_SEALED.json','NATIVE_JOURNAL.json']:
    j(D/'FGO_COMPLETE_AUDIT_20261004/SEGMENTED_NATIVE_CHECKPOINT'/n,'strict/segmented control evidence')
read(R/'cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp','robust analogue implementation','full file acquired; 437-552 inspected')
tab(D/'V3_STORY_20261004/INTERNAL_ROBUST_ANALOGUE_SCOPE.csv','7 covariance shape identities, not 7 author algorithms')
save('SOURCES_READ.csv',sources)
print(json.dumps(dict(source_count=len(sources),lc_rows=len(lc),hx_rows=len(hx),hx_paired_rows=len(hxp),strict_metrics=len(strict),strict_runs=len(sruns),segmented_runs=len(segdetails)),ensure_ascii=False))

# Inspect native evidence and retained time series rather than relying only on reports.
checks=[]
for x,d in zip(sruns,strict_details):
    p=Path(d['run_path']); states=p.parent/'STATES.csv'
    rows=tab(states,'full actual strict native time series; row/status and sealed hash')
    a=j(p.parent/'ACCESS.json','actual strict native access receipt')
    checks.append(dict(kind='strict_native',sequence=x['sequence_id'],method=x['method_id'],path=str(states),rows=len(rows),first=rows[0],last=rows[-1],hash_equal=hashlib.sha256(states.read_bytes()).hexdigest()==x['states_sha256'],run_manifest_equal=hashlib.sha256(p.read_bytes()).hexdigest()==x['run_manifest_sha256']))
    snap=p.parent/'SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/fgo_comparison'/('oisam.py' if x['method_id']=='OISAM' else 'wen_tc.py' if x['method_id']=='WEN_TC' else 'gnc.py')
    if x['sequence_id']=='BY2': read(snap,'actual sealed execution source','full source acquired; identity and key estimator branch inspected')
for seq in ['BY2','BY2H','BY2O']:
    p=seg/f'runs/{seq}/OISAM/SEGMENTED_DIAGNOSTIC'
    rows=tab(p/'STATES.csv','full actual segmented state series')
    events=[json.loads(x) for x in read(p/'SOLVER_EVENTS.jsonl','full saved solver event stream').splitlines() if x]
    checks.append(dict(kind='segmented_native',sequence=seq,method='OISAM',path=str(p/'STATES.csv'),rows=len(rows),event_count=len(events),first=rows[0],last=rows[-1]))
    for method in ['OISAM','WEN_TC','GNC']:
        ep=seg/f'evaluation/{seq}/{method}_PRIMARY_DYNAMIC_ONLY_ERRORS.csv'
        er=tab(ep,'full retained primary error series; no recomputation')
        checks.append(dict(kind='segmented_errors',sequence=seq,method=method,path=str(ep),rows=len(er),first=er[0],last=er[-1]))

hx_details=[]
for method in ['LC01','EXT05C','LC01-BR']:
    name=f'BY2__{method}__LIT__D62_20s_seed_00__seed_00'
    p=S/'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION/RUNS'/name
    hx_details.append(dict(method=method,command=j(p/'COMMAND.json','actual HX03 command'),params=j(p/'PARAMS_ECHO.json','actual HX03 runtime parameters'),input=j(p/'INPUT_HASHES.json','actual existing injection and input identity'),native=j(p/'native/NATIVE_RESULT.json','actual native completion'),stderr=read(p/'native_stderr.log','actual native stderr')))
    erp=S/'CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/RUNS'/name/'v3_R2/error_series_R2.csv.gz'
    er=tab(erp,'full retained corrected 20s A2 error series')
    checks.append(dict(kind='hx_a2_errors',method=method,path=str(erp),rows=len(er),first=er[0],last=er[-1]))
dump('HX03_ACTUAL_RUNS_READ.json',hx_details)
for seq,start in [('BY2','C00'),('BY2H','CONTRACT_START'),('BY2O','FILE_START')]:
    p=S/f'CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS/{seq}__GINAV__NONE__{start}__NA'
    for fn in ['COMMAND.json','DONE.json','native/GINAV_RUN.json','eval/GINAV_EVALUATION.json','eval/D8_BOUNDED_GATE.json']:
        j(p/fn,'actual GINav command, native run and later evaluation/gate record')
    log=read(p/'native/NATIVE_stdout.log','actual MATLAB stdout, selected diagnostic messages','full text acquired; terminal lines and data counts inspected')
    checks.append(dict(kind='ginav_log',sequence=seq,path=str(p/'native/NATIVE_stdout.log'),lines=len(log.splitlines()),tail=log.splitlines()[-8:]))
for method in ['LC01','LC01-S','EXT05C','EXT05C-S']:
    p=S/f'CLEAN7_HEXT_EXTERNAL_SEQUENCES/04_NATIVE_RUNS/BY2H/{method}/CONTRACT_START'
    for fn in ['NATIVE_SUMMARY.json','NATIVE_FREEZE.json','SCIENTIFIC_SUMMARY.json','GEOMETRIC_AUDIT.json']:
        read(p/fn,'actual natural run parameters, identity and geometry','full JSON; key fields inspected')
dump('ACTUAL_RECORD_CHECKS.json',checks)
save('SOURCES_READ.csv',sources)
print(json.dumps(dict(source_count=len(sources),strict_hash_checks=sum(c.get('hash_equal',False) for c in checks),strict_manifest_checks=sum(c.get('run_manifest_equal',False) for c in checks),actual_series=len(checks)),ensure_ascii=False))

registry=[]
def rec(**kw):
    row={k:'' for k in ['stage','sequence','method','configuration','case_id','seed','comparison_role','status','input_scope','support','yaw_rmse_deg','horizontal_rmse_m','up_rmse_m','source_table','native_record','error_series','reading_depth','reuse_note']}
    row.update(kw);registry.append(row)
for x in lc:
    rec(stage='CLEAN7 / frozen V3 retained',sequence=x['sequence_id'],method=x['method_id'],configuration=x['config']+' / '+x['start_convention'],case_id='natural',comparison_role='closest position-level IEKF / single-receiver update control',status=x['evaluation_status'],input_scope='position solution + body IMU; same IEKF backbone, LIT/S parameter conditions',support=x['matched_epoch_count']+'/'+x['output_epoch_count'],yaw_rmse_deg=x['yaw_rmse_deg'],horizontal_rmse_m=x['h_rmse_m'],up_rmse_m=x['up_rmse_m'],source_table=str(S/'CLEAN8_PROTOCOL_V3/07_AGGREGATE/MAIN_TABLE_V3.csv'),native_record=json.loads(x['notes']).get('native_source','see retained source provenance'),error_series=x['error_series_source'],reading_depth='full frozen table; four BY2H CONTRACT_START native metadata and core source branches',reuse_note='16 includes FILE_START/CONTRACT_START conditions; no added runs')
for x in hx:
    run=x['source_run_dir'].replace('$HX03',str(S/'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'))
    rec(stage='HX03R2 corrected audit',sequence='BY2',method=x['method'],configuration=x['config'],case_id=x['case_id'],seed=x['seed'],comparison_role=x['family']+' / paired F04/F02 or A2 relative-only control',status=x['failure_class'],input_scope=x['input_identity_note'],yaw_rmse_deg=x['yaw_rmse_deg'],horizontal_rmse_m=x['horizontal_rmse_m'],up_rmse_m=x['up_rmse_m'],source_table=str(D/'hext/HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv'),native_record=run+'/native/NATIVE_RESULT.json',error_series=run.replace('HX03_DEGRADATION','HX03R2_AUDIT_REEVAL')+'/v3_R2/error_series_R2.csv.gz',reading_depth='all 396 result rows and 744 pairing rows; three A2 seed00 actual native/error chains',reuse_note='logical row: A1/D61 aliases A2/D62; no-op rows and cached equivalent runs retained')
for x in strict:
    if x['support']!='OWN_VALID':continue
    rr=next(z for z in strict_details if z['sequence']==x['sequence_id'] and z['method']==x['method_id'])
    rec(stage='FGO strict 20261004',sequence=x['sequence_id'],method=x['method_id'],configuration='PAPER_CONTRACT',case_id='natural',comparison_role='system route / strict one-init continuity',status=x['status'],input_scope=x['input_layer'],support=x['matched_epoch_count']+'/'+x['expected_epoch_count'],yaw_rmse_deg=x['yaw_rmse_deg'],horizontal_rmse_m=x['horizontal_rmse_m'],up_rmse_m=x['vertical_rmse_m'],source_table=str(D/'hext/FGO_REPRODUCTION_FIX_20261004/METRICS.csv'),native_record=rr['run_path'],error_series=x['error_path'].replace('<FGO_EVALUATION_ROOT>',str(froot/'evaluation')),reading_depth='actual RUN and entire STATES; both hashes checked',reuse_note='source snapshot + per-file uncommitted overlay defines executed identity')
for seq in ['BY2','BY2H','BY2O']:
    for x in tab(D/f'FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/evaluation/{seq}/METRICS.csv','registry exact source rows'):
        if x['support_role']!='PRIMARY_DYNAMIC_ONLY' or x['support']!='OWN_VALID':continue
        method=x['method_id']; p=seg/f'runs/{seq}/OISAM/SEGMENTED_DIAGNOSTIC/RUN.json' if method=='OISAM' else froot/f'runs/{seq}/{method}/PAPER_CONTRACT/RUN.json'
        rec(stage='FGO segmented 20261004',sequence=seq,method=method,configuration='PRIMARY_DYNAMIC_ONLY',case_id='natural gap blocks',comparison_role='same physical point and support / separate gap policy',status=x['status'],input_scope=x['input_layer'],support=x['matched_epoch_count']+'/'+x['expected_epoch_count'],yaw_rmse_deg=x['yaw_rmse_deg'],horizontal_rmse_m=x['horizontal_rmse_m'],up_rmse_m=x['vertical_rmse_m'],source_table=str(D/f'FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/evaluation/{seq}/METRICS.csv'),native_record=str(p),error_series=str(seg/f'evaluation/{seq}/{method}_PRIMARY_DYNAMIC_ONLY_ERRORS.csv'),reading_depth='actual 3 OiSAM RUN/BLOCKS/events; all 9 error CSV read',reuse_note='only OiSAM adds 3 native; Wen/GNC reuse strict native; prior-only excluded')
for seq,start,n,status in [('BY2','C00','77/275','ALGORITHM_FAILURE_DIVERGED'),('BY2H','CONTRACT_START','2/271','COMPLETED_LOW_SUPPORT'),('BY2O','FILE_START','5/378','ALGORITHM_FAILURE_DIVERGED')]:
    p=S/f'CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/RUNS/{seq}__GINAV__NONE__{start}__NA'
    rec(stage='HX02 official GINav',sequence=seq,method='GINav SPP/INS LC',configuration=start,case_id='natural',comparison_role='raw SPP/INS route boundary',status=status,input_scope='single GNSS RAWX/SFRBX + Go2 IMU + TDCP alignment',support=n,yaw_rmse_deg='11.662' if seq=='BY2H' else '',horizontal_rmse_m='2.8949' if seq=='BY2H' else '',source_table=str(D/'hext/HX02/EXTERNAL_FIVE_CATEGORY_TABLE.csv'),native_record=str(p/'native/GINAV_RUN.json'),error_series=str(p/'eval/GINAV_EVALUATION.json'),reading_depth='actual command/native/D8/eval JSON plus stdout (empty)',reuse_note='earlier archive stop superseded by real native; failure remains distinct from native exit zero')
rec(stage='FGO segmented control',sequence='BY2',method='OiSAM strict vs segmented',case_id='no gap control',comparison_role='same data/model implementation-equivalence control',status='PASS_EXACT',input_scope='same source and no real gap; no extra A1 initialization',support='285 native states plus state labels and old event fields',source_table=str(D/'FGO_COMPLETE_AUDIT_20261004/SEGMENTED_NATIVE_CHECKPOINT/BY2_NO_RESTART_CONTROL.json'),reading_depth='full control JSON and actual states',reuse_note='existing control; not new experiment')
save('EXPERIMENTS.csv',registry)
save('SOURCES_READ.csv',sources)
print('registry_rows',len(registry))
