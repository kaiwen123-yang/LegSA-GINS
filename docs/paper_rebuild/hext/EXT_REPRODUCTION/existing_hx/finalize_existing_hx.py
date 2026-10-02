#!/usr/bin/env python3
"""Normalize this collection's own indexes; do not rescan original payloads."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

FIELDS = 'record_id,stage,record_kind,method_id,paper,implementation_version,sequence_id,case_id,config_id,start_policy,input_identity,native_status,evaluation_status,metric_source,source_row_key,source_values_json,native_output_paths,evaluation_paths,figure_paths,read_depth,retention_status,archive_path,archive_member,notes'.split(',')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots', type=Path, required=True);args=ap.parse_args()
    aliases=json.loads(args.roots.read_text())['aliases']
    repo=Path(aliases['<CODE_ROOT>']);out=repo/'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_hx'
    receipt=json.loads((out/'COLLECTION_RECEIPT.json').read_text())
    prior_receipt_sha=hashlib.sha256((out/'COLLECTION_RECEIPT.json').read_bytes()).hexdigest()

    def load(name):
        with (out/name).open(newline='') as f:return list(csv.DictReader(f))

    def alias(text):
        for raw,key in sorted(((v,k) for k,v in aliases.items()), key=lambda x:len(x[0]), reverse=True):text=text.replace(raw,key)
        return text

    records=load('EXISTING_HX_INDEX.csv');files=load('EXISTING_HX_FILES.csv')
    first=load('HX02_HX07R_FIRST_INDEX.csv');first_receipt=json.loads((out/'HX02_HX07R_FIRST_RECEIPT.json').read_text())
    source_records={(r['metric_source'],r['record_kind'],r['source_row_key'].split(';physical_line=')[0]) for r in records}
    omitted=Counter();kept=[]
    for r in records:
        if r['record_kind']=='CSV_ROW' and '/RUNS/' in r['metric_source'] and any(x in Path(r['metric_source']).name for x in ('FAILURE_LEDGER','RUNTIME')):
            omitted[r['metric_source']]+=1
        else:kept.append(r)
    records=kept
    # The first subset explicitly read four JSON kinds absent from the first main allowlist.
    supplemental=0
    for r in first:
        key=(r['metric_source'],r['record_kind'],r['source_row_key'])
        if r['record_kind']=='EVALUATION_RECORD' and key not in source_records:
            records.append(r);source_records.add(key);supplemental+=1
    by_file={r['metric_source']:r for r in files}
    for path, value in first_receipt['files'].items():
        if path in by_file:continue
        record={k:'unknown' for k in FIELDS}
        record.update(record_id='HX02-FILE-'+hashlib.sha256(path.encode()).hexdigest()[:16],stage='HX02' if '/HX02_FIVE_CATEGORY/' in path else 'HX07R',record_kind='FILE',metric_source=path,source_row_key='',source_values_json=json.dumps({'bytes':value['bytes'],'newly_verified_sha256':value.get('sha256_newly_verified','not_computed'),'hash_scope':'same_bytes_read_for_metadata','recorded_sha256':'unknown'}),read_depth=value['read_depth'],retention_status='PRESENT_READ' if value['read_depth']!='METADATA_ONLY' else 'PRESENT_METADATA_ONLY',native_output_paths='[]',evaluation_paths='[]',figure_paths='[]',archive_path='',archive_member='',notes='Supplemental metadata read by collect_hx02_hx07r_first.py; no payload body read.')
        files.append(record);by_file[path]=record
    first_runs={r['metric_source']:r for r in first if r['record_kind']=='RUN_IDENTITY'}
    natural_start={'BY2':'FILE_START','BY2H':'CONTRACT_START','BY2O':'FILE_START'}
    for r in records+files:
        r['source_row_key']=r['source_row_key'].split(';physical_line=')[0]
        if r['stage']=='HX02' and '/RUNS/' in r['metric_source']:
            name=r['metric_source'].split('/RUNS/',1)[1].split('/',1)[0];tokens=name.split('__')
            if len(tokens)>=4:
                r['case_id']=tokens[3];r['start_policy']=natural_start[tokens[0]]
        if r['record_kind']=='RUN_IDENTITY' and r['metric_source'] in first_runs:
            src=first_runs[r['metric_source']]
            for field in ('implementation_version',):r[field]=src[field]
            r['notes']+=' '+src['notes']
            r['evaluation_paths']=json.dumps(sorted(set(json.loads(r['evaluation_paths']))|set(json.loads(src['evaluation_paths']))),ensure_ascii=False,separators=(',',':'))
        for key,value in r.items():
            if isinstance(value,str):r[key]=alias(value)
    for path,count in omitted.items():
        info=json.loads(by_file[path]['source_values_json'])
        assert int(info['row_count'])==count,(path,count,info)
        by_file[path]['notes']='Fully read original per-epoch failure/runtime result table; '+str(count)+' original rows remain readable at this exact source. Rows are intentionally not duplicated into the shared run/result index. Full row count, schema and same-read hash are retained here.'
    # Keep directly cited V3 source tables distinct from HX new native identities.
    cited=[('V3_CITED','07_AGGREGATE/MAIN_TABLE_V3.csv'),('V3_CITED','07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv')]
    for stage,relative in cited:
        p=Path(aliases['<V3_ROOT>'])/relative;source=alias(str(p))
        if source in by_file:continue
        raw=p.read_bytes();data=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        r={k:'unknown' for k in FIELDS};r.update(record_id=stage+'-FILE-'+hashlib.sha256(source.encode()).hexdigest()[:16],stage=stage,record_kind='FILE',metric_source=source,source_row_key='',source_values_json=json.dumps({'bytes':len(raw),'row_count':len(data),'columns':list(data[0]) if data else [],'newly_verified_sha256':hashlib.sha256(raw).hexdigest(),'hash_scope':'same_bytes_read_for_table'},ensure_ascii=False,separators=(',',':')),read_depth='FULL_TABLE_READ',retention_status='PRESENT_READ',native_output_paths='[]',evaluation_paths='[]',figure_paths='[]',archive_path='',archive_member='',notes='Existing V3 source table cited by HX02. Whole table read; source remains in the prior V3 collection. Not a new HX native call or duplicated HX run denominator.')
        files.append(r);by_file[source]=r
    # One compact source table contains all original cells; FILE catalog contains schemas/counts.
    runrows=[r for r in records if r['record_kind']=='RUN_IDENTITY']
    tables=[r for r in files if r['read_depth']=='FULL_TABLE_READ']

    def write(path, rows, local=False):
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n');w.writeheader()
            for r in rows:
                if local:
                    r=dict(r)
                    for k,v in r.items():
                        for key,value in sorted(aliases.items(),key=lambda x:len(x[0]),reverse=True):v=v.replace(key,value)
                        r[k]=v
                w.writerow(r)

    write(out/'EXISTING_HX_INDEX.csv',records);write(out/'EXISTING_HX_FILES.csv',files);write(out/'EXISTING_HX_RUNS.csv',runrows);write(out/'EXISTING_HX_TABLES.csv',tables)
    inputs=load('INPUT_LOCATIONS.csv') if (out/'INPUT_LOCATIONS.csv').is_file() else []
    write(Path(aliases['<EXT_REPRO_ROOT>'])/'existing_hx.local.csv',records+files+inputs,local=True)
    original=receipt.get('initial_collection_counts',{'record_rows':receipt['record_rows'],'file_rows':receipt['file_rows'],'script_sha256':receipt['script_sha256'],'stage_counts':receipt['stage_counts']})
    receipt.update(initial_collection_counts=original,record_rows=len(records),file_rows=len(files),run_identity_rows=len(runrows),record_kinds=dict(Counter(r['record_kind'] for r in records)),read_depth_counts=dict(Counter(r['read_depth'] for r in files)),retention_counts=dict(Counter(r['retention_status'] for r in files)))
    receipt['stage_counts']={stage:{'record_rows':sum(r['stage']==stage for r in records),'run_directories':sum(r['stage']==stage for r in runrows),'full_table_files':sum(r['stage']==stage and r['read_depth']=='FULL_TABLE_READ' for r in files),'full_metadata_files':sum(r['stage']==stage and r['read_depth']=='FULL_RECORD_READ' for r in files)} for stage in sorted({r['stage'] for r in files+records})}
    receipt['collection_index_normalization']={'prior_collection_receipt_sha256':prior_receipt_sha,'per_epoch_result_rows_kept_in_original_table_only':sum(omitted.values()),'original_epoch_tables':dict(omitted),'supplemental_evaluation_json_records':supplemental,'source_row_key':'CSV:data_row=N, one-based data record, excluding header; no physical-line claim','HX02_case_mapping':'Original contract CASE retained; start_policy independently records start_convention; collection-stage supervisor mapping correction, no source changes.','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'collector_final_sha256':hashlib.sha256((out/'collect_existing_hx.py').read_bytes()).hexdigest()}
    receipt['table_files_fully_read']=len(tables)
    receipt['table_rows_actually_read_physical_sources']=sum(int(json.loads(r['source_values_json']).get('row_count',0)) for r in tables)
    receipt['all_original_epoch_result_tables_read']=True
    receipt['local_mirror_includes_input_rows']=len(inputs)
    (out/'COLLECTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'records':len(records),'files':len(files),'runs':len(runrows),'tables':len(tables),'omitted_epoch_copies':sum(omitted.values()),'supplemental_evaluation_records':supplemental,'bytes':{name:(out/name).stat().st_size for name in ('EXISTING_HX_INDEX.csv','EXISTING_HX_FILES.csv','EXISTING_HX_RUNS.csv','EXISTING_HX_TABLES.csv')}}))

if __name__=='__main__':main()
