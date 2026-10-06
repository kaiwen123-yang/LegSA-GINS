#!/usr/bin/env python3
"""Byte-preserving stage-2 supplement to the pinned 370-member CLEAN5 handoff."""
from __future__ import annotations
import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path,PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile
import yaml

V1_SHA='c319c7b1f82d71f06409d234d10db5bdb0db1fb869d9cb7a715452796b1c2858'
V1_COUNT=370
PARITY='stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF'
CALIBRATED='stages/CLEAN5_CALIBRATED_SENSOR_MODEL'
PARITY_DIRS=(
 '00_PARITY_TARGET_AND_AUDITS','08_AGGREGATE','10_IMU_PROCESSING/00_AUDITS','10_IMU_PROCESSING/08_AGGREGATE',
 '11_VERTICAL_DIAGNOSIS/01_ANALYSIS','12_PARITY_GENERALIZATION/08_AGGREGATE',
 '12_PARITY_GENERALIZATION/BY2H/08_AGGREGATE','12_PARITY_GENERALIZATION/BY2O/08_AGGREGATE','13_NOISE_MODEL_SENSITIVITY/08_AGGREGATE')
CALIBRATED_DIRS=('00_CALIBRATION','08_AGGREGATE','BY2/08_AGGREGATE','BY2H/08_AGGREGATE','BY2O/08_AGGREGATE')
PARITY_METADATA=(
 'P02_TERMINAL.json','P02_CONTINUED_TERMINAL.json','P02_FINAL_TERMINAL.json','P02_DELIVERY.json',
 '04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json','04_PARITY_SEAL/PARITY_OUTPUT_SEAL_CONTINUED.json',
 '09_EXTERNAL_COMPLETION_AUDIT/COMPLETION_TERMINAL.json','10_IMU_PROCESSING/P03_TERMINAL.json','10_IMU_PROCESSING/P03_DELIVERY.json',
 '10_IMU_PROCESSING/04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json','11_VERTICAL_DIAGNOSIS/P04_DIAGNOSIS_TERMINAL.json',
 '11_VERTICAL_DIAGNOSIS/02_SEAL/DIAGNOSIS_OUTPUT_SEAL.json','12_PARITY_GENERALIZATION/P04_TERMINAL.json',
 '12_PARITY_GENERALIZATION/BY2H/04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json','12_PARITY_GENERALIZATION/BY2O/04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json',
 '13_NOISE_MODEL_SENSITIVITY/P05_TERMINAL.json','13_NOISE_MODEL_SENSITIVITY/04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json',
 '13_NOISE_MODEL_SENSITIVITY/04_PARITY_SEAL/ORIGIN_IDENTITY_GATE.json')
CALIBRATED_METADATA=('CALIBRATED_TERMINAL.json','04_CALIBRATED_SEAL/CALIBRATED_OUTPUT_SEAL.json','04_CALIBRATED_SEAL/EVALUATION_ARTIFACT_SEAL.json','00_CONTROL/BC_INDEPENDENT_REVIEW.json')
DOCS=('CLEAN5_PARITY_PLAN.md','CLEAN5_PARITY_RESULTS.md','CLEAN5_IMU_PARITY_RESULTS.md',
 'CLEAN5_VERTICAL_DIAGNOSIS.md','CLEAN5_PARITY_GENERALIZATION_RESULTS.md','CLEAN5_NOISE_MODEL_SENSITIVITY.md','CLEAN5_STAGE2_CLOSEOUT.md','A04_F04_ROLE_DECISION_RULE.md','CONVERSATION_HANDOFF.md','CLEAN5_SENSOR_CALIBRATION_RECORD.md','CLEAN5_CALIBRATED_CHAIN_RESULTS.md')
CONTRACTS=('CLEAN5_PARITY_CONTRACT.yaml','CLEAN5_PARITY_P04_CONTRACT.yaml','CLEAN5_PARITY_P05_CONTRACT.yaml',
 'CLEAN5_CALIBRATED_SENSOR_MODEL_CONTRACT.yaml','CLEAN5_CALIBRATED_SENSOR_MODEL.yaml','CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml',
 'CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml','CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml')
DERIVED_TRACE=PARITY+'/11_VERTICAL_DIAGNOSIS/01_ANALYSIS/TRACE_NATIVE_DIFFERENCE_VELOCITY.csv'
DERIVED_TRACE_SHA='c80a4e92a2023c770bac599556b2d67409b3f72ec5ea26c2a132a4bef6de8d3a'
TABLE_EXTENSIONS={'.csv','.json','.yaml','.yml','.md'}


