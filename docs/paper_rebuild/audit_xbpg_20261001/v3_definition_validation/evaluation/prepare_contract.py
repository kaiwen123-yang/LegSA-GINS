#!/usr/bin/env python3
"""Read only small source/result metadata; prepare 17 slots without evaluator calls."""
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CODE=HERE.parents[4]
PREFIX='src/legsa_gins/paper_rebuild/'
PIN_VALUES={
 PREFIX+'protocol_v3/evaluation_process.py':'179c354a8d2500791d0b2cfb1c89b815fdf25575d66cac4b44eb87967b6a4489',
 'scripts/paper_rebuild/v3_evaluator_observer/sitecustomize.py':'89d894869e33c51c269a15ddb65b4aef9b2e0191a0114741284ee65d5a522925',
 PREFIX+'clean5_sequence/evaluator_capture.py':'beb6ff36022866795c608a7ebbc8c356698eaf614ba22b98cbb57b3b7f4f6c8c',
 PREFIX+'clean6_canonical_v2/evaluation.py':'8dfacf094879e7c091f1ddf1d5dcb3164f43923dc0903734cb6d29e05eeccc10',
 PREFIX+'clean5_parity/evaluation.py':'cfd8b276c9fe663f823a5846dab6a54de72664688b798a6591f168dd86044d0a',
 PREFIX+'clean5_parity_p04/evaluation.py':'533b3b3bf0f6b1361fcd914c8011335aaa4c57ac7f29b41b33eeeab594793352',
 PREFIX+'canonical541/offline_eval_aggregate.py':'d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16',
 PREFIX+'horizontal_literature/shared_raw_backend.py':'d72548fb9cea3f8d6075bd231ba9a2bb970f71382006edbec045a4c7ea8f6e5a'}
SUPPORT=['evaluation_status','matched_epoch_count','output_epoch_count','unmatched_epoch_count',
 'coverage_ratio','reference_epoch_count','time_start','time_end','sequence_window_start_s','sequence_window_end_s',
 'reference_velocity_supported','reference_is_independent_ground_truth','finite_output','finite_ratio']
METRIC_PREFIXES=('north_','east_','up_','roll_','pitch_','yaw_','horizontal_','position_3d_')


def main():
    roots=json.loads((CODE/'configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json').read_text())['aliases']
    queue=list(csv.DictReader((HERE.parent/'CANDIDATE_QUEUE.csv').open()))
    unique={r['baseline_run_id']:r for r in queue}
    assert len(queue)==10 and len(unique)==7
    for name in ['FROZEN_PINS.json','BASELINE_EXPECTATIONS.json','EVAL_MANIFEST.csv']:
        if (HERE/name).exists():raise RuntimeError('refuse preparation overwrite: '+name)
    pins=[]
    for path,pin in PIN_VALUES.items():
        actual=hashlib.sha256((CODE/path).read_bytes()).hexdigest()
        assert actual==pin,path
        pins.append(dict(path='<CODE_ROOT>/'+path,sha256=pin,verification='NEW_LOCAL_HASH_MATCH_TO_SUPERVISOR_FROZEN_PIN',frozen_runner_commit='7d43b9af26120ed5dde21f53e515386361072ba6'))
    for path in ['clean5_sequence/io_audit.py','subprocess_guard.py','manifest.py','evidence.py','clean6_canonical_v2/resources.py']:
        actual=hashlib.sha256((CODE/PREFIX/path).read_bytes()).hexdigest()
        pins.append(dict(path='<CODE_ROOT>/'+PREFIX+path,sha256=actual,verification='NEW_LOCAL_PIN; supervisor included file in verified frozen source set',frozen_runner_commit='7d43b9af26120ed5dde21f53e515386361072ba6'))
    pins.append(dict(path='<FROZEN_EVALUATOR>',sha256='aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da',verification='SUPERVISOR_NEW_VERIFICATION; runner verifies again before each explicit slot',frozen_runner_commit='external_archived_evaluator'))
    (HERE/'FROZEN_PINS.json').write_text(json.dumps(dict(files=pins,reference_path='<V3_REFERENCE>',reference_sha256='ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c',reference_read_policy='child existing handle only; parent stat permitted; never parent hash'),indent=2)+'\n')
    expected={}
    for rid,item in sorted(unique.items()):
        relative='04_EVALUATION/'+('' if item['group']=='C00' else 'V3R_CONTINUATION/')+rid+'/v3/EVALUATION_RESULT.json'
        source=Path(roots['<V3_ROOT>'])/relative
        original=json.loads(source.read_text(),parse_float=str)['row']
        assert original['status']=='COMPLETED' and original['metrics_admitted'] is True
        assert original['case_id']==item['case_id'] and original['method_id']==item['method_id']
        keys=[k for k in original if k.startswith(METRIC_PREFIXES) or k in SUPPORT]
        columns={k:dict(source_value=original[k],row_key='#/row/'+k,comparison_kind='exact' if isinstance(original[k],(bool,int)) or k=='evaluation_status' else 'time' if k in {'time_start','time_end','sequence_window_start_s','sequence_window_end_s'} else 'numeric') for k in keys}
        capture_path=source.parent/'FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json'
        capture=json.loads(capture_path.read_text())
        expected[rid]=dict(source_path='<V3_ROOT>/'+relative,source_json_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            capture_source_path='<V3_ROOT>/'+str(capture_path.relative_to(Path(roots['<V3_ROOT>']))),capture_source_sha256=hashlib.sha256(capture_path.read_bytes()).hexdigest(),
            native_nav_sha256=original['native_nav_sha256'],std_sha256=original['std_sha256'],evaluator_nav_sha256=original['evaluator_nav_sha256'],
            config_sha256=original['config_hash'],columns=columns,reference_cleaned_epoch_count=capture['consistency']['reference_cleaned_epoch_count'],
            recorded_hashes_are_newly_verified_payload_hashes=False)
    (HERE/'BASELINE_EXPECTATIONS.json').write_text(json.dumps(expected,indent=2,ensure_ascii=False)+'\n')
    slots=[('BASELINE',r) for r in sorted(unique.values(),key=lambda r:r['baseline_run_id'])]+[(r['candidate_id'],r) for r in queue]
    rows=[]
    for variant,item in slots:
        rid=item['baseline_run_id']
        rows.append(dict(slot_id=variant+'__'+rid,candidate_id=variant,run_id=rid,case_id=item['case_id'],group=item['group'],method_id=item['method_id'],status='PLANNED_NOT_INVOKED',
            evaluator_invocation_attempts=0,evaluator_child_execs=0,reference_child_opens=0,baseline_gate='NOT_CHECKED',
            output_root='<VALIDATION_ROOT>/evaluations/'+variant+'/'+rid,source_result=expected[rid]['source_path'],
            data_mode=item['data_mode'],synthetic_data_used=item['synthetic_data_used'],semisynthetic_data_used=item['semisynthetic_data_used'],reason=''))
    with (HERE/'EVAL_MANIFEST.csv').open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    print(json.dumps(dict(prepared_slots=len(rows),baseline_identities=len(expected),candidate_identities=len(queue),reference_payload_reads=0,evaluator_calls=0,native_calls=0)))


if __name__=='__main__':main()
