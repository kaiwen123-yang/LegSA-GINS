#!/usr/bin/env python3
"""Structural checks of the new collection views, with no original payload reads."""
import argparse
import ast
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',type=Path,required=True);args=ap.parse_args()
    cfg=json.loads(args.roots.read_text());repo=Path(cfg['aliases']['<CODE_ROOT>']);out=repo/'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_hx';full=Path(cfg['aliases']['<EXT_REPRO_ROOT>'])/'existing_hx_full'
    def rows(p):
        with p.open(newline='') as f:return list(csv.DictReader(f))
    public=rows(out/'EXISTING_HX_INDEX.csv');original=rows(full/'EXISTING_HX_INDEX.csv');runrows=rows(out/'EXISTING_HX_RUNS.csv');files=rows(out/'EXISTING_HX_FILES.csv');tables=rows(out/'EXISTING_HX_TABLES.csv');inputs=rows(out/'INPUT_LOCATIONS.csv')
    checks=[]
    def check(name, passed, actual):
        checks.append({'name':name,'passed':bool(passed),'actual':actual})
    check('public_record_ids_unique',len({r['record_id'] for r in public})==len(public),len(public))
    expected_runs={r['metric_source'] for r in original if r['record_kind']=='RUN_IDENTITY'}
    check('all_674_run_directories_preserved',{r['metric_source'] for r in runrows}==expected_runs,len(runrows))
    check('source_tables_83_all_full_read',len(tables)==83 and all(r['read_depth']=='FULL_TABLE_READ' for r in tables),len(tables))
    counts=Counter((r['stage'],Path(r['metric_source']).name) for r in public if r['record_kind']=='EVALUATION_RECORD')
    check('HX03_492_original_evaluation_slots',counts[('HX03','EVALUATION_RESULT.json')]==492,counts[('HX03','EVALUATION_RESULT.json')])
    check('HX03R2_492_reevaluation_slots',counts[('HX03R2','RESULT_R2.json')]==492,counts[('HX03R2','RESULT_R2.json')])
    orig={(r['stage'],r['metric_source']):json.loads(r['source_values_json']) for r in original if r['record_kind']=='EVALUATION_RECORD'}
    cell_count=0;differences=[]
    def subset(new, old, path):
        nonlocal cell_count
        if isinstance(new,dict):
            for k,v in new.items():
                if k not in old:differences.append(path+'/'+k+':KEY_MISSING')
                else:subset(v,old[k],path+'/'+k)
        else:
            cell_count+=1
            if new!=old:differences.append(path+':VALUE_DIFFERENT')
    for r in public:
        if r['record_kind']=='EVALUATION_RECORD':subset(json.loads(r['source_values_json']),orig[(r['stage'],r['metric_source'])],r['metric_source'])
    check('selected_evaluation_values_unchanged',not differences,{'selected_leaf_values':cell_count,'differences':differences})
    contract_pairs={'BY2':('C00','FILE_START'),'BY2H':('CONTRACT_START','CONTRACT_START'),'BY2O':('FILE_START','FILE_START')}
    bad=[r['source_row_key'] for r in runrows if r['stage']=='HX02' and (r['case_id'],r['start_policy'])!=contract_pairs[r['sequence_id']]]
    check('HX02_case_and_start_independent',not bad,bad)
    bad=[r['source_row_key'] for r in runrows if r['stage']=='HX03' and json.loads(r['source_values_json']).get('reused') and not r['evaluation_status'].startswith('REUSED_EVALUATION')]
    check('reused_evaluation_not_labeled_missing',not bad,bad)
    failures=[r for r in runrows if r['stage']=='HX03' and json.loads(r['source_values_json']).get('native_failure_class')=='ALGORITHM_FAILURE_DIVERGED']
    check('all_36_native_divergences_preserved',len(failures)==36,len(failures))
    check('input_locations_100_no_missing',len(inputs)==100 and all(r['retention_status']!='EXPECTED_NOT_FOUND' for r in inputs),len(inputs))
    leaks=[]
    for p in out.iterdir():
        if p.is_file() and p.suffix in {'.csv','.json','.md','.py'}:
            if re.search(r'/(?:home/[^/\s]+|mnt/[a-z])/',p.read_text()):leaks.append(p.name)
    check('no_local_absolute_paths_in_shared_outputs',not leaks,leaks)
    parsed=[]
    for p in out.glob('*.py'):ast.parse(p.read_text());parsed.append(p.name)
    check('collector_scripts_parse',True,parsed)
    counts_files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file() and p.name!='COLLECTION_CHECKS.json'}
    result={'status':'PASS' if all(c['passed'] for c in checks) else 'FAIL','data_mode':'existing_result_index_validation','synthetic_data_used':False,'semisynthetic_data_used':True,'new_native_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,'new_performance_calculations':0,'original_time_series_payload_reads':0,'checks':checks,'files':counts_files}
    (out/'COLLECTION_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'checks':len(checks),'selected_value_checks':cell_count,'public_records':len(public),'public_files':len(files),'failed':[c for c in checks if not c['passed']]}))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
