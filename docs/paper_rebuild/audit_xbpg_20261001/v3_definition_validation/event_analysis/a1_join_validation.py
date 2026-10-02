#!/usr/bin/env python3
"""N09 A1 cache-only text-key reconciliation; no event/provider/evaluator reads."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import sqlite3

HERE=Path(__file__).resolve().parent
RUNS=('ADD_RUN_00105','ADD_RUN_00103')
SOURCE='go2_attitude_roll_pitch'


def exact_key(gnss_id,source,time_literal):
    if isinstance(time_literal,bool) or time_literal is None:
        raise ValueError('UNKNOWN_OR_NONFINITE_TIME')
    try:
        time=Decimal(str(time_literal))
        valid=time.is_finite() and math.isfinite(float(time))
    except (ValueError,TypeError,OverflowError,InvalidOperation):
        raise ValueError('UNKNOWN_OR_NONFINITE_TIME')
    if not valid:raise ValueError('UNKNOWN_OR_NONFINITE_TIME')
    return int(gnss_id),source,time


def unique_lookup(items):
    result={}
    for item in items:
        key=exact_key(item['gnss_input_seq'],item['source'],item['measurement_time'])
        if key in result:raise ValueError('DUPLICATE_NUMERIC_KEY')
        result[key]=item
    return result


def self_test():
    tests=[]
    def check(name,value):tests.append(dict(check=name,status='PASS' if value else 'FAIL'))
    check('197_and_197_0_match',exact_key(1,SOURCE,'197')==exact_key(1,SOURCE,'197.0'))
    check('different_actual_time_no_match',exact_key(1,SOURCE,'197')!=exact_key(1,SOURCE,'197.0000000000001'))
    check('different_GNSS_identity_no_match',exact_key(1,SOURCE,'197')!=exact_key(2,SOURCE,'197'))
    check('different_source_no_match',exact_key(1,SOURCE,'197')!=exact_key(1,'other','197'))
    for value in [None,'UNKNOWN','NaN','Infinity','-Infinity',True]:
        try:exact_key(1,SOURCE,value)
        except ValueError:ok=True
        else:ok=False
        check('refuse_'+str(value),ok)
    try:unique_lookup([dict(gnss_input_seq=1,source=SOURCE,measurement_time='197'),dict(gnss_input_seq=1,source=SOURCE,measurement_time='197.0')])
    except ValueError:ok=True
    else:ok=False
    check('duplicate_numeric_key_refused',ok)
    payload=dict(status='PASS' if all(t['status']=='PASS' for t in tests) else 'FAIL',checks=tests,
        validation_kind='SYNTHETIC_DERIVED_JOIN_HELPER_ONLY',new_test_script_processes=1,
        native_calls=0,evaluator_calls=0,raw_event_payload_opens=0,provider_reads=0,
        data_mode='synthetic_helper_validation',synthetic_data_used=True,semisynthetic_data_used=False,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    path=HERE/'summaries/N09_RP_ONLY__ADD_RUN_00105/A1_JOIN_VALIDATION_TEST_RECEIPT.json'
    with path.open('x') as stream:json.dump(payload,stream,indent=2);stream.write('\n')
    print(json.dumps(payload));return 0 if payload['status']=='PASS' else 1


def run(roots_path,run_id):
    aliases=json.loads(roots_path.read_text())['aliases']
    root=Path(aliases['<VALIDATION_ROOT>'])/'analysis'
    public=HERE/'summaries'/('N09_RP_ONLY__'+run_id)
    target=public/'A1_JOIN_VALIDATION.csv'
    receipt_path=public/'A1_JOIN_VALIDATION_RECEIPT.json'
    if target.exists() or receipt_path.exists():raise ValueError('REFUSE_RECONCILIATION_OVERWRITE')
    cache_dirs={side:root/'event_cache'/prefix for side,prefix in [('baseline','BASELINE__'+run_id),('candidate','N09_RP_ONLY__'+run_id)]}
    dbs={}
    pins={}
    for side,directory in cache_dirs.items():
        if directory.is_symlink() or (directory/'cache.sqlite').is_symlink():raise ValueError('SYMLINK_REFUSED')
        meta=json.loads((directory/'SCAN_RECEIPT.json').read_text())
        if meta['stream_status']!='COMPLETE' or meta['analysis_status']!='VALIDATED':raise ValueError('CACHE_NOT_COMPLETE_VALIDATED')
        expected=run_id if side=='baseline' else 'N09_RP_ONLY__'+run_id
        if meta['run_id']!=expected:raise ValueError('CACHE_IDENTITY_MISMATCH')
        st=(directory/'cache.sqlite').stat()
        for field,value in meta['cache_stat'].items():
            if getattr(st,field)!=value:raise ValueError('CACHE_STAT_CHANGED')
        dbs[side]=sqlite3.connect('file:'+str(directory/'cache.sqlite')+'?mode=ro',uri=True)
        pins[side]=dict(source_sha256=meta['source_sha256'],analyzer_sha256=meta['analyzer_sha256'])
    originals=list(csv.DictReader((root/'comparisons'/('N09_RP_ONLY__'+run_id)/'ORIGINAL_RP_OPPORTUNITIES.csv').open()))
    by_id={int(row['gnss_input_seq']):row for row in originals}
    if len(by_id)!=len(originals):raise ValueError('DUPLICATE_ORIGINAL_GNSS_ID')
    candidate=[]
    for key,event_seq,data in dbs['candidate'].execute('SELECT stable_key,event_seq,data FROM measurement WHERE stable_key LIKE ?',('%"'+SOURCE+'"%',)):
        item=json.loads(data,parse_float=str,parse_int=str)
        item['original_string_key']=key;item['cache_event_seq']=event_seq;candidate.append(item)
    lookup=unique_lookup(candidate)
    baseline=[]
    for gnss_id,sqlite_time,data in dbs['baseline'].execute('SELECT gnss_seq,time,data FROM gnss ORDER BY gnss_seq'):
        item=json.loads(data,parse_float=str,parse_int=str)
        if item['all_flags_false'] and item['rp_preinnovation_qualified']:
            item['source']=SOURCE;item['sqlite_time']=sqlite_time;baseline.append(item)
    unique_lookup(baseline)
    if len(baseline)!=100 or set(by_id)!={int(x['gnss_input_seq']) for x in baseline}:raise ValueError('EXPECTED_A1_SCOPE_NOT_100')
    rows=[]
    for old in baseline:
        key=exact_key(old['gnss_input_seq'],SOURCE,old['measurement_time']);found=lookup.get(key)
        if found is None:raise ValueError('NUMERIC_EXACT_MATCH_MISSING:'+str(key))
        candidate_key=json.loads(found['original_string_key'],parse_float=str,parse_int=str)
        if exact_key(*candidate_key)!=key:raise ValueError('CANDIDATE_CONTEXT_AND_STABLE_KEY_DISAGREE')
        old_row=by_id[key[0]];old_constructed=json.dumps([key[0],SOURCE,old['sqlite_time']],separators=(',',':'))
        is_accepted=found['decision'].get('accepted') is True and bool(found.get('ekf',{}).get('after_pointer'))
        rows.append(dict(run_id=run_id,gnss_input_seq=key[0],source=SOURCE,
            window='[196.2,216.2)',baseline_cache_JSON_time_literal=old['measurement_time'],
            baseline_SQLite_time_literal=repr(old['sqlite_time']),original_CSV_time_literal=old_row['measurement_time'],
            candidate_cache_context_time_literal=found['measurement_time'],candidate_cache_key_time_literal=candidate_key[2],
            original_constructed_string_key=old_constructed,candidate_original_string_key=found['original_string_key'],
            string_key_equal=old_constructed==found['original_string_key'],finite_numeric_exact_equal=key==exact_key(found['gnss_input_seq'],SOURCE,found['measurement_time']),
            original_reported_attempts=old_row['candidate_RP_attempts'],original_reported_accepted=old_row['actual_accepted_updates'],
            corrected_unique_attempts=1,actual_accepted=is_accepted,actual_decision_reason=found['decision']['reason'],
            derived_join_status='TEXT_KEY_OMISSION_CORRECTED' if old_row['candidate_RP_attempts']=='0' else 'ORIGINAL_JOIN_CONFIRMED',
            baseline_event_pointer=json.dumps(old['pointer'],sort_keys=True,separators=(',',':')),
            candidate_attempt_pointer=json.dumps(found['attempt_pointer'],sort_keys=True,separators=(',',':')),
            candidate_decision_pointer=json.dumps(found['decision_pointer'],sort_keys=True,separators=(',',':')),
            candidate_EKF_after_pointer=json.dumps(found['ekf']['after_pointer'],sort_keys=True,separators=(',',':'))))
    for db in dbs.values():db.close()
    with target.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    payload=dict(status='DERIVED_JOIN_CORRECTION_VALIDATED',run_id=run_id,candidate_id='N09_RP_ONLY',
        rows=len(rows),original_reported_attempts=sum(int(x['original_reported_attempts']) for x in rows),
        corrected_unique_attempts=len(rows),corrected_actual_accepted=sum(x['actual_accepted'] for x in rows),
        text_key_omissions=[dict(gnss_input_seq=x['gnss_input_seq'],baseline_SQLite_time_literal=x['baseline_SQLite_time_literal'],candidate_cache_context_time_literal=x['candidate_cache_context_time_literal']) for x in rows if x['derived_join_status']=='TEXT_KEY_OMISSION_CORRECTED'],
        matching='gnss_input_seq + exact source + finite Decimal numeric equality; zero tolerance; keys unique',
        original_summary_preserved=True,original_analyzer_modified=False,raw_event_payload_opens=0,
        native_calls=0,evaluator_calls=0,provider_reads=0,data_mode='semisynthetic',synthetic_data_used=False,semisynthetic_data_used=True,
        source_pins=pins,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        correction_scope='Text-key omission in this round auxiliary analyzer, not an original V3 run-data or algorithm defect.',
        literal_scope='Literals preserved from completed cache JSON/SQLite/derived CSV; no original event stream reread.')
    with receipt_path.open('x') as stream:json.dump(payload,stream,indent=2);stream.write('\n')
    print(json.dumps({k:payload[k] for k in ['status','run_id','rows','original_reported_attempts','corrected_unique_attempts','corrected_actual_accepted']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--roots',type=Path);parser.add_argument('--run-id',choices=RUNS)
    args=parser.parse_args()
    if args.self_test:raise SystemExit(self_test())
    if not args.roots or not args.run_id:parser.error('actual validation requires --roots and one --run-id')
    run(args.roots,args.run_id)
