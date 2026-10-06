from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
CODE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
STAGE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z')
EVALUATOR=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(name,data):
    with (STAGE/name).open('x') as f:json.dump(data,f,indent=2)
if sys.argv[1:]==['--launch']:
    env={**os.environ,'PYTHONPATH':str(CODE/'src'),'PYTHONUNBUFFERED':'1'}
    with (STAGE/'CONTROLLER.stdout.log').open('x') as out,(STAGE/'CONTROLLER.stderr.log').open('x') as err:
        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve())],cwd=CODE,env=env,
                           stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
    emit('CONTROLLER_LAUNCH.json',{'pid':p.pid,'pgid':p.pid,'controller':str(Path(__file__).resolve()),
        'controller_sha256':sha(__file__),'preregistration_sha256':sha(STAGE/'PREREGISTRATION.json'),
        'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'science_sources_frozen':True,'all_native_seal_required_before_any_offline_reference_read':True})
    print(json.dumps({'status':'LAUNCHED','pid':p.pid,'stage':str(STAGE)}));sys.exit(0)
plan=json.loads((STAGE/'PREREGISTRATION.json').read_text())
admission=json.loads((STAGE/'ALL_135_NATIVE_LOADER_ADMISSION.json').read_text())
assert admission['status']=='ALL_135_CORRECTED_CONFIGS_NATIVE_LOADER_ADMITTED'
assert admission['preregistration_sha256']==sha(STAGE/'PREREGISTRATION.json')
assert len(plan['runs'])==135 and plan['native_configurations']==135
prefix=[sys.executable,'-m','legsa_gins.paper_rebuild.imu_contract_repair']
common=['--stage',str(STAGE),'--code',str(CODE)]
for phase,extras in [('native',[]),('evaluate',['--evaluator',str(EVALUATOR),
    '--raw-root','/mnt/g/LegSA-GINS-project/data/raw',
    '--clean-root','/mnt/g/LegSA-GINS-project/clean_rebuild_202607'])]:
    if phase=='evaluate':
        sealed=json.loads((STAGE/'ALL_NATIVE_SEALED.json').read_text())
        assert sealed['status']=='SEALED' and len(sealed['runs'])==135
        assert sealed['preregistration_sha256']==sha(STAGE/'PREREGISTRATION.json')
        assert {r['run_id'] for r in sealed['runs']}=={r['run_id'] for r in plan['runs']}
        assert all(r['status']=='COMPLETED_SEGMENTED' and r['trace_open_count']==0 and
                   all(c['status']=='COMPLETED' and c['trace_open_count']==0 for c in r['children']) for r in sealed['runs'])
        emit('ALL_135_NATIVE_VERIFIED_BEFORE_OFFLINE.json',{'status':'ALL_135_NATIVE_SEALED_NO_ONLINE_TRACE_READS',
            'native_seal_sha256':sha(STAGE/'ALL_NATIVE_SEALED.json'),
            'preregistration_sha256':sha(STAGE/'PREREGISTRATION.json'),'native_configurations':135,
            'native_children':135,'online_trace_open_count':0,
            'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    argv=prefix+[phase]+common+extras
    emit(phase.upper()+'_CONTROLLER_START.json',{'argv':argv,'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    with (STAGE/(phase.upper()+'.stdout.log')).open('x') as out,(STAGE/(phase.upper()+'.stderr.log')).open('x') as err:
        r=subprocess.run(argv,cwd=CODE,stdout=out,stderr=err)
    emit(phase.upper()+'_CONTROLLER_COMPLETE.json',{'exit_code':r.returncode,
         'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    if r.returncode:raise RuntimeError(phase+' failed; preserved stop, no retry')
results=json.loads((STAGE/'CORRECTED_RESULTS.json').read_text())
assert len(results)==135 and {r['run_id'] for r in results}=={r['run_id'] for r in plan['runs']}
emit('CONTROLLER_COMPLETE.json',{'status':'ALL_135_NATIVE_AND_OFFLINE_COMPLETED',
    'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'result_count':135,'accepted_count':sum(r['status']=='COMPLETED_SEGMENTED' for r in results),
    'unavailable_count':sum(r['status']!='COMPLETED_SEGMENTED' for r in results),
    'native_seal_sha256':sha(STAGE/'ALL_NATIVE_SEALED.json'),'results_sha256':sha(STAGE/'CORRECTED_RESULTS.json')})
