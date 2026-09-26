"""HX-05 source receipts and protected-artifact checks; no solver imports."""
from __future__ import annotations
import builtins
import hashlib
import io
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


def forbid_reference_open():
    def wrap(fn):
        def checked(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                name = os.fsdecode(file)
                if 'trace_vrtk' in Path(name).name or name.endswith(('.bag', '.fpl')):
                    raise RuntimeError('HX05_FORBIDDEN_REFERENCE_OPEN: ' + name)
            return fn(file, *args, **kwargs)
        return checked
    builtins.open = wrap(builtins.open)
    io.open = wrap(io.open)


def sha(path):
    path = Path(path)
    if 'trace_vrtk' in path.name or path.suffix in ('.bag', '.fpl'):
        raise RuntimeError('HX05_FORBIDDEN_REFERENCE_HASH')
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def paths(worktree=None):
    w = Path(worktree or Path.cwd()).resolve()
    local = yaml.safe_load((w/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    stages = Path(local['clean_root'])/'stages'
    ext = stages/'CLEAN9_EXTERNAL_COMPARISON'
    return {'W':w, 'STAGES':stages, 'V3':stages/'CLEAN8_PROTOCOL_V3',
            'HX02':ext/'HX02_FIVE_CATEGORY', 'HX02D':ext/'HX02D_HARTLEY_DIAGNOSTIC',
            'HX02E':ext/'HX02E_HARTLEY_OFFICIAL', 'HX03':ext/'HX03_DEGRADATION',
            'HX03R1':ext/'HX03_DEGRADATION/95_D12_DIAGNOSIS',
            'HX03R2':ext/'HX03R2_AUDIT_REEVAL', 'HX05':ext/'HX05_CLOSEOUT',
            'SCRATCH':Path(local['hx02_scratch'])/'HX05', 'EXTERNAL':Path(local['hx02_external_root']),
            'RAW_ROOT':Path(local['raw_root']), 'CLEAN_ROOT':Path(local['clean_root'])}


def dump(path, value, exclusive=True):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def alias(path, roots):
    path = Path(path)
    for key in ('HX05','HX03R2','HX03R1','HX03','HX02E','HX02D','HX02','V3','W','STAGES','EXTERNAL','RAW_ROOT','CLEAN_ROOT'):
        try:return '$'+key+'/'+str(path.relative_to(roots[key]))
        except ValueError:pass
    return str(path)


def resolve(value, roots):
    for key, path in roots.items():
        if value == '$'+key:return path
        if value.startswith('$'+key+'/'):return path/value[len(key)+2:]
    return Path(value)


def protected_metadata(roots):
    output={}
    for key in ('HX02','HX02D','HX02E','HX03','HX03R2'):
        entries={}
        for directory, _, files in os.walk(roots[key]):
            for name in files:
                p=Path(directory)/name;s=p.stat()
                entries[str(p.relative_to(roots[key]))]=[s.st_size,s.st_mtime_ns]
        output[key]=entries
    return output


def disk_guard(roots):
    text=subprocess.check_output(['df','--output=avail','/mnt/e','/mnt/g'],text=True)
    available=[int(x)*1024 for x in text.splitlines()[1:]]
    assert available[0]>=40_000_000_000 and available[1]>=30_000_000_000, 'HX05_DISK_GUARD'
    scratch_bytes=sum(p.stat().st_size for p in roots['SCRATCH'].rglob('*') if p.is_file()) if roots['SCRATCH'].exists() else 0
    assert scratch_bytes<=20_000_000_000,'HX05_SCRATCH_LIMIT'
    return {'df_output':text,'E_available_bytes':available[0],'G_available_bytes':available[1],'scratch_bytes':scratch_bytes}


def verify(roots, phase):
    c=roots['HX05']/'00_CONTROL'
    prior=json.loads((roots['HX03R2']/'00_CONTROL/PREREQUISITE_START_R2.json').read_text())
    baseline=roots['V3']/'00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BASELINE.json'
    expected=json.loads(baseline.read_text())['files_sha256']
    sealed={str(p.relative_to(roots['V3'])):sha(p) for folder in ('07_AGGREGATE','07C_FAILURE_FAMILY_CONFIG','07D_CLASSIFICATION_PROVENANCE') for p in (roots['V3']/folder).rglob('*') if p.is_file()}
    assert sealed==expected and len(sealed)==65,'HX05_SEALED_PIN_MISMATCH'
    methods={name:sha(resolve(name,roots)) for name in prior['method_body_items']}
    assert methods==prior['method_body_items'] and len(methods)==423,'HX05_METHOD_BODY_CHANGED'
    unrelated={name:sha(roots['W']/name) for name in prior['unrelated_untracked_sha256']}
    assert unrelated==prior['unrelated_untracked_sha256'] and len(unrelated)==29,'HX05_UNRELATED_FILE_CHANGED'
    metadata=protected_metadata(roots)
    if phase=='START':dump(c/'PROTECTED_METADATA_START.json',metadata)
    else:
        assert metadata==json.loads((c/'PROTECTED_METADATA_START.json').read_text()),'HX05_PROTECTED_STAGE_CHANGED'
        manifest=c/'SOURCE_PINS.json'
        if manifest.exists():
            pins=json.loads(manifest.read_text())
            assert all(sha(resolve(k,roots))==v for k,v in pins.items()),'HX05_SOURCE_PIN_CHANGED'
    result={'utc':datetime.now(timezone.utc).isoformat(),'phase':phase,'passed':True,
            'sealed_count':65,'sealed_csv_count':59,'baseline_sha256':sha(baseline),
            'sealed_files_sha256':sealed,'method_body_count':423,'method_body_items':methods,
            'unrelated_untracked_count':29,'unrelated_untracked_sha256':unrelated,
            'protected_stage_file_counts':{k:len(v) for k,v in metadata.items()},
            'protected_stage_check':'path, size and mtime_ns; consumed sources separately pinned by content hash',
            'storage':disk_guard(roots),'solver_calls':{'LegSA':0,'external':0}}
    dump(c/('VERIFY_'+phase+'.json'),result)
    return result
