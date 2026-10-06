#!/usr/bin/env python3
"""Bounded read-only HX result collection. No project imports or scientific calls."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re

FIELDS = ('record_id,stage,record_kind,method_id,paper,implementation_version,sequence_id,case_id,config_id,start_policy,input_identity,native_status,evaluation_status,metric_source,source_row_key,source_values_json,native_output_paths,evaluation_paths,figure_paths,read_depth,retention_status,archive_path,archive_member,notes').split(',')
STAGES = {
    'HX02':'HX02_FIVE_CATEGORY', 'HX02E':'HX02E_HARTLEY_OFFICIAL',
    'HX03':'HX03_DEGRADATION', 'HX03R2':'HX03R2_AUDIT_REEVAL',
    'HX05':'HX05_CLOSEOUT', 'HX07':'HX07', 'HX07R':'HX07R',
}
PRUNED = {'CACHE', 'SOURCE_BACKEND', '.cache', '.epoch_parts', '.determinism', '__pycache__', 'BUILD', 'SOURCE', 'SOURCE_FROZEN'}
RESULT_NAMES = {'DONE.json','FAILURE.json','RESULT.json','RESULT_R2.json','NATIVE_RESULT.json','EVALUATION_RESULT.json','HEADING_METRICS.json','RELATIVE_POSE_METRICS.json','summary.json','summary_R2.json','ASSOCIATION_SUMMARY.json','CONVENTION_DIAGNOSTIC.json','COVERAGE_RESULT.json','GINAV_EVALUATION.json','COVERAGE_METRICS.json','D8_BOUNDED_GATE.json','DIVERGENCE_GATE.json'}
META_NAMES = {'COMMAND.json','PARAMS_ECHO.json','INPUT_HASHES.json','OUTPUT_HASHES.json','ARCHIVE_MANIFEST.json','ARCHIVE_RECEIPT_R2.json','SCIENTIFIC_IDENTITY_R2.json','INTEGRATION_RECEIPT.json','SEQUENCE_SPEC.json','SPEC.json','SPEC_R2.json','EVALUATOR_CAPTURE.json','EVALUATOR_CAPTURE_R2.json','EVALUATOR_STRACE_AUDIT.json','EVALUATOR_STRACE_AUDIT_R2.json','NATIVE_ACCESS_AUDIT.json','NATIVE_AUDIT.json','TRANSFORM_MANIFEST.json','NATIVE_TIMING.json','AUDIT_DETAIL_R2.json'}
PAYLOAD_WORDS = ('NAV','HEADING','ERROR_SERIES','TRAJECTORY','AUDIT_RESIDUAL','NATIVE_STATE','ARRAYS.NPZ')
MANIFEST_NAMES = {'ARCHIVE_MANIFEST.json','OUTPUT_HASHES.json','ARCHIVE_RECEIPT_R2.json'}

def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def jload(text):
    return json.loads(text, parse_float=str, parse_int=str)

class Collector:
    def __init__(self, roots):
        cfg=json.loads(roots.read_text()); self.aliases=cfg['aliases']; self.start_head=cfg['start_head']
        self.repo=Path(self.aliases['<CODE_ROOT>']); self.docs=self.repo/'docs/paper_rebuild/hext'
        self.out=self.docs/'EXT_REPRODUCTION/existing_hx'
        self.external=Path(self.aliases['<CLEAN_ROOT>'])/'stages/CLEAN9_EXTERNAL_COMPARISON'
        self.stage_roots={k:self.external/v for k,v in STAGES.items()}
        self.replacements=sorted([(v,k) for k,v in self.aliases.items()],key=lambda x:len(x[0]),reverse=True)
        self.macros={'$'+k:str(v) for k,v in self.stage_roots.items()}
        self.macros.update({'<'+k+'>':str(v) for k,v in self.stage_roots.items()})
        self.macros.update({'$V3':self.aliases['<V3_ROOT>'],'$W':self.aliases['<AUDIT_SOURCE_WORKTREE>'],'$CLEAN4':str(Path(self.aliases['<CLEAN_ROOT>'])/'stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON')})
        self.records=[];self.files={};self.parsed={};self.table_sources={};self.table_counts=Counter();self.metadata_counts=Counter();self.run_rows=[];self.issues=[]
        self.hashes={};self.manifest_hashes={};self.paper_map={};self.source_paths=defaultdict(list);self.stage_counters={};self.document_paths=[]
        self.unmapped_paths={}

    def alias(self,value):
        value=str(value)
        for raw,alias in self.replacements:value=value.replace(raw,alias)
        # Source paths embedded in old cells remain reversible aliases; numeric values untouched.
        return value

    def portable(self,value):
        if isinstance(value,str):return self.alias(value)
        if isinstance(value,list):return [self.portable(x) for x in value]
        if isinstance(value,dict):return {self.alias(k):self.portable(v) for k,v in value.items()}
        return value

    def resolve(self,value):
        value=str(value)
        for alias,raw in sorted({**self.aliases,**self.macros}.items(),key=lambda x:len(x[0]),reverse=True):value=value.replace(alias,raw)
        return Path(value)

    def identity(self,path,stage):
        out=dict(method_id='unknown',sequence_id='unknown',case_id='unknown',config_id='unknown',start_policy='unknown')
        parts=path.parts
        if 'RUNS' not in parts:return out
        name=parts[parts.index('RUNS')+1];tokens=name.split('__')
        if len(tokens)>=4:
            out.update(sequence_id=tokens[0],method_id=tokens[1],config_id=tokens[2],case_id=tokens[3])
            if stage=='HX02':out['start_policy']={'BY2':'FILE_START','BY2H':'CONTRACT_START','BY2O':'FILE_START'}[tokens[0]]  # HX02_CONTRACT_V1.yaml sequences.*.start_convention
            if stage=='HX02E':out['start_policy']=tokens[3]
        elif stage in ('HX07','HX07R'):
            seq,variant=name.split('_',1);out.update(sequence_id=seq,method_id='RTKLIB',case_id='C00' if seq=='BY2' else 'NATURAL',config_id=variant)
        elif stage=='HX05':out.update(sequence_id=name,method_id='LEG-DR',case_id='C00' if name=='BY2' else 'NATURAL',config_id='INPUT_REFERENCE')
        return out

    def add(self,stage,kind,path,key,value,identity=None,**kwargs):
        row={k:'unknown' for k in FIELDS};source=self.alias(path)
        row.update(record_id=stage+'-'+hashlib.sha256((kind+'|'+source+'|'+key).encode()).hexdigest()[:20],stage=stage,record_kind=kind,metric_source=source,source_row_key=key,source_values_json=compact(self.portable(value)),
            native_output_paths='[]',evaluation_paths='[]',figure_paths='[]',archive_path='',archive_member='',read_depth='FULL_RECORD_READ',retention_status='PRESENT_READ',notes='JSON numeric lexemes are strings; CSV source cells preserved; absolute path prefixes replaced reversibly by local aliases only.')
        row.update(identity or self.identity(Path(path),stage));row.update(kwargs)
        if row['paper']=='unknown':row['paper']=self.paper_map.get(row['method_id'],'unknown')
        self.records.append(row);return row

    def file(self,path,stage,depth='METADATA_ONLY',**extra):
        path=Path(path);key=str(path)
        if key not in self.files:
            row={k:'unknown' for k in FIELDS};row.update(self.identity(path,stage))
            exists=path.is_file();info={'bytes':path.stat().st_size if exists else None,'recorded_sha256':self.manifest_hashes.get(key,'unknown'),'newly_verified_sha256':'not_computed','hash_scope':'none'}
            row.update(record_id=stage+'-FILE-'+hashlib.sha256(self.alias(path).encode()).hexdigest()[:16],stage=stage,record_kind='FILE',metric_source=self.alias(path),source_row_key='',source_values_json=compact(info),read_depth=depth,retention_status='PRESENT_METADATA_ONLY' if exists else 'EXPECTED_NOT_FOUND',native_output_paths='[]',evaluation_paths='[]',figure_paths='[]',archive_path='',archive_member='',notes='File stat is not a payload read. Recorded hashes are not newly verified.')
            if path.suffix=='.gz':row.update(retention_status='PRESENT_COMPRESSED_FILE' if exists else 'EXPECTED_NOT_FOUND',archive_path=self.alias(path),archive_member='SINGLE_GZIP_STREAM_NOT_OPENED',notes='Standalone gzip payload retained; body and CRC not read in this collection.')
            self.files[key]=row
        self.files[key].update(extra)
        return self.files[key]

    def read(self,path,stage,kind='JSON_METADATA',emit=True):
        path=Path(path);key=str(path)
        if key in self.parsed:return self.parsed[key]
        row=self.file(path,stage)
        if not path.is_file():self.issues.append({'stage':stage,'path':self.alias(path),'status':'EXPECTED_NOT_FOUND'});return None
        try:
            raw=path.read_bytes();txt=raw.decode('utf-8-sig');sha=hashlib.sha256(raw).hexdigest()
            if path.suffix=='.json':value=jload(txt)
            elif path.suffix=='.jsonl':value=[jload(line) for line in txt.splitlines() if line.strip()]
            else:value=txt
            self.parsed[key]=value;self.hashes[key]=sha
            row.update(read_depth='FULL_RECORD_READ',retention_status='PRESENT_READ',source_values_json=compact({'bytes':len(raw),'newly_verified_sha256':sha,'hash_scope':'same_bytes_read_for_metadata','recorded_sha256':self.manifest_hashes.get(key,'unknown'),'top_level_keys':list(value) if isinstance(value,dict) else None}))
            self.metadata_counts[stage]+=1
            if emit:self.add(stage,kind,path,'#',value)
            if path.name in MANIFEST_NAMES:self.register_manifest(path,value,stage)
            return value
        except Exception as exc:
            row.update(read_depth='READ_FAILED',retention_status='UNREADABLE',notes=type(exc).__name__+': '+str(exc));self.issues.append({'stage':stage,'path':self.alias(path),'status':'READ_FAILED','exception':type(exc).__name__});return None

    def register_manifest(self,path,data,stage):
        if not isinstance(data,dict):return
        values=data.get('files',data.get('files_sha256',data))
        if isinstance(values,list):items=[(x.get('path',''),x.get('sha256','unknown')) for x in values if isinstance(x,dict)]
        elif isinstance(values,dict):items=[(k,v.get('sha256','unknown') if isinstance(v,dict) else v) for k,v in values.items()]
        else:return
        for rel,sha in items:
            if not isinstance(rel,str) or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):continue
            p=path.parent/rel;self.manifest_hashes[str(p)]=sha
            if self.is_payload(p):self.file(p,stage)

    @staticmethod
    def is_payload(path):
        name=path.name.upper()
        return path.suffix.lower() in ('.nav','.pos','.stat','.npz') or (path.suffix.lower() in ('.csv','.gz','.txt') and any(w in name for w in PAYLOAD_WORDS))

    def table(self,path,stage,emit_rows=True):
        path=Path(path);key=str(path)
        if key in self.table_sources:return
        if not path.is_file():self.file(path,stage);self.issues.append({'stage':stage,'path':self.alias(path),'status':'EXPECTED_TABLE_NOT_FOUND'});return
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        self.table_sources[key]=rows;self.table_counts[stage]+=1
        self.file(path,stage,read_depth='FULL_TABLE_READ',retention_status='PRESENT_READ',source_values_json=compact({'bytes':len(raw),'row_count':len(rows),'columns':list(rows[0]) if rows else [],'newly_verified_sha256':sha,'hash_scope':'same_bytes_read_for_table'}))
        if not emit_rows:return
        for i,data in enumerate(rows,2):
            ident=self.identity(path,stage);ident.update({out:data[src] for out,choices in {'method_id':['method_id','method'],'sequence_id':['sequence_id','sequence','dataset_id'],'case_id':['case_id'],'config_id':['config','configuration','variant'],'start_policy':['start_mode','start_policy']}.items() for src in choices if data.get(src)})
            if stage in ('HX03','HX03R2') and ident['sequence_id']=='unknown' and data.get('case_id'):ident['sequence_id']='BY2'
            source=data.get('source_run_dir',data.get('source',''))
            row=self.add(stage,'CSV_ROW',path,'CSV:data_row='+str(i-1),data,ident,evaluation_status=data.get('evaluation_status',data.get('failure_flag',data.get('failure_class',data.get('status','unknown')))),notes='All original CSV cells read. Table row is not an independent native process. Source links: '+self.alias(source))
            if path.name=='HX_INVENTORY.csv':self.paper_map[data['method_id']]=data['reference']
            for token in re.findall(r'(?:\$HX\w+|<HX\w+>|<CLEAN_ROOT>)/RUNS/[^;\s:]+',source):self.source_paths[str(self.resolve(token))].append(data)

    def doc(self,path,stage):
        value=self.read(path,stage,emit=False)
        if value is not None:self.document_paths.append(self.alias(path))

    def walk_run(self,path,stage):
        jsons=[];payload=[]
        for dr,dirs,files in os.walk(path,followlinks=False):
            dirs[:]=[x for x in dirs if x not in PRUNED and not Path(dr,x).is_symlink()]
            for name in sorted(files):
                p=Path(dr,name)
                if p.is_symlink():self.file(p,stage,notes='Symlink only; target payload not read.');continue
                if name in RESULT_NAMES or name in META_NAMES or (name.endswith('_SUMMARY.json') and not name.startswith('epoch_')):jsons.append(p)
                elif self.is_payload(p):payload.append(p);self.file(p,stage)
                elif p.suffix=='.csv' and ('FAILURE_LEDGER' in name or 'RUNTIME' in name):self.table(p,stage,emit_rows=False)
        for p in sorted(jsons):
            emit=p.name in RESULT_NAMES or (p.name.endswith('_SUMMARY.json') and 'SOURCE_BACKEND' not in p.parts)
            data=self.read(p,stage,'EVALUATION_RECORD' if ('eval' in p.parts or '_R2' in p.parent.name) else 'NATIVE_RECORD',emit=emit)
        return jsons,payload

    def run_identity(self,path,stage,jsons,payloads):
        ident=self.identity(path/'RESULT.json',stage);get=lambda n:self.parsed.get(str(path/n),{}) or {}
        result=get('RESULT.json');done=get('DONE.json');cmd=get('COMMAND.json');seqspec=get('native/SEQUENCE_SPEC.json')
        data=result or done or cmd
        for out,choices in {'method_id':['method','method_id'],'sequence_id':['sequence','sequence_id'],'case_id':['case_id','case'],'config_id':['config','variant'],'start_policy':['start_mode','start_policy','start_convention']}.items():
            for src in choices:
                for source in [data,cmd,seqspec]:
                    if source.get(src) is not None:ident[out]=str(source[src]);break
                if ident[out]!='unknown':break
        linked=[x for key,rows in self.source_paths.items() if key==str(path) for x in rows]
        if ident['start_policy']=='unknown':
            vals=sorted({x['start_mode'] for x in linked if x.get('start_mode')});ident['start_policy']='|'.join(vals) or 'unknown'
        native=result.get('native',{}) if isinstance(result.get('native'),dict) else {}
        ns=done.get('native_classification',native.get('status',result.get('failure_flag',cmd.get('native_classification',cmd.get('status','unknown')))))
        if result.get('execution'):ns=result['execution']+':'+str(ns)
        if stage=='HX03R2':ns='NO_NEW_NATIVE_REEVALUATION_ONLY'
        if stage=='HX05':ns='INTEGRATION_ONLY_NOT_EXTERNAL_SOLVER'
        if stage=='HX07':ns=str(cmd.get('returncode','unknown'))+':ORIGINAL_V0_REPRODUCTION_HARD_STOP'
        evaluation_files=[p for p in jsons if p.name in {'EVALUATION_RESULT.json','RESULT_R2.json','HEADING_METRICS.json','RELATIVE_POSE_METRICS.json','COVERAGE_RESULT.json','GINAV_EVALUATION.json','COVERAGE_METRICS.json','D8_BOUNDED_GATE.json','DIVERGENCE_GATE.json'}]
        statuses={}
        for p in evaluation_files:
            value=self.parsed.get(str(p),{}) or {};row=value.get('row',{})
            status=value.get('audit_status_R2',row.get('evaluation_status',row.get('status',value.get('status','METRICS_RECORDED'))))
            statuses[str(p.relative_to(path))]=status
        if not statuses:statuses={'status':'NOT_GENERATED_AFTER_NATIVE_FAILURE' if any(t in str(ns) for t in ('FAIL','DIVERGED','ABNORMAL')) else 'NO_EVALUATION_RECORD_LOCATED'}
        start_evidence={'native_initial_time':native.get('initial_time','unknown'),'start_policy_field':ident['start_policy'],'table_start_modes':sorted({x['start_mode'] for x in linked if x.get('start_mode')})}
        record={'run_directory':self.alias(path),'run_id':data.get('run_id',path.name),'record_source_files':[self.alias(p) for p in jsons],
            'execution':result.get('execution','unknown'),'reused':result.get('reused','unknown'),'native_returncode':cmd.get('returncode',result.get('returncode','unknown')),'original_native_terminal':done.get('runner_terminal_status',cmd.get('runner_terminal_status','unknown')),
            'native_failure_class':result.get('failure_class',done.get('native_classification','unknown')),'start_evidence':start_evidence,'input_hashes_source':self.alias(path/'INPUT_HASHES.json') if (path/'INPUT_HASHES.json').is_file() else 'unknown','recorded_input_sha256':cmd.get('input_sha256',{}),'provenance':done.get('provenance',cmd.get('provenance',{}))}
        row=self.add(stage,'RUN_IDENTITY',path,'run_id='+record['run_id'],record,ident,native_status=ns,evaluation_status=compact(statuses),implementation_version=str(data.get('code_commit',done.get('provenance',{}).get('code_commit',cmd.get('code_commit','unknown')))),input_identity=compact({'source':record['input_hashes_source'],'cache_sha256':result.get('cache_sha256',native.get('cache_manifest_sha256','unknown')),'config_sha256':result.get('config_sha256','unknown')}),native_output_paths=compact([self.alias(p) for p in payloads if 'eval' not in p.parts and stage!='HX03R2']),evaluation_paths=compact([self.alias(p) for p in jsons+payloads if 'eval' in p.parts or stage=='HX03R2']),retention_status='ARCHIVED_DIRECTORY_PRESENT',notes='RUN directory is not necessarily a new native call; inspect execution/reused. Actual current paths listed, historical scratch paths in source records retained as aliases.')
        self.run_rows.append(row)

    def collect(self):
        self.table(self.docs/'HX_INVENTORY.csv','HX_INVENTORY')
        # Method aliases retain distinct table/native names but share bibliography only.
        for target,origin in {'EXT04_FAR':'EXT04','EXT04_PAR':'EXT04','RTKLIB':'RTKLIB_UNMODIFIED_MOVING_BASE','GINAV':'LC02_GINAV','HARTLEY_S':'Hartley-S','HARTLEY_LIT':'Hartley-LIT','HARTLEY_OFFICIAL':'Hartley-LIT'}.items():self.paper_map[target]=self.paper_map.get(origin,'unknown')
        for stage,root in self.stage_roots.items():
            begin=len(self.records)
            for p in sorted((self.docs/stage).glob('*.md')):self.doc(p,stage)
            for p in sorted(self.docs.glob(stage+'*_PREREG*.md')):self.doc(p,stage)
            for p in sorted((self.docs/stage).glob('*.csv')):self.table(p,stage)
            for p in sorted((self.docs/stage).glob('*.json')):
                if not any(x in p.name for x in ['METHOD_BODY','SHA256_BEFORE','SHA256_AFTER','VERIFY_','ALL_SOURCE','SOURCE_CITATIONS','MANUSCRIPT_DATA','AUDIT_SLOT_DETAIL','EVALUATOR_AUDITS']):self.read(p,stage,emit=False)
            # Existing aggregate locations, identified in stage reports, not a whole-disk scan.
            for sub in ['90_AGGREGATE','90_MANUSCRIPT']:
                q=root/sub
                if q.is_dir():
                    for p in sorted(q.glob('*.csv')):self.table(p,stage)
                    for p in sorted(q.glob('*.json')):
                        if not any(x in p.name for x in ['PROTECTED','SOURCE_CITATIONS','MANUSCRIPT_DATA','EVALUATOR_AUDITS','AUDIT_SLOT_DETAIL']):self.read(p,stage,emit=False)
            for p in sorted(root.glob('*.csv')):self.table(p,stage)
            for p in sorted(root.glob('*.json')):
                if not any(x in p.name for x in ['PROTECTED_METADATA','RTKLIB_SOURCE_SHA256','PREFLIGHT','STAGED','GIT_']):self.read(p,stage,emit=False)
            for n in ['STATE.json','STATE_R2.json','RESULTS.json','EXECUTION_COUNTS.json','EXECUTION_COUNTS_R2.json','COUNTERS.json','RUN_MAPPING_R2.json','LEDGER.jsonl','LEDGER_R2.jsonl']:
                p=root/'00_CONTROL'/n
                if p.is_file():self.read(p,stage,emit=False)
            runs=root/'RUNS'
            for number,path in enumerate(sorted(p for p in runs.iterdir() if p.is_dir()),1):
                jsons,payload=self.walk_run(path,stage);self.run_identity(path,stage,jsons,payload)
                if number%75==0:print('PROGRESS',stage,number,'run directories',flush=True)
            for parent in [self.docs/stage,root/'FIGURES']:
                if parent.is_dir():
                    for p in parent.iterdir():
                        if p.suffix.lower() in ['.png','.pdf','.svg']:self.file(p,stage,figure_paths=compact([self.alias(p)]),notes='Figure export indexed by stat only; no new raster review or performance extraction.')
            self.stage_counters[stage]={'record_rows':len(self.records)-begin,'run_directories':sum(r['stage']==stage for r in self.run_rows),'full_table_files':self.table_counts[stage],'full_metadata_files':self.metadata_counts[stage]}
            print('COMPLETE',stage,self.stage_counters[stage],flush=True)
        # Directly cited explanatory records, separate from the seven result-stage denominators.
        for stage,names in {'HX02D':['HX02D_HARTLEY_DIAGNOSTIC.md','JUDGMENT_ZH.md','FINAL_INTEGRITY.json'],'HX03R':['HX03R1_D12_DIAGNOSIS.md']}.items():
            for name in names:
                p=self.docs/stage/name
                if p.is_file():self.doc(p,stage)
        self.write()

    def write_csv(self,path,rows,local=False):
        with path.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader()
            for row in rows:
                if local:
                    row=dict(row)
                    for k,v in row.items():
                        if isinstance(v,str):
                            for alias,raw in sorted(self.aliases.items(),key=lambda x:len(x[0]),reverse=True):v=v.replace(alias,raw)
                            row[k]=v
                writer.writerow(row)

    def write(self):
        for key,row in self.files.items():
            if key in self.manifest_hashes:
                info=json.loads(row['source_values_json']);info['recorded_sha256']=self.manifest_hashes[key];row['source_values_json']=compact(info)
        self.write_csv(self.out/'EXISTING_HX_INDEX.csv',self.records)
        self.write_csv(self.out/'EXISTING_HX_FILES.csv',self.files.values())
        self.write_csv(self.out/'EXISTING_HX_RUNS.csv',self.run_rows)
        local=Path(self.aliases['<EXT_REPRO_ROOT>'])/'existing_hx.local.csv';self.write_csv(local,self.records+list(self.files.values()),local=True)
        summary={'status':'COLLECTED_WITH_EXPLICIT_DEPTH_LIMITS','start_head_recorded':self.start_head,'data_mode':'mixed_existing_real_and_semisynthetic_with_original_roles_preserved','synthetic_data_used':False,'semisynthetic_data_used':True,'new_native_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,'reference_payload_reads':0,'time_series_payload_reads':0,'project_modules_imported':0,'performance_recomputation':0,'stage_roots':{k:self.alias(v) for k,v in self.stage_roots.items()},'stage_counts':self.stage_counters,'record_rows':len(self.records),'file_rows':len(self.files),'run_identity_rows':len(self.run_rows),'record_kinds':dict(Counter(x['record_kind'] for x in self.records)),'read_depth_counts':dict(Counter(x['read_depth'] for x in self.files.values())),'retention_counts':dict(Counter(x['retention_status'] for x in self.files.values())),'issues':self.issues,'documents_read':self.document_paths,'numeric_preservation':'CSV values retained as original strings. JSON number lexemes retained as strings; no rounding, RMSE, bootstrap or evaluator recomputation. Path-prefix aliases are reversible via ignored roots map.','large_payload_policy':'Stat only; no NAV, pos, heading, error-series or reference body reads. Compressed file presence does not assert CRC/member payload readability.','local_mirror':'<EXT_REPRO_ROOT>/existing_hx.local.csv','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (self.out/'COLLECTION_RECEIPT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        print('TOTAL',compact({k:summary[k] for k in ['record_rows','file_rows','run_identity_rows','record_kinds','retention_counts']}),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--roots',type=Path,required=True);args=parser.parse_args();Collector(args.roots).collect()

if __name__=='__main__':main()
