#!/usr/bin/env python3
"""One registered candidate native call; no baseline replay, evaluator or controller."""
import argparse, fcntl, importlib.util, json, os, re, shutil, signal, subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'v3_mechanism'
spec=importlib.util.spec_from_file_location('previous_single_slot_utilities',OLD/'replay_one.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)  # utilities only; main is guarded.

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--roots',type=Path,required=True)
    p.add_argument('--candidate-id',choices=['N12_ONLY','N16_ONLY','N09_RP_ONLY'],required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    aliases=json.loads(a.roots.read_text())['aliases'];repo=Path(aliases['<CODE_ROOT>'])
    lock=open(Path(aliases['<VALIDATION_BUILD_ROOT>'])/'NATIVE.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    queue=u.read_csv(HERE/'CANDIDATE_QUEUE.csv');ledger=HERE/'RUN_MANIFEST.csv';rows=u.read_csv(ledger)
    item=next(x for x in queue if x['candidate_id']==a.candidate_id and x['baseline_run_id']==a.run_id)
    row=next(x for x in rows if x['slot_id']==item['slot_id'])
    if row['status']!='PLANNED' or int(row['native_attempts']) or sum(int(x['native_attempts']) for x in rows)>=10:
        raise RuntimeError('already attempted or bounded queue exhausted; no retry mode')
    ready_path=HERE/'candidates'/a.candidate_id/'READY.json';ready=json.loads(ready_path.read_text())
    u.assert_committed(repo,[HERE/'V3_DEFINITION_DECISIONS.md',HERE/'CANDIDATE_QUEUE.csv',Path(__file__),ready_path]+
        [OLD/n for n in ['replay_one.py','QUALIFIED_INPUTS.csv','INPUT_USES.csv','INPUT_STAT_CHECKPOINT.csv',
                         'REPLAY_MANIFEST.csv','HISTORICAL_OUTPUT_HASHES.csv']])
    assert ready['candidate_id']==a.candidate_id and ready['native_tests_passed'] is True
    if len(ready['source_patch_sha256'])!=64:raise RuntimeError('missing scientific patch identity')
    binary=u.resolve(ready['binary'],aliases)
    if u.sha(binary)!=ready['binary_sha256']:raise RuntimeError('candidate executable pin mismatch')
    config=u.resolve(item['original_config'],aliases)
    if u.sha(config)!=item['original_config_sha256']:raise RuntimeError('original config pin mismatch')
    old_runs=u.read_csv(OLD/'REPLAY_MANIFEST.csv')
    for variant in ['original','observed']:
        prior=next(x for x in old_runs if x['run_id']==a.run_id and x['variant']==variant)
        if prior['status']!='COMPLETED_BYTE_IDENTICAL':raise RuntimeError('previous baseline identity not closed')
    qualified={x['input_id']:x for x in u.read_csv(OLD/'QUALIFIED_INPUTS.csv')}
    checkpoint={x['input_id']:x for x in u.read_csv(OLD/'INPUT_STAT_CHECKPOINT.csv')}
    input_paths=[]
    for use in u.read_csv(OLD/'INPUT_USES.csv'):
        if use['run_id']!=a.run_id:continue
        path=u.resolve(use['source_path'],aliases);stat=path.stat();record=checkpoint[use['input_id']]
        if path.is_symlink() or stat.st_size!=int(qualified[use['input_id']]['bytes']) or any(getattr(stat,k)!=int(record[k]) for k in ['st_dev','st_ino','st_mtime_ns']):
            raise RuntimeError('qualified input stat changed: '+use['source_path'])
        input_paths.append(str(path))
    out=u.resolve(row['output_root'],aliases);root=Path(aliases['<VALIDATION_ROOT>']).resolve()
    if row['output_root']!=item['candidate_outputs'] or root not in out.resolve().parents or any(x.is_symlink() for x in [out,*out.parents]):
        raise RuntimeError('output containment/symlink failure')
    tracer=shutil.which('strace')
    if not tracer:raise RuntimeError('strace unavailable; no native call')
    if shutil.disk_usage(root).free<2_000_000_000:raise RuntimeError('insufficient free space for retained evidence')
    if a.check_only:
        print(json.dumps({'slot_id':item['slot_id'],'preflight':'PASS','native_calls':0,
                          'qualified_dependency_uses':len(input_paths),'config_sha256':item['original_config_sha256'],
                          'binary_sha256':ready['binary_sha256'],'candidate_output_exists':out.exists()}))
        if out.exists():raise RuntimeError('output already exists; no native invocation')
        return
    out.mkdir(parents=True,exist_ok=False);obs=out/'observer';obs.mkdir()
    env=os.environ.copy();env.update(LEGSA_V3_OBSERVER_DIR=str(obs),LEGSA_V3_OBSERVER_RUN_ID=item['slot_id'])
    env.update({k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']})
    argv=[str(binary),'--config',str(config),'--output-dir',str(out),'--debug-update-timeline','--debug-output-dir',str(out),'--debug-max-rows','1000000']
    trace=out/'NATIVE_ACCESS.strace';command=[tracer,'-f','-s','4096','-e','trace=openat,execve','-o',str(trace)]+argv
    row.update(status='STARTED',native_attempts='1',native_calls='UNKNOWN',binary_sha256=ready['binary_sha256'],
               source_patch_sha256=ready['source_patch_sha256'])
    receipt={k:item[k] for k in ['slot_id','candidate_id','baseline_run_id','case_id','method_id','data_mode']}
    receipt.update(synthetic_data_used=item['synthetic_data_used']=='True',semisynthetic_data_used=item['semisynthetic_data_used']=='True',
        observation_origin='new_candidate_closed_loop',original_V3_overwritten=False,baseline_native_calls=0,evaluator_calls=0,
        provider_generator_calls=0,automatic_retry_count=0,started_utc=u.now(),argv=[u.alias(x,aliases) for x in argv],
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),binary_sha256=row['binary_sha256'],
        config_sha256=item['original_config_sha256'],ready_sha256=u.sha(ready_path),input_qualification='PREVIOUS_HASH_VERIFIED_CURRENT_STAT_CHECKED')
    u.write_csv(ledger,rows);(out/'STARTED.json').write_text(json.dumps(receipt,indent=2)+'\n')
    try:
        with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
            process=subprocess.Popen(command,cwd=out,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
            try:code=process.wait(timeout=1800)
            except BaseException:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                raise
        row['exit_code']=str(code);audit=u.audit_access(trace,out,binary,aliases)
        successful_opens=[line for line in trace.read_text(errors='replace').splitlines()
                          if 'openat(' in line and re.search(r'\)\s+=\s+\d+',line)]
        audit['successful_open_parse_complete']=len(successful_opens)==len(audit['successful_open_records'])
        # Original helpers detect writes/raw/reference. Exact reference and project read allowlist add a second gate.
        read_allowed={u.alias(x,aliases) for x in input_paths+[str(binary),str(config)]}
        unexpected=[]
        for record in audit['successful_open_records']:
            path=record['path'];flags=record['flags']
            if not path.startswith(('/', '<')):unexpected.append(record);continue
            if any(t in flags for t in ['O_WRONLY','O_RDWR','O_CREAT','O_TRUNC']):continue
            physical=u.resolve(path,aliases) if path.startswith('<') else Path(path)
            if str(physical)==aliases['<V3_REFERENCE>']:unexpected.append(record)
            elif any(str(physical).startswith(aliases[k]+'/') for k in ['<RAW_ROOT>','<CLEAN_ROOT>','<CODE_ROOT>','<MECHANISM_BUILD_ROOT>','<VALIDATION_BUILD_ROOT>']):
                if path not in read_allowed and not str(physical).startswith(str(out)+'/'):unexpected.append(record)
        audit['unexpected_project_reads']=unexpected;audit['passed']=audit['passed'] and not unexpected and audit['successful_open_parse_complete']
        (out/'ACCESS_REVIEW.json').write_text(json.dumps(audit,indent=2)+'\n');row['native_calls']=str(audit['native_exec_count'])
        hashes=[]
        for hist in u.read_csv(OLD/'HISTORICAL_OUTPUT_HASHES.csv'):
            if hist['run_id']!=a.run_id:continue
            file=out/hist['filename'];current=u.sha(file) if file.is_file() else ''
            hashes.append(dict(filename=hist['filename'],candidate_sha256=current,baseline_recorded_sha256=hist['recorded_sha256'],
                bytes=file.stat().st_size if file.exists() else '',comparison='BYTE_IDENTICAL' if current==hist['recorded_sha256'] else 'DIFFERENT_OR_MISSING',old_payload_read=False))
        u.write_csv(out/'OUTPUT_HASH_COMPARISON.csv',hashes)
        missing=[x['filename'] for x in hashes if not x['candidate_sha256']]
        row['status']=('COMPLETED' if audit['passed'] and len(hashes)==5 and not missing else 'COMPLETED_REVIEW_REQUIRED') if code==0 else 'NATIVE_FAILED'
        receipt.update(exit_code=code,access_passed=audit['passed'],native_exec_count=audit['native_exec_count'],output_hashes=hashes)
        if (out/'RUN_MANIFEST.json').exists():
            current=json.loads((out/'RUN_MANIFEST.json').read_text());receipt['native_manifest']=current
            baseline=json.loads((u.resolve(item['baseline_outputs'],aliases)/'RUN_MANIFEST.json').read_text())
            flags=['data_mode','synthetic_data_used','semisynthetic_data_used','trace_used_online',
                   'receiver_imu_as_body_imu','final_v23_output_solver_input','LegSA_output_solver_input',
                   'per_case_tuning','output_only_correction','epoch_deleted_for_metric','old_runtime_input_count']
            flags+=['trace_solver_input','trace_used_for_initialization','starttime','endtime','imudatalen','imudatarate',
                    'actual_solver_input_paths','actual_solver_input_roles','measurement_update_order','antlever_m',
                    'solver_output_reference_point','common_initialization','common_initialization_source',
                    'common_initialization_covariance_diagonal_internal','algorithm_id','ablation_variant',
                    'source_caps','source_aware_source_configs','raw_doppler_backend_source_hashes',
                    'raw_doppler_R_scale','raw_doppler_time_tolerance_sec','raw_doppler_min_sat','raw_doppler_residual_gate_mps',
                    'go2_attitude_prior_std_roll_deg','go2_attitude_prior_std_pitch_deg','go2_attitude_prior_time_tolerance_sec',
                    'go2_velocity_prior_time_tolerance_sec','go2_horizontal_velocity_prior_mode','go2_horizontal_velocity_prior_std_scale']
            flags += [k for k in baseline if k.startswith(('init_','enable_','disable_','yaw_std_','yaw_res_'))]
            flags += [k for k in baseline if k.startswith('source_aware_') and k not in [
                'source_aware_trace_rows','source_aware_update_count_by_source','source_aware_reject_count_by_source',
                'source_aware_R_scale_p50_p95_max_by_source','source_aware_R_scale_stats_by_source','source_aware_spike_response_evaluated',
                'source_aware_evaluation_count','source_aware_weight_changed_count']]
            identity={k:{'baseline':baseline.get(k),'candidate':current.get(k),'present':k in baseline and k in current,
                          'same':k in baseline and k in current and baseline[k]==current[k]} for k in flags}
            receipt['data_role_manifest_check']=identity
            if not all(v['same'] for v in identity.values()):row['status']='COMPLETED_REVIEW_REQUIRED' if code==0 else row['status']
        elif code==0:row['status']='COMPLETED_REVIEW_REQUIRED'
    except BaseException as exc:
        row.update(status='TECHNICAL_FAILURE_RETAINED',reason=u.alias(type(exc).__name__+': '+str(exc),aliases));receipt['exception']=row['reason']
        raise
    finally:
        if row['native_calls']=='UNKNOWN':row['native_calls']=str(u.audit_access(trace,out,binary,aliases)['native_exec_count']) if trace.exists() else '0'
        receipt.update(status=row['status'],finished_utc=u.now(),native_exec_count=row['native_calls'])
        (out/'CANDIDATE_RECEIPT.json').write_text(u.alias(json.dumps(receipt,indent=2),aliases)+'\n');u.write_csv(ledger,rows)
        print(json.dumps({k:row[k] for k in ['slot_id','status','native_calls','exit_code','output_root']}))
if __name__=='__main__':main()
