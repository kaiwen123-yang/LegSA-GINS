"""Read-only trace from figure CSVs to H5/H6 native evidence; never run a solver."""
from pathlib import Path
import hashlib,json,subprocess,math
import pandas as pd
import numpy as np
import yaml

OUT=Path(__file__).parent
ROOT=Path('/mnt/g/LegSA-GINS-project')
STAGE=ROOT/'clean_rebuild_202607/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF'
FIG=ROOT/'V3正文精修_20261012_R3/observability/source_data'
FOCUS=ROOT/'V3论文组图_20261008/focused_20261011/robot/source_data'
REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
RUNS=Path('/home/kaiwen/research/LegSA-GINS-RUNS')
H6ROOT=RUNS/'LSE01_H6_REAL_DATA_GAUGE_OBSERVABILITY_4B25FA6_V1'
H5ROOT=RUNS/'LSE01_H5_BY2_NATIVE_B1B3B0E_V3'
for sub in ['evidence','source_snapshots']:(OUT/sub).mkdir(parents=True,exist_ok=True)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

pins=[];rows=[]
paths=[STAGE/'08_BY2_NATIVE/01_PRIMARY_GO2_ALLAN_EQ61_FK10MM']+sorted((STAGE/'09_GAUGE_ENSEMBLE').glob('*/NAV.csv'))
paths=[p if p.is_dir() else p.parent for p in paths]
assert len(paths)==7
for d in paths:
    meta=json.loads((d/'NATIVE_SUMMARY.json').read_text())
    frozen=json.loads((d/'NATIVE_FREEZE.json').read_text())
    native=d/'NAV.csv'
    actual_hash=sha(native)
    expected=frozen['files']['NAV.csv']['sha256']
    assert actual_hash==expected
    nav=pd.read_csv(native,usecols=['timestamp_ns','row_index','r00','r10','px','py','pz'])
    assert len(nav)==meta['state_rows']==63277
    angle=np.rad2deg(np.unwrap(np.arctan2(nav.r10,nav.r00)))
    yaw=int(round(angle[0]))
    file=FIG/f'native_initial_yaw_{yaw:+04d}.csv.gz'
    figure=pd.read_csv(file)
    assert np.array_equal(nav.timestamp_ns,figure.timestamp_ns)
    position_error=float(np.max(np.abs(nav[['px','py','pz']].to_numpy()-figure[['local_x_m','local_y_m','local_z_m']].to_numpy())))
    yaw_error=float(np.max(np.abs(angle-figure.unwrapped_yaw_deg)))
    elapsed=(nav.timestamp_ns.to_numpy()-nav.timestamp_ns.iloc[0])/1e9
    elapsed_error=float(np.max(abs(elapsed-figure.elapsed_s)))
    assert position_error<1e-12 and yaw_error<1e-10 and elapsed_error<1e-12
    assert sha(file)==sha(FOCUS/file.name)
    is_h6=meta['run_id'].startswith('H6_')
    if is_h6:
        cfgpath=d/'NATIVE_CONFIG.yaml'
        cfg=yaml.safe_load(cfgpath.read_text())
        manifest=cfg['native_config_metadata']['scoped_source_files']
        command_status='Source-defined native argv; per-member stdout retained; original shell command line not located'
        stdout=cfg['native_config_metadata']['native_stdout']
        alpha=cfg['initial_gauge_yaw_deg']
        expected_yaw=cfg['expected_native_euler_yaw_offset_deg']
        assert yaw==expected_yaw==-alpha
        binary=H6ROOT/'00_BUILD/hartley_h5_runner'
        assert sha(binary)==meta['native_executable_sha256']
        config_argument=str(H6ROOT/'01_NATIVE_RAW'/meta['run_id']/'NATIVE_CONFIG.cfg')
        output_argument=str(H6ROOT/'01_NATIVE_RAW'/meta['run_id'])
        cache=Path(cfg['native_config_metadata']['cache_path'])
        argv=[str(binary),str(cache),config_argument,output_argument]
        config_hash=cfg['native_config_metadata']['config_hash']
        task='H6 six nonzero replays; base native anchor reused'
    else:
        cfgpath=d/'NATIVE_CONFIG.cfg'
        cfg=dict(x.split('=',1) for x in cfgpath.read_text().splitlines() if '=' in x)
        pm=json.loads((STAGE/'08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CACHE_MANIFEST.json').read_text())
        manifest=pm['scoped_source_manifest']['files']
        command_status='Native config, runtime and execution ledger retained; original shell command line not located'
        stdout='not in this published H5 config; native summary + EXECUTION_LEDGER retained'
        alpha=0;expected_yaw=0;config_hash=cfg['config_hash'];argv=[]
        task='H5 frozen primary run reused as zero-yaw member'
    runtime=pd.read_csv(d/'RUNTIME.csv').iloc[0]
    for rel,entry in manifest.items():
        pins.append(dict(run_id=meta['run_id'],source_rel=rel,declared_sha256=entry['sha256'],declared_size=entry['size']))
    row=dict(plotted_positive_z_euler_yaw_deg=yaw,registered_negative_gravity_axis_alpha_deg=alpha,
             run_id=meta['run_id'],algorithm=meta['backend_id'],stage=task,
             original_native_directory=str(d),original_NAV_sha256=actual_hash,
             original_freeze_sha256=sha(d/'NATIVE_FREEZE.json'),original_config_path=str(cfgpath),
             original_config_file_sha256=sha(cfgpath),native_config_body_hash=config_hash,
             native_summary_sha256=sha(d/'NATIVE_SUMMARY.json'),native_executable_sha256=meta['native_executable_sha256'],
             scoped_source_manifest_sha256=meta['scoped_source_manifest_sha256'],
             task_start_head=meta['task_start_head'],execution_source_was_precommit=meta['task_start_dirty_or_precommit'],
             raw_source_sha256=meta['raw_source_sha256'],cache_sha256=meta['cache_sha256'],
             state_rows=len(nav),propagation_calls=meta['propagation_calls'],contact_updates=meta['survivor_update_calls'],
             runtime_seconds=float(runtime.elapsed_seconds),plotted_file=str(file),plotted_file_sha256=sha(file),
             plotted_vs_native_max_position_difference_m=position_error,
             plotted_vs_native_max_yaw_difference_deg=yaw_error,plotted_vs_native_max_elapsed_difference_s=elapsed_error,
             extraction_csv_unchanged_from_20261011=True,native_stdout=stdout,
             native_argv_reconstruction=json.dumps(argv),command_evidence_status=command_status)
    rows.append(row)
    # Tiny original receipts copied, not 30MB NAV payloads or any unneeded run data.
    for f in ['NATIVE_SUMMARY.json','NATIVE_FREEZE.json','RUNTIME.csv',cfgpath.name]:
        (OUT/'evidence'/f'{meta["run_id"]}__{f}').write_bytes((d/f).read_bytes())