def safe_member(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or p.as_posix()!=name or any(ord(c)<32 for c in name):raise ValueError('Unsafe archive member')
    return name


def safe_path(path,root):
    path=Path(path).absolute();root=Path(root).absolute()
    if '..' in path.parts or path.is_symlink() or any(p.is_symlink() for p in path.parents):raise ValueError('Symlink/traversal source')
    if root not in path.parents or not path.is_file():raise ValueError('Source missing/outside approved root')
    if not stat.S_ISREG(path.stat().st_mode):raise ValueError('Source is not a regular file')
    return path


def digest(path):
    h=sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def classify_source(path,clean_root):
    rel=path.relative_to(clean_root).as_posix()
    if re.match(r'trace.*\.csv(?:\.gz)?$',path.name,re.I):
        if rel!=DERIVED_TRACE or digest(path)!=DERIVED_TRACE_SHA:raise ValueError('Forbidden reference trace payload')
        return 'DERIVED_DIAGNOSTIC_ONLY'
    if path.suffix.lower() in {'.bag','.fpl','.nav','.imu','.gnss','.npz','.npy'} or path.name.startswith(('KF_GINS_','LegSA_PORT_','EVAL_NAV')):raise ValueError('Forbidden runtime/provider/raw payload')
    if path.suffix.lower() not in TABLE_EXTENSIONS:raise ValueError('Unapproved extension')
    return 'COPIED_SOURCE_TABLE_OR_METADATA'


def git_gate(code,expected_head,expected_remote,remote_ref):
    if expected_head!=expected_remote or not re.fullmatch('[0-9a-f]{40}',expected_head):raise ValueError('Expected final HEAD/remote mismatch')
    def git(*args):return subprocess.run(['git','-C',str(code),*args],check=True,capture_output=True,text=True).stdout.strip()
    if git('rev-parse','HEAD')!=expected_head:raise ValueError('Final code HEAD differs')
    if git('status','--porcelain','--untracked-files=no'):raise ValueError('Tracked final code/document changes are not committed')
    remote=git('ls-remote','--exit-code','origin',remote_ref).splitlines()
    if len(remote)!=1 or remote[0].split()[0]!=expected_remote:raise ValueError('Remote branch differs from expected final HEAD')
    return {'head':expected_head,'remote_head':expected_remote,'remote_ref':remote_ref,'tracked_worktree_clean':True}


def collect_sources(clean,code):
    """Explicit directories only; never inspect a provider/run/evaluator payload root."""
    sources={};skipped=[]
    def add(path,root,alias,prefix):
        path=safe_path(path,root);relative=path.relative_to(root).as_posix();member=safe_member(prefix+'/'+relative)
        if root==clean:role=classify_source(path,clean)
        else:role='COMMITTED_DOCUMENT_OR_CONTRACT'
        if member in sources:raise ValueError('Duplicate supplemental archive member')
        table={}
        if path.suffix.lower()=='.csv':
            with path.open(newline='',encoding='utf-8-sig') as handle:
                reader=csv.reader(handle);header=next(reader,None)
                if header is None:raise ValueError('Empty CSV lacks schema')
                count=0
                for cells in reader:
                    if len(cells)!=len(header):raise ValueError('Malformed CSV row')
                    count+=1
            table={'csv_header':header,'csv_row_count':count,'column_selection_applied':False}
        stamp=path.stat();sources[member]={'path':path,'source_alias':alias+'/'+relative,'sha256':digest(path),'bytes':stamp.st_size,'mtime_ns':stamp.st_mtime_ns,'role':role,**table}
    for base,dirs in [(PARITY,PARITY_DIRS),(CALIBRATED,CALIBRATED_DIRS)]:
        for relative in dirs:
            directory=clean/base/relative
            if not directory.is_dir() or directory.is_symlink() or any(p.is_symlink() for p in directory.parents):raise ValueError('Missing/symlink required evidence directory '+base+'/'+relative)
            for path in sorted(directory.rglob('*')):
                if path.is_symlink():raise ValueError('Symlink in allowed evidence directory')
                if not path.is_file():continue
                if path.suffix.lower() in {'.bag','.fpl','.nav','.imu','.gnss','.npz','.npy'}:raise ValueError('Forbidden payload in approved table directory')
                if path.suffix.lower() not in TABLE_EXTENSIONS:
                    skipped.append({'source':'<CLEAN_ROOT>/'+path.relative_to(clean).as_posix(),'reason':'not a table/metadata suffix'});continue
                add(path,clean,'<CLEAN_ROOT>','STAGE2/CLEAN_ROOT')
    for base,names in [(PARITY,PARITY_METADATA),(CALIBRATED,CALIBRATED_METADATA)]:
        for name in names:add(clean/base/name,clean,'<CLEAN_ROOT>','STAGE2/CLEAN_ROOT')
    add(code/'AGENTS.md',code,'<CODE_ROOT>','STAGE2/CODE_ROOT')
    add(code/'scripts/paper_rebuild/clean5_pack_v2.py',code,'<CODE_ROOT>','STAGE2/CODE_ROOT')
    for name in DOCS:add(code/'docs/paper_rebuild'/name,code,'<CODE_ROOT>','STAGE2/CODE_ROOT')
    for name in CONTRACTS:add(code/'configs/paper_rebuild/clean5'/name,code,'<CODE_ROOT>','STAGE2/CODE_ROOT')
    return sources,skipped


def seal_crosschecks(sources,clean):
    """Cross-check selected files when a frozen seal already records them; no unselected reads."""
    indexed={v['path']:v for v in sources.values()};checks=[]
    for entry in sources.values():
        p=entry['path']
        if p.suffix!='.json' or 'SEAL' not in p.name:continue
        obj=json.loads(p.read_text());mapping=obj.get('files_sha256')
        if not isinstance(mapping,dict):continue
        base=p.parent.parent
        if '11_VERTICAL_DIAGNOSIS' in p.parts:base=clean/PARITY/'11_VERTICAL_DIAGNOSIS'
        for rel,expected in mapping.items():
            safe_member(rel);target=(base/rel).absolute()
            if target in indexed:
                if indexed[target]['sha256']!=expected:raise ValueError('Selected file differs from existing frozen seal')
                checks.append({'source_alias':indexed[target]['source_alias'],'seal_alias':entry['source_alias'],'sha256':expected})
    return checks


def terminal_gates(clean):
    expected=[(PARITY+'/P02_FINAL_TERMINAL.json','COMPLETED_WITH_V2E_NATIVE_FAILURE'),(PARITY+'/10_IMU_PROCESSING/P03_TERMINAL.json','COMPLETED_WITH_P02_V2E_UNAVAILABLE'),
        (PARITY+'/11_VERTICAL_DIAGNOSIS/P04_DIAGNOSIS_TERMINAL.json','COMPLETED'),
        (PARITY+'/12_PARITY_GENERALIZATION/P04_TERMINAL.json','COMPLETED'),
        (PARITY+'/13_NOISE_MODEL_SENSITIVITY/P05_TERMINAL.json','COMPLETED'),
        (CALIBRATED+'/CALIBRATED_TERMINAL.json','COMPLETED')]
    result=[]
    for rel,status in expected:
        path=safe_path(clean/rel,clean);obj=json.loads(path.read_text());actual=obj.get('status',obj.get('terminal_status'))
        if actual!=status:raise ValueError('Required frozen terminal status differs: '+rel)
        if rel==CALIBRATED+'/CALIBRATED_TERMINAL.json' and (obj.get('run_count')!=15 or obj.get('evaluation',{}).get('evaluator_invocation_count')!=30):raise ValueError('Calibrated 15-run/30-evaluation terminal missing')
        result.append({'source_alias':'<CLEAN_ROOT>/'+rel,'status':actual,'sha256':digest(path)})
    return result


def copy_package(v1,output,sources,metadata,*,expected_v1_sha=V1_SHA,expected_v1_count=V1_COUNT):
    """Copy exact member contents; intentionally independent from the v1 builder."""
    v1=Path(v1).absolute();output=Path(output).absolute()
    safe_path(v1,v1.parent)
    if digest(v1)!=expected_v1_sha:raise ValueError('Inherited v1 ZIP identity mismatch')
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents) or '..' in output.parts:raise FileExistsError('Exclusive ZIP output required')
    entries=[];names=set();generated={'STAGE2/README.md','STAGE2/IDENTITY_PROBE.json'}
    with zipfile.ZipFile(v1) as original:
        infos=original.infolist()
        if len(infos)!=expected_v1_count:raise ValueError('Inherited member count mismatch')
        for info in infos:
            name=safe_member(info.filename)
            if name in names or info.is_dir() or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:raise ValueError('Unsafe or duplicate inherited ZIP entry')
            names.add(name)
        if names&set(sources) or (names|set(sources))&generated:raise ValueError('Supplement would replace an existing member')
        with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as target:
            for info in infos:
                h=sha256();size=0
                with original.open(info) as src,target.open(info,'w',force_zip64=True) as dst:
                    for chunk in iter(lambda:src.read(1024*1024),b''):h.update(chunk);size+=len(chunk);dst.write(chunk)
                entries.append({'member':info.filename,'sha256':h.hexdigest(),'bytes':size,'source_alias':'<USER_HOME>/clean5_handoff.zip#'+info.filename,'source_zip_sha256':expected_v1_sha,'role':'INHERITED_V1_CONTENT_UNCHANGED'})
            for name,entry in sorted(sources.items()):
                safe_member(name);path=entry['path'];safe_path(path,path.parent);before=path.stat()
                if (before.st_size,before.st_mtime_ns)!=(entry['bytes'],entry['mtime_ns']):raise ValueError('Source changed since collection')
                h=sha256();size=0
                with path.open('rb') as src,target.open(name,'w',force_zip64=True) as dst:
                    for chunk in iter(lambda:src.read(1024*1024),b''):h.update(chunk);size+=len(chunk);dst.write(chunk)
                after=path.stat()
                if h.hexdigest()!=entry['sha256'] or (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns):raise ValueError('Source changed during byte copy')
                entries.append({k:entry[k] for k in ['source_alias','sha256','bytes','role','csv_header','csv_row_count','column_selection_applied'] if k in entry}|{'member':name,'member_sha256':h.hexdigest(),'bytes_unchanged':True})
            readme=('CLEAN5 stage-2 handoff. The pinned v1 archive\'s 370 original member contents are retained unchanged.\n'
                'STAGE2 copies complete source CSV/JSON/YAML/Markdown bytes; no scalar columns are removed or recomputed.\n'
                'No new NAV/STD/provider/raw-reference payload is added. Inherited v1 display-only samples retain their original roles.\n'
                'The sole TRACE_NATIVE_DIFFERENCE_VELOCITY.csv exception is DERIVED_DIAGNOSTIC_ONLY, not a reference velocity contract.\n'
                'P05 is SENSITIVITY_NOT_FROZEN; P06 is NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL. Original anchors and Outcome remain authoritative.\n').encode()
            target.writestr('STAGE2/README.md',readme);entries.append({'member':'STAGE2/README.md','sha256':sha256(readme).hexdigest(),'bytes':len(readme),'role':'GENERATED_PACKAGE_DESCRIPTION'})
            probe={**metadata,'status':'PACKAGE_CONTENTS_VALIDATED','inherited_zip_sha256':expected_v1_sha,'inherited_member_count':len(infos),'supplemental_source_count':len(sources),
                'data_mode':'frozen_real_evidence_package','synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False,
                'entry_count':len(entries)+1,'members':entries,'self_hash_policy':'IDENTITY_PROBE.json excluded from own member digest list; whole ZIP SHA reported externally',
                'raw_source_open_count':0,'solver_invocation_count':0,'evaluator_invocation_count':0,'metric_recomputation_count':0,'source_scalar_columns_removed':0,
                'source_bytes_modified':False,'v1_builder_invoked':False}
            target.writestr('STAGE2/IDENTITY_PROBE.json',json.dumps(probe,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    if digest(v1)!=expected_v1_sha:raise ValueError('Inherited archive changed during packaging')
    with zipfile.ZipFile(output) as check:
        if len(check.infolist())!=probe['entry_count'] or len(set(check.namelist()))!=probe['entry_count']:raise ValueError('Output member count mismatch')
        for entry in entries:
            h=sha256()
            with check.open(entry['member']) as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=entry['sha256']:raise ValueError('Output member content mismatch')
    return {'status':'PASS','sha256':digest(output),'bytes':output.stat().st_size,'entry_count':probe['entry_count'],'inherited_members':len(infos),'new_sources':len(sources)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-root',type=Path,required=True);p.add_argument('--local-config',type=Path,required=True)
    p.add_argument('--expected-head',required=True);p.add_argument('--expected-remote-head',required=True)
    p.add_argument('--remote-ref',default='refs/heads/stage/clean3-math-repair')
    args=p.parse_args(argv);code=args.code_root.absolute();local=yaml.safe_load(args.local_config.read_text())['paths'];clean=Path(local['clean_root']).absolute()
    raw=Path(local['raw_root']).absolute()
    if clean==raw or raw in clean.parents or clean in raw.parents:raise ValueError('CLEAN_ROOT/RAW_ROOT overlap')
    if Path(local['code_root']).absolute()!=code:raise ValueError('Local code alias differs')
    git=git_gate(code,args.expected_head,args.expected_remote_head,args.remote_ref)
    sources,skipped=collect_sources(clean,code);seals=seal_crosschecks(sources,clean);terminals=terminal_gates(clean)
    out=Path.home()/'clean5_handoff_v2.zip';v1=Path.home()/'clean5_handoff.zip'
    result=copy_package(v1,out,sources,{'git_identity':git,'terminal_gates':terminals,'frozen_seal_crosschecks':seals,'excluded_non_table_files':skipped})
    if git_gate(code,args.expected_head,args.expected_remote_head,args.remote_ref)!=git:raise ValueError('Code/remote changed while packing')
    print(json.dumps({'output':'<USER_HOME>/clean5_handoff_v2.zip',**result},ensure_ascii=False));return 0

if __name__=='__main__':
    sys.dont_write_bytecode=True
    raise SystemExit(main())
