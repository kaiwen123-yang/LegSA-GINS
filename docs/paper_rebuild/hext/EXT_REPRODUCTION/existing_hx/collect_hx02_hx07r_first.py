#!/usr/bin/env python3
"""Small first delivery from HX02/HX07R records; no solver or payload reads."""
import argparse,csv,hashlib,io,json,re
from pathlib import Path

FIELDS='record_id,stage,record_kind,method_id,paper,implementation_version,sequence_id,case_id,config_id,start_policy,input_identity,native_status,evaluation_status,metric_source,source_row_key,source_values_json,native_output_paths,evaluation_paths,figure_paths,read_depth,retention_status,archive_path,archive_member,notes'.split(',')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',type=Path,required=True);args=ap.parse_args()
    config=json.loads(args.roots.read_text());aliases=config['aliases'];repo=Path(aliases['<CODE_ROOT>']);out=repo/'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_hx';ext=Path(aliases['<CLEAN_ROOT>'])/'stages/CLEAN9_EXTERNAL_COMPARISON'
    def alias(s):
        for raw,name in sorted(((v,k) for k,v in aliases.items()),key=lambda x:len(x[0]),reverse=True):s=s.replace(raw,name)
        return s
    contract_path=repo/'configs/paper_rebuild/hext/HX02_CONTRACT_V1.yaml'
    contract_text=contract_path.read_text()
    sequence_block=contract_text.split('sequences:\n',1)[1].split('contract_start_application:',1)[0]
    contract_starts={m[0]:m[2] for m in re.findall(r'  (BY2[HO]?):\n    case: (\S+)\n    start_convention: (\S+)',sequence_block)}
    assert set(contract_starts)=={'BY2','BY2H','BY2O'}
    rows=[];files={};counts={}
    def add(stage,kind,p,key,values,**kw):
        row={k:'unknown' for k in FIELDS};source=alias(str(p));row.update(stage=stage,record_kind=kind,record_id=stage+'-'+hashlib.sha256((source+'|'+key).encode()).hexdigest()[:20],metric_source=source,source_row_key=key,source_values_json=alias(json.dumps(values,ensure_ascii=False,separators=(',',':'))),native_output_paths='[]',evaluation_paths='[]',figure_paths='[]',archive_path='',archive_member='',read_depth='FULL_RECORD_READ',retention_status='PRESENT_READ',notes='First-delivery subset. Source values preserved; path aliases only. No payload-body read.');row.update(kw);rows.append(row)
    def read_json(stage,p):
        raw=p.read_bytes();v=json.loads(raw,parse_float=str,parse_int=str);files[alias(str(p))]={'bytes':len(raw),'sha256_newly_verified':hashlib.sha256(raw).hexdigest(),'read_depth':'FULL_RECORD_READ'};return v
    for stage,dirname in [('HX02','HX02_FIVE_CATEGORY'),('HX07R','HX07R')]:
        root=ext/dirname;before=len(rows);tables=[repo/'docs/paper_rebuild/hext/HX02/EXTERNAL_FIVE_CATEGORY_TABLE.csv'] if stage=='HX02' else [root/'SUMMARY.csv',root/'VALID_DIAGNOSTICS.csv']
        for p in tables:
            raw=p.read_bytes();data=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));files[alias(str(p))]={'bytes':len(raw),'rows':len(data),'sha256_newly_verified':hashlib.sha256(raw).hexdigest(),'read_depth':'FULL_TABLE_READ'}
            for i,v in enumerate(data,1):add(stage,'CSV_ROW',p,'CSV:data_row='+str(i),v,method_id=v.get('method_id','RTKLIB'),sequence_id=v.get('sequence','unknown'),config_id=v.get('config',v.get('variant','unknown')),start_policy=v.get('start_mode','unknown'),evaluation_status=v.get('failure_flag','METRICS_RECORDED'))
        rundirs=sorted(p for p in (root/'RUNS').iterdir() if p.is_dir());native_count=0;eval_count=0
        for run in rundirs:
            split=run.name.split('__');identity={'sequence_id':split[0],'method_id':split[1],'config_id':split[2],'case_id':split[3],'start_policy':contract_starts[split[0]]} if len(split)>=4 else {'sequence_id':run.name.split('_',1)[0],'method_id':'RTKLIB','config_id':run.name.split('_',1)[1],'case_id':'NATURAL'}
            metadata={}
            for n in ['COMMAND.json','DONE.json','FAILURE.json','ASSOCIATION_SUMMARY.json']:
                p=run/n
                if p.is_file():metadata[n]=read_json(stage,p)
            if 'COMMAND.json' in metadata:native_count+=1
            evaluation=[]
            for p in sorted((run/'eval').rglob('*.json')):
                if p.name not in ['HEADING_METRICS.json','GINAV_EVALUATION.json','RELATIVE_POSE_METRICS.json','COVERAGE_METRICS.json','EVALUATION_RESULT.json','D8_BOUNDED_GATE.json','DIVERGENCE_GATE.json','EVALUATOR_STRACE_AUDIT.json']:continue
                v=read_json(stage,p);add(stage,'EVALUATION_RECORD',p,'#',v,**identity);evaluation.append(alias(str(p)))
                if p.name=='EVALUATOR_STRACE_AUDIT.json':eval_count+=1
            current=[]
            # The heading table named in DONE is historical scratch; current retained output is resolved within this archive directory.
            for p in [run/'solution.pos',run/'HEADING_TABLE.csv']+list((run/'native/HX02_HEADING_TABLES').glob('*.csv')):
                if p.is_file():current.append(alias(str(p)));files[alias(str(p))]={'bytes':p.stat().st_size,'read_depth':'METADATA_ONLY'}
            done=metadata.get('DONE.json',{});cmd=metadata.get('COMMAND.json',{})
            add(stage,'RUN_IDENTITY',run,'run_id='+run.name,metadata,**identity,native_status=done.get('native_classification',cmd.get('status','NO_NEW_NATIVE_COMMAND_RECORDED')),evaluation_status='EVALUATION_RECORDS_PRESENT' if evaluation else 'NO_EVALUATION_RECORD_PRESENT',implementation_version=str(done.get('provenance',{}).get('code_commit',cmd.get('code_commit','unknown'))),native_output_paths=json.dumps(current),evaluation_paths=json.dumps(evaluation),retention_status='ARCHIVED_DIRECTORY_PRESENT',notes='For HX02, directory token 4 is the original contract CASE; start_policy is sequences.<SEQ>.start_convention in HX02_CONTRACT_V1.yaml. This corrects the collection-stage CASE/start mapping; original metadata is unchanged. native_classification='+str(done.get('native_classification','unknown'))+'; runner_terminal_status='+str(done.get('runner_terminal_status',cmd.get('runner_terminal_status','unknown')))+'. Original metadata values preserved in source_values_json.')
        counts[stage]={'row_records':len(rows)-before,'physical_directories':len(rundirs),'native_COMMAND_files':native_count,'evaluation_audit_files':eval_count}
    # Original recorded process counts distinguish coverage-only children and the extra convbin evaluation.
    for stage,name in [('HX02','COUNTERS.json'),('HX07R','HX07R_EXECUTION_COUNTS.json')]:
        p=repo/'docs/paper_rebuild/hext'/stage/name;add(stage,'RECORDED_COUNTERS',p,'#',read_json(stage,p))
    path=out/'HX02_HX07R_FIRST_INDEX.csv'
    with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(rows)
    receipt={'status':'FIRST_SUBSET_COLLECTED','data_mode':'existing_real_data_results','synthetic_data_used':False,'semisynthetic_data_used':False,'new_native_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,'time_series_payload_reads':0,'reference_payload_reads':0,'counts':counts,'index_rows':len(rows),'files':files,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'not_total_hx_collection':True,'field_mapping_source':alias(str(contract_path)),'field_mapping_source_sha256_newly_verified':hashlib.sha256(contract_text.encode()).hexdigest(),'mapping_correction':'Original HX02 CASE words restored after supervisor checked the contract; start_policy independently records start_convention.'}
    (out/'HX02_HX07R_FIRST_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'index_rows':len(rows),'counts':counts,'bytes':path.stat().st_size}))
if __name__=='__main__':main()
