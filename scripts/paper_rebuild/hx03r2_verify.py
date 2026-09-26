#!/usr/bin/env python3
"""R2 registration/results identity receipts, without solver or evaluator calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime,timezone
import yaml


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('registration','result'),required=True);phase=parser.parse_args().phase
    W=Path.cwd();local=yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    stages=Path(local['clean_root'])/'stages';v3=stages/'CLEAN8_PROTOCOL_V3';root=stages/'CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL';c=root/'00_CONTROL';old=root.parent/'HX03_DEGRADATION'
    initial=json.loads((c/'PREREQUISITE_START_R2.json').read_text())
    base=v3/'00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BASELINE.json';expected=json.loads(base.read_text())['files_sha256']
    current={str(p.relative_to(v3)):sha(p) for d in ('07_AGGREGATE','07C_FAILURE_FAMILY_CONFIG','07D_CLASSIFICATION_PROVENANCE') for p in (v3/d).rglob('*') if p.is_file()}
    assert current==expected==initial['sealed_files_sha256'] and len(current)==65
    methods={k:sha(Path(k.replace('$W',str(W)).replace('$EXTERNAL',local['hx02_external_root']))) for k in initial['method_body_items']}
    assert methods==initial['method_body_items'] and len(methods)==423
    untracked={k:sha(W/k) for k in initial['unrelated_untracked_sha256']}
    assert untracked==initial['unrelated_untracked_sha256'] and len(untracked)==29
    code=json.loads((c/'CODE_PINS_R2.json').read_text())
    assert all(sha(W/k)==v for k,v in code.items())
    oldpins=json.loads((c/'OLD_RECORD_PINS_R2.json').read_text())
    assert all(sha(Path(k.replace('$HX03',str(old))))==v for k,v in oldpins.items())
    metadata={}
    for d,dirs,files in os.walk(old):
        for name in files:
            p=Path(d)/name;s=p.stat();metadata[str(p.relative_to(old))]=[s.st_size,s.st_mtime_ns]
    assert metadata==json.loads((c/'HX03_METADATA_START_R2.json').read_text())
    available={p:os.statvfs(p).f_bavail*os.statvfs(p).f_frsize for p in ('/mnt/e','/mnt/g')}
    assert available['/mnt/e']>=40_000_000_000 and available['/mnt/g']>=30_000_000_000
    events=[json.loads(x) for x in (c/'LEDGER_R2.jsonl').read_text().splitlines()]
    attempts=sum(e['event']=='RESERVED' for e in events);preexec=sum(e['event']=='PREEXEC_NOT_STARTED' for e in events);completed=sum(e['event']=='ARCHIVED' for e in events)
    assert attempts-preexec==completed==(6 if phase=='registration' else 492)
    record={'utc':datetime.now(timezone.utc).isoformat(),'phase':phase,'passed':True,
        'sealed_count':65,'sealed_csv_count':59,'baseline_sha256':sha(base),'sealed_files_sha256':current,
        'method_body_count':423,'method_body_items':methods,'unrelated_untracked_count':29,
        'code_pin_count':len(code),'old_record_pin_count':len(oldpins),
        'HX03_existing_metadata_unchanged':len(metadata),'HX03_preservation':'all file paths/sizes/mtime_ns unchanged; read record pins and each used NAV verified separately',
        'disk_available_bytes':available,'external_evaluation':completed,'launch_attempts':attempts,'preexec_launch_failures':preexec,
        'native_calls':0,'legsa_native':0,'legsa_evaluation':0}
    target=c/('BEFORE_REGISTRATION_R2.json' if phase=='registration' else 'BEFORE_RESULTS_R2.json')
    with target.open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ('sealed_files_sha256','method_body_items')},indent=2))


if __name__=='__main__':main()
