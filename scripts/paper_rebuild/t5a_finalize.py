#!/usr/bin/env python3
"""Seal the completed T5a evidence and create the requested handoff ZIP; no science calls."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import zlib
import yaml
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.hext.t5a_execution import FLAGS,write_json


def trace_accounting(scratch, ledgers):
    result={}
    for kind,entries in ledgers.items():
        rows=[]
        for entry in entries:
            parts=entry['run_id'].split('__');seq,cfg,variant=parts[:3]
            audit=(scratch/'03_NATIVE'/seq/cfg/variant/'NATIVE_ACCESS_AUDIT.json') if kind=='NATIVE' else (scratch/'04_EVAL'/parts[3]/seq/cfg/variant/'FROZEN_EVALUATOR/EVALUATOR_STRACE_AUDIT.json')
            try:value=json.loads(audit.read_text()).get('trace_open_count','UNAVAILABLE')
            except (OSError,ValueError):value='UNAVAILABLE'
            if not isinstance(value,int) or isinstance(value,bool) or value<0:value='UNAVAILABLE'
            rows.append(dict(run_id=entry['run_id'],trace_open_count=value))
        unknown=sum(r['trace_open_count']=='UNAVAILABLE' for r in rows)
        known=sum(r['trace_open_count'] for r in rows if isinstance(r['trace_open_count'],int))
        result[kind]=dict(trace_open_count='UNAVAILABLE' if unknown else known,known_open_count=known,unknown_slots=unknown,slots=rows)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--code-freeze',required=True);args=parser.parse_args()
    local=yaml.safe_load(Path('configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    contract=yaml.safe_load(Path('configs/paper_rebuild/hext/T5A_CONTRACT_V1.yaml').read_text())
    scratch=Path(local['t5a_scratch']);archive=Path(contract['output_root'].replace('<CLEAN_ROOT>',str(local['clean_root'])))
    summary=json.loads((scratch/'07_HANDOFF/EXECUTION_SUMMARY.json').read_text())
    if summary['code_commit']!=args.code_freeze:raise ValueError('Code freeze mismatch')
    def resolve(value):
        for k,v in local.items():value=value.replace('<'+k.upper()+'>',str(v))
        return Path(value)
    for name,expected in summary['input_hashes'].items():
        if sha256_file(resolve(name))!=expected:raise RuntimeError('HARD_STOP_FINAL_INPUT_HASH '+name)
    frozen=json.loads((scratch/'07_HANDOFF/CODE_FREEZE.json').read_text())['original_figure_hashes']
    original=Path(local['clean_root'])/'stages/CLEAN6_PUBLICATION_FIGURES/figures/v21'
    if any(sha256_file(original/name)!=h for name,h in frozen.items()):raise RuntimeError('FROZEN_FIGURE_MUTATION')
    ledgers={}
    for kind in ('NATIVE','EVALUATOR'):
        p=scratch/'07_HANDOFF'/(kind+'_LEDGER.jsonl');ledgers[kind]=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    trace=trace_accounting(scratch,ledgers)
    completed=summary['status']=='COMPLETED'
    if completed and (len(ledgers['NATIVE'])!=16 or len(summary['native'])!=16 or len(summary['evaluations'])!=32):raise RuntimeError('Incomplete terminal matrix')
    render_path=scratch/'06_FIGURES/T5A_RENDER_MANIFEST.json'
    visual_path=scratch/'07_HANDOFF/VISUAL_REVIEW.json'
    if completed and (not render_path.is_file() or not visual_path.is_file()):raise RuntimeError('Completed delivery requires render manifest and actual visual review')
    if completed and json.loads(visual_path.read_text()).get('status')!='PASS':raise RuntimeError('Visual review incomplete')
    file_hashes={p.relative_to(scratch).as_posix():sha256_file(p) for p in sorted(scratch.rglob('*')) if p.is_file() and p.suffix!='.zip'}
    final={**FLAGS,'status':'PASS_T5A_HEADING_SENSITIVITY_COMPLETE' if completed else 'HARD_STOP_PARTIAL_EVIDENCE',
        'code_freeze':args.code_freeze,'task':'T5a-R','historical_invalid_native':3,'historical_invalid_classification':'INVALID_CONFIG_PARSE',
        'fidelity_native_invocations':summary.get('fidelity_native_invocations',0),'fidelity_evaluator_invocations':summary.get('fidelity_evaluator_invocations',0),'fidelity_gate_route':summary.get('fidelity_route'),'A0':summary.get('a0'),
        'native_budget':16,'native_invocations':len(ledgers['NATIVE']),
        'evaluator_budget':32,'evaluator_invocations':len(ledgers['EVALUATOR']),
        'native_completed':sum(r['status']=='COMPLETED' for r in summary['native']),
        'evaluations_completed':sum(r['row'].get('evaluation_status')=='COMPLETED' for r in summary['evaluations']),
        'parent_trace_open_count':0,'native_trace_open_count':trace['NATIVE']['trace_open_count'],
        'evaluator_trace_open_count':trace['EVALUATOR']['trace_open_count'],'trace_accounting':trace,
        'trace_used_online':False if trace['NATIVE']['trace_open_count']==0 else 'UNAVAILABLE',
        'retries':0,'frozen_inputs_unchanged':True,'frozen_28_figures_and_manifest_unchanged':True,
        'input_hashes':summary['input_hashes'],'artifact_hashes':file_hashes,'scratch_retained':True,'error':summary.get('error')}
    write_json(scratch/'FINAL_SUMMARY.json',final)
    members=[]
    for p in sorted(scratch.rglob('*')):
        if not p.is_file() or p.suffix=='.zip':continue
        data=p.read_bytes();members.append({'name':'T5A/'+p.relative_to(scratch).as_posix(),'source':p,'sha256':hashlib.sha256(data).hexdigest(),'size_bytes':len(data),'crc32':f'{zlib.crc32(data)&0xffffffff:08x}'})
    manifest={**FLAGS,'code_freeze':args.code_freeze,'members':[{k:v for k,v in r.items() if k!='source'} for r in members],
        'self_reference_policy':'MEMBER_MANIFEST.json is validated in the external ZIP_VERIFICATION.json including SHA256 and CRC32.'}
    zpath=scratch/'07_HANDOFF'/Path(contract['handoff']).name
    with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for r in members:z.write(r['source'],r['name'])
        z.writestr('MEMBER_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    checked=[]
    with zipfile.ZipFile(zpath) as z:
        expected={r['name']:r for r in members}
        for item in z.infolist():
            data=z.read(item);digest=hashlib.sha256(data).hexdigest();crc=f'{zlib.crc32(data)&0xffffffff:08x}'
            if crc!=f'{item.CRC:08x}':raise RuntimeError('ZIP_CRC_FAIL')
            if item.filename in expected and digest!=expected[item.filename]['sha256']:raise RuntimeError('ZIP_MEMBER_HASH_FAIL')
            checked.append(dict(name=item.filename,sha256=digest,crc32=crc,size_bytes=len(data)))
    digest=sha256_file(zpath);dest=Path(local['handoff_root'])/zpath.name
    if dest.exists():raise FileExistsError('Preserve existing handoff')
    shutil.copyfile(zpath,dest)
    if sha256_file(dest)!=digest:raise RuntimeError('ZIP_ARCHIVE_HASH_FAIL')
    write_json(scratch/'07_HANDOFF/ZIP_VERIFICATION.json',dict(status='PASS',code_freeze=args.code_freeze,zip_sha256=digest,zip_size_bytes=zpath.stat().st_size,members=checked,ext4_and_G_equal=True))
    for p in sorted(scratch.rglob('*')):
        if not p.is_file() or p.suffix=='.zip':continue
        target=archive/p.relative_to(scratch);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and sha256_file(target)!=sha256_file(p):raise RuntimeError('Existing archive member differs '+str(target))
        if not target.exists():shutil.copyfile(p,target)
        if sha256_file(target)!=sha256_file(p):raise RuntimeError('Archive hash failure')
    print(json.dumps({'status':final['status'],'native':final['native_invocations'],'evaluator':final['evaluator_invocations'],'zip_sha256':digest,'members':len(checked),'size_bytes':dest.stat().st_size},indent=2))

if __name__=='__main__':main()