rows.sort(key=lambda x:x['plotted_positive_z_euler_yaw_deg'])
pd.DataFrame(rows).to_csv(OUT/'SEVEN_RUN_IDENTITIES.csv',index=False)
pd.DataFrame(pins).drop_duplicates().to_csv(OUT/'DECLARED_RUNTIME_SOURCE_PINS.csv',index=False)

# Recover committed scientific source at closure and explicitly check pins.
sources=[]
for commit,tag in [('4b25fa6337f4760557f501f102a38a1ac65c766e','H5'),('fbf771b3a43afcc11bc85596efc422a0cd7b9046','H6')]:
    chosen=[p for p in pins if (p['run_id'].startswith('H6_') if tag=='H6' else p['run_id'].startswith('H5_'))]
    seen=set()
    for p in chosen:
        rel=p['source_rel']
        if rel in seen:continue
        seen.add(rel)
        payload=subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)
        hs=hashlib.sha256(payload).hexdigest()
        name=tag+'__'+rel.replace('/','__')
        (OUT/'source_snapshots'/name).write_bytes(payload)
        sources.append(dict(stage=tag,closure_commit=commit,source_rel=rel,declared_runtime_sha256=p['declared_sha256'],
                            closure_source_sha256=hs,exact_runtime_pin_match=(hs==p['declared_sha256']),audit_snapshot='source_snapshots/'+name))
pd.DataFrame(sources).to_csv(OUT/'SOURCE_PIN_VERIFICATION.csv',index=False)
cache=H5ROOT/'00_PROVIDER/H5_INPUT_CACHE.bin'
assert sha(cache)==rows[0]['cache_sha256']
commit_info=[]
for commit in ['b1b3b0ec5e5d811c1658541a98b660f326500ac3','4b25fa6337f4760557f501f102a38a1ac65c766e','fbf771b3a43afcc11bc85596efc422a0cd7b9046']:
    x=subprocess.check_output(['git','show','-s','--format=%H%n%aI%n%cI%n%an%n%s',commit],cwd=REPO,text=True).splitlines()
    commit_info.append(dict(commit=x[0],author_date=x[1],committer_date=x[2],git_author=x[3],subject=x[4]))
dump(OUT/'COMMIT_DATES.json',commit_info)
dump(OUT/'AUDIT_RESULT.json',dict(algorithm_count=1,field_recording_count=1,retained_state_histories=7,
     h5_anchor_count=1,h6_nonzero_native_runs=6,temporary_zero_parity_run_additional_not_plotted=True,
     native_rows_per_history=63277,stored_native_rows_total=sum(r['state_rows'] for r in rows),
     all_seven_NAV_hashes_match_original_freezes=True,all_plotted_rows_match_specific_native_NAV=True,
     initial_yaw_axis_sign='plotted conventional +Z yaw = negative registered alpha about downward gravity',
     common_cache_live_sha256=sha(cache),current_native_executable_matches_runtime_pin=True,
     solver_called_during_this_audit=False,reference_opened=False,
     shell_command_history_status='Individual complete original shell command lines not located; native argument form and exact config/cache identities recovered',
     native_wallclock_start_status='No exact native UTC start field found in read summaries; commit dates are archival dates, not run timestamps',
     executor_identity='Project H5/H6 runner; Git records author kaiwen123-yang, not proof of who manually invoked shell',
     source_pin_scope='Native C++ runner and backend closure blobs checked against runtime hashes; wrapper/report source differences retained in source pin table'))
print(pd.DataFrame(rows)[['plotted_positive_z_euler_yaw_deg','registered_negative_gravity_axis_alpha_deg','run_id','state_rows','runtime_seconds','plotted_vs_native_max_position_difference_m']].to_string(index=False))
print(pd.DataFrame(sources)[['stage','source_rel','exact_runtime_pin_match']].to_string(index=False))
