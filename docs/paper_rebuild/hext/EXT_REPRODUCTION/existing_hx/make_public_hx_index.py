#!/usr/bin/env python3
"""Make a small navigation index from the already-read full collection only."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

FIELDS='record_id,stage,record_kind,method_id,paper,implementation_version,sequence_id,case_id,config_id,start_policy,input_identity,native_status,evaluation_status,metric_source,source_row_key,source_values_json,native_output_paths,evaluation_paths,figure_paths,read_depth,retention_status,archive_path,archive_member,notes'.split(',')
EVAL_NAMES={'EVALUATION_RESULT.json','RESULT_R2.json','HEADING_METRICS.json','RELATIVE_POSE_METRICS.json','GINAV_EVALUATION.json','COVERAGE_METRICS.json','D8_BOUNDED_GATE.json','DIVERGENCE_GATE.json'}
CORE_FIELDS={'horizontal_rmse_m','up_rmse_m','yaw_rmse_deg','roll_rmse_deg','pitch_rmse_deg','yaw_p95_deg','horizontal_p95_m','position_drift_m_per_100m','heading_drift_deg_per_min','relative_pose_error_yaw_translation','valid_rmse_deg','hold_rmse_deg','availability','valid_epochs','availability_denominator','denominator','matched_epoch_count','matched_count','output_epoch_count','reference_epoch_count','coverage_ratio','evaluation_status','status','failure_class','scored_epochs','nav_rows','nav_first_rel_s','nav_last_rel_s','unsupported_grid_epochs','reference_path_length_m','time_start','time_end','count','evaluation_invoked','STD','evaluator_contract','source_nav_sha256','evaluator_nav_sha256','version','slot_id','role','audit_status_R1','audit_status_R2','native_failure_class'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',type=Path,required=True);args=ap.parse_args()
    aliases=json.loads(args.roots.read_text())['aliases'];repo=Path(aliases['<CODE_ROOT>']);out=repo/'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_hx';full=Path(aliases['<EXT_REPRO_ROOT>'])/'existing_hx_full'
    full.mkdir(exist_ok=True)
    originals=['EXISTING_HX_INDEX.csv','EXISTING_HX_FILES.csv','EXISTING_HX_RUNS.csv','EXISTING_HX_TABLES.csv','COLLECTION_RECEIPT.json']
    pins={}
    for name in originals:
        src=out/name;dst=full/name
        if not dst.exists():dst.write_bytes(src.read_bytes())
        pins[name]={'source_path':'<EXT_REPRO_ROOT>/existing_hx_full/'+name,'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}

    def load(name):
        with (full/name).open(newline='') as f:return list(csv.DictReader(f))
    def compact(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
    def essential(p):
        n=Path(p).name.lower()
        return n in {'nav.csv','kf_gins_navresult.nav','kf_gins_std.txt','exact_evaluator_input.nav','eval_nav.txt','eval_nav.nav','eval_nav_v2.nav','eval_nav_v3.nav','heading_table.csv','solution.pos','arrays.npz'} or ('error_series' in n or 'trajectory' in n or n.endswith('.nav') or n.endswith('_nav.csv')) or (n.endswith('.csv') and 'heading_table' in n) or n.endswith('.pos')
    def slim_metrics(v):
        return {k:x for k,x in v.items() if (k in CORE_FIELDS or k.endswith('_count') or k.endswith('_epochs') or 'rmse' in k) and not isinstance(x,(list,dict))}

    records=load('EXISTING_HX_INDEX.csv');files=load('EXISTING_HX_FILES.csv');by_source={r['metric_source']:r for r in files}
    public=[];runrows=[];evalrows=[];table_rows=[]
    original_run_results={r['metric_source'].rsplit('/',1)[0]:json.loads(r['source_values_json']) for r in records if r['record_kind']=='NATIVE_RECORD' and r['metric_source'].endswith('/RESULT.json')}
    for old in records:
        name=Path(old['metric_source']).name
        if old['record_kind']=='RUN_IDENTITY':
            r=dict(old);v=json.loads(r['source_values_json'])
            values={k:v[k] for k in ('run_id','execution','reused','native_returncode','original_native_terminal','native_failure_class','start_evidence') if k in v}
            metadata=[p for p in v.get('record_source_files',[]) if Path(p).name in {'DONE.json','FAILURE.json','RESULT.json','COMMAND.json','NATIVE_RESULT.json'} and '/eval/' not in p]
            primary=[p for p in metadata if Path(p).name=='RESULT.json'] or [p for p in metadata if Path(p).name in {'DONE.json','FAILURE.json'}] or [p for p in metadata if Path(p).name=='COMMAND.json']
            values['original_metadata_sources']=primary
            original=original_run_results.get(r['metric_source'],{})
            for key in ('source_run_dir','source_nav_sha256','reuse_source_run_id','seed','family','type','input_identity_note'):
                if key in original:values[key]=original[key]
            if original.get('reused'):
                values['reused_evaluations']={key:slim_metrics(item) for key,item in original.get('evaluations',{}).items()}
                r['evaluation_status']='REUSED_EVALUATION; see source_values_json.reused_evaluations and source_run_dir'
            r['source_values_json']=compact(values)
            r['native_output_paths']=compact([p for p in json.loads(r['native_output_paths']) if essential(p)])
            r['evaluation_paths']=compact([p for p in json.loads(r['evaluation_paths']) if Path(p).name in EVAL_NAMES or essential(p)])
            r['notes']='One existing RUN directory; execution/reused distinguishes real native calls and reused identities. All source metadata was read; the complete collection is retained locally. No new call.'
            public.append(r);runrows.append(r)
        elif old['record_kind']=='EVALUATION_RECORD' and name in EVAL_NAMES:
            r=dict(old);v=json.loads(r['source_values_json']);values=slim_metrics(v)
            if isinstance(v.get('row'),dict):values['row']=slim_metrics(v['row'])
            if isinstance(v.get('metrics'),dict):values['metrics']=slim_metrics(v['metrics'])
            # Heading outputs may contain separate FAR/PAR branches: retain every branch.
            for k,x in v.items():
                if isinstance(x,dict) and k not in {'row','metrics','audit','capture','transform','scientific_identity','old_available_metrics_identity','observer_discrepancy_R2'}:
                    picked=slim_metrics(x)
                    if picked:values[k]=picked
            for nested in ('variants','branches'):
                if isinstance(v.get(nested),dict):values[nested]=v[nested]
            if 'audit' in v and isinstance(v['audit'],dict):values['audit']={k:v['audit'][k] for k in ('passed','technical_passed','consistency_passed','exit_code','trace_open_count') if k in v['audit']}
            r['source_values_json']=compact(values)
            r['notes']='Selected original metrics/support/status for navigation only; not a replacement for the fully read source JSON. Exact remaining fields and all numeric precision remain at metric_source and in the local complete collection. No recomputation.'
            public.append(r);evalrows.append(r)
    # Small tracked result tables are linked rather than duplicated into another inventory.
    for old in files:
        if old['read_depth']=='FULL_TABLE_READ':
            r=dict(old);r['record_kind']='RESULT_TABLE';r['notes']='Whole source CSV read; data rows remain available at this exact path. Original source-table row count/schema/hash preserved. Copies with equal hashes are not independent experiments.'
            public.append(r);table_rows.append(r)
    necessary_sources={r['metric_source'] for r in evalrows+table_rows}
    necessary_payloads=set()
    for r in runrows:
        necessary_payloads.update(json.loads(r['native_output_paths']));necessary_payloads.update(json.loads(r['evaluation_paths']))
        necessary_sources.update(json.loads(r['source_values_json']).get('original_metadata_sources',[]))
    file_public=[]
    for old in files:
        p=old['metric_source']
        if p not in necessary_sources and p not in necessary_payloads and old['figure_paths'] in ('[]','unknown'):
            continue
        r=dict(old);v=json.loads(r['source_values_json'])
        r['source_values_json']=compact({k:x for k,x in v.items() if k in {'bytes','recorded_sha256','newly_verified_sha256','hash_scope','row_count','columns'}})
        r['notes']='Read depth is literal: result JSON/table fully read; NAV/STD/pos/heading/error payloads only located/stat. Recorded hash is not a new payload hash. Full 12903-entry work inventory remains local.'
        file_public.append(r)
    # Preserve exact table/figure bindings without duplicating all manuscript table rows.
    presentation=[]
    for name in ('SOURCE_CITATIONS.json','FIGURE_MANIFEST.json','MANUSCRIPT_DATA.json'):
        p=repo/'docs/paper_rebuild/hext/HX05'/name
        if not p.is_file():continue
        raw=p.read_bytes();v=json.loads(raw,parse_float=str,parse_int=str)
        info={'source_path':'<CODE_ROOT>/docs/paper_rebuild/hext/HX05/'+name,'bytes':len(raw),'newly_verified_sha256':hashlib.sha256(raw).hexdigest(),'read_depth':'FULL_RECORD_READ','top_level_record_count':len(v)}
        presentation.append(info)
        if name in ('SOURCE_CITATIONS.json','FIGURE_MANIFEST.json'):
            text=json.dumps(v,ensure_ascii=False,separators=(',',':'))
            for rawpath,macro in sorted(((v,k) for k,v in aliases.items()),key=lambda x:len(x[0]),reverse=True):text=text.replace(rawpath,macro)
            (out/('HX05_'+name)).write_text(text+'\n')

    def write(name,rows):
        with (out/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(rows)
    write('EXISTING_HX_INDEX.csv',public);write('EXISTING_HX_RUNS.csv',runrows);write('EXISTING_HX_FILES.csv',file_public);write('EXISTING_HX_TABLES.csv',table_rows)
    receipt=json.loads((full/'COLLECTION_RECEIPT.json').read_text())
    receipt['public_index']={'format':'run identity + evaluation/gate JSON summary + fully read source table links','record_rows':len(public),'run_identity_rows':len(runrows),'evaluation_or_gate_rows':len(evalrows),'source_table_rows':len(table_rows),'key_file_rows':len(file_public),'full_work_inventory':pins,'complete_absolute_path_mirror':'<EXT_REPRO_ROOT>/existing_hx.local.csv','original_metric_values':'Selected unchanged values in public JSON; complete source table/JSON values in original files and full local work index. Public subset is explicitly not all metric columns.','source_presentation_metadata_read':presentation,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'COLLECTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(compact({'public':receipt['public_index']['record_rows'],'runs':len(runrows),'eval_or_gate':len(evalrows),'tables':len(table_rows),'files':len(file_public),'bytes':{n:(out/n).stat().st_size for n in ('EXISTING_HX_INDEX.csv','EXISTING_HX_RUNS.csv','EXISTING_HX_FILES.csv','EXISTING_HX_TABLES.csv')}}))

if __name__=='__main__':main()
