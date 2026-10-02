#!/usr/bin/env python3
"""Transcribe a completed three-method native batch; no solve or evaluation."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--roots',required=True);parser.add_argument('--sequence',required=True)
    args=parser.parse_args();roots=json.loads(Path(args.roots).read_text())['aliases']
    root=Path(roots['<EXT_REPRO_ROOT>']);repo=Path(roots['<CODE_ROOT>'])
    base=repo/'docs/paper_rebuild/hext/EXT_REPRODUCTION/native_results'/args.sequence
    runs=[]
    for method in ('EXT01','EXT02','EXT03'):
        folder=root/'runs'/f'{args.sequence}__{method}__RAW_REPRO_V1'
        receipt=json.loads((folder/'RUN.json').read_text())
        assert receipt['status']=='COMPLETED', (method,receipt['status'])
        runs.append((method,folder,receipt))
    base.mkdir(parents=True,exist_ok=False)
    summaries=[];audits=[];diagnostics=[]
    def alias(value):
        for key,path in sorted(roots.items(),key=lambda x:len(x[1]),reverse=True):
            if value==path or value.startswith(path+'/'):return key+value[len(path):]
        return value
    for method,folder,receipt in runs:
        payload=(folder/'HEADING.csv').read_bytes()
        assert hashlib.sha256(payload).hexdigest()==receipt['outputs']['HEADING.csv']['sha256']
        shutil.copyfile(folder/'HEADING.csv',base/f'{method}_HEADING.csv')
        (base/f'{method}_RUN.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        with (folder/'HEADING.csv').open() as f:rows=list(csv.DictReader(f))
        assert len(rows)==receipt['completed_epochs']==receipt['planned_paired_epochs']
        assert sum(r['valid']=='1' for r in rows)==receipt['valid_epochs']
        summaries.append({k:receipt.get(k) for k in ('run_id','sequence','method','status','code_commit',
            'planned_paired_epochs','completed_epochs','valid_epochs','float_solved_epochs','float_stage_applicability',
            'search_attempted_epochs','search_complete_epochs','candidate_returned_epochs','ratio_fixed_epochs',
            'spp_attempts','total_satellite_state_calls','elapsed_s')})
        summaries[-1].update(failure_counts=json.dumps(receipt['failure_counts'],sort_keys=True),
                            unknown_stage_counts=json.dumps(receipt['unknown_stage_counts'],sort_keys=True),
                            source_path=f'<EXT_REPRO_ROOT>/runs/{receipt["run_id"]}/RUN.json')
        trace=root/'batches'/args.sequence/(method+'.openat')
        data_reads=set();reference_reads=[];unclassified=[]
        for line in trace.read_text().splitlines():
            if 'openat(' not in line or 'O_RDONLY' not in line or re.search(r'= -1',line):continue
            match=re.search(r'openat\([^,]+, "([^"\\]+)"',line)
            if not match:continue
            path=Path(match.group(1));path=path if path.is_absolute() else repo/path
            if path.suffix.lower() not in {'.csv','.ubx','.obs','.nav','.pos','.npy','.npz','.mat','.gz'}:continue
            text=str(path);data_reads.add(alias(text))
            if not text.startswith(str(root/'inputs')+'/') and not text.startswith(str(folder)+'/'):
                unclassified.append(alias(text))
            if text.startswith(roots['<RAW_ROOT>']+'/') or '/evaluation/' in text or '/trace/' in text:
                reference_reads.append(alias(text))
        assert not reference_reads and not unclassified,(method,reference_reads,unclassified)
        audits.append({'method':method,'trace':'<EXT_REPRO_ROOT>/batches/'+args.sequence+'/'+trace.name,
                       'checked_successful_read_openat_payload_suffixes':['csv','ubx','obs','nav','pos','npy','npz','mat','gz'],
                       'data_reads':sorted(data_reads),'reference_or_unclassified_data_reads':[],
                       'limit':'file-open role check; imported Python source is not reference payload; not a proof of all mathematical correctness'})
        if method=='EXT01':
            # Predetermined first feasible model only, no reference or score selection.
            with gzip.open(folder/'EPOCH_EVIDENCE.jsonl.gz','rt') as stream:
                for line in stream:
                    record=json.loads(line)
                    if not record.get('geometry'):continue
                    pivot=record['model']['pivot'];key=':'.join(str(pivot[k]) for k in ('gnss_id','sv_id','sig_id','freq_id'))
                    by={x['signal']:x for x in record['geometry']};reference=by[key]['known_sd_m']
                    for signal,row in by.items():
                        diagnostics.append({'sequence':args.sequence,'epoch_index':record['epoch_index'],
                            'gps_tow_seconds':record['gps_tow_seconds'],'signal':signal,'pivot':key,
                            'known_sd_m':row['known_sd_m'],'known_dd_m':row['known_sd_m']-reference,
                            'satellite_motion_sd_m':row['satellite_motion_sd_m'],
                            'satellite_clock_sd_m':row['satellite_clock_sd_m'],
                            'selection':'FIRST_FEASIBLE_MODEL_NO_REFERENCE',
                            'source_path':f'<EXT_REPRO_ROOT>/runs/{receipt["run_id"]}/EPOCH_EVIDENCE.jsonl.gz',
                            'source_row_key':f'epoch_index={record["epoch_index"]};geometry.signal={signal}'})
                    break
    for name,rows in (('NATIVE_SUMMARY.csv',summaries),('FIRST_MODEL_GEOMETRY.csv',diagnostics)):
        with (base/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    (base/'ACCESS_AUDIT.json').write_text(json.dumps({'data_mode':'real_raw','synthetic_data_used':False,
        'semisynthetic_data_used':False,'methods':audits,'native_method_sequence_calls':3,
        'evaluator_calls':0,'reference_payload_reads_detected':0},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sequence':args.sequence,'methods':len(runs),'completed_pairs_each':summaries[0]['completed_epochs']}))

if __name__=='__main__':main()
