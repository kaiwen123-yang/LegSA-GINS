#!/usr/bin/env python3
"""Read-only mapping of HX-03 retained evaluation slots for HX-03R-2."""
from __future__ import annotations

import builtins
import io
import os
from pathlib import Path

def deny_reference(original):
    def checked(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            name = os.fsdecode(file)
            if '/data/raw/' in name or 'trace_vrtk' in Path(name).name or name.endswith(('.bag', '.fpl')):
                raise RuntimeError('HARD_STOP_CONTROLLER_REFERENCE_OPEN: ' + name)
        return original(file, *args, **kwargs)
    return checked
builtins.open = deny_reference(builtins.open)
io.open = deny_reference(io.open)

import csv
import hashlib
import json
from collections import Counter
import yaml


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, obj):
    with path.open('x') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def main():
    W = Path.cwd()
    local = yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    stages = Path(local['clean_root'])/'stages'
    old = stages/'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
    root = stages/'CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL'
    control = root/'00_CONTROL'
    config = W/'configs/paper_rebuild/hext/HX03'
    runs = list(csv.DictReader((config/'RUN_MANIFEST.csv').open()))
    slots, mapping, pins = [], [], {}
    counts = Counter()
    for run in runs:
        rd = old/'RUNS'/run['run_id']
        result = json.loads((rd/'RESULT.json').read_text())
        manifest = json.loads((rd/'OUTPUT_HASHES.json').read_text())
        for path in (rd/'RESULT.json', rd/'OUTPUT_HASHES.json'):
            pins[str(path).replace(str(old), '$HX03')] = sha(path)
        if sha(rd/'RESULT.json') != manifest['RESULT.json']:
            raise RuntimeError('HARD_STOP_OLD_RESULT_HASH')
        own = 0
        for version in ('v3','v2'):
            ep = rd/'eval'/version
            if not (ep/'EVALUATION_RESULT.json').is_file():
                continue
            own += 1
            record = json.loads((ep/'EVALUATION_RESULT.json').read_text())
            spec = json.loads((ep/'SPEC.json').read_text())
            scratch_marker = '/HX03/RUNS/'+run['run_id']+'/'
            if scratch_marker not in spec['nav']:
                raise RuntimeError('HARD_STOP_NAV_SOURCE_MAPPING')
            actual_nav = rd/spec['nav'].split(scratch_marker,1)[1]
            rel = str(actual_nav.relative_to(rd))
            expected = manifest[rel]
            if expected != record['row']['evaluator_nav_sha256']:
                raise RuntimeError('HARD_STOP_NAV_HASH_DECLARATIONS_DIFFER')
            slot = {**run, 'version':version, 'slot_id':run['run_id']+'__'+version,
                'old_run_dir':str(rd), 'old_eval_dir':str(ep),
                'native_failure_class':result['failure_class'],
                'role':'PRE_FAILURE' if result['failure_class']=='ALGORITHM_FAILURE_DIVERGED' else 'FULL',
                'nav':str(actual_nav), 'nav_sha256':expected,
                'native_nav':str(rd/'native/EXACT_EVALUATOR_INPUT.nav'),
                'native_nav_sha256':result['source_nav_sha256'],
                'evaluator':spec['evaluator'], 'trace':spec['trace'], 'trace_sha256':spec['trace_sha256'],
                'base_time':spec['base_time'], 'window':spec['window'],
                'old_summary_sha256':manifest['eval/'+version+'/OUTPUT/summary.json'],
                'old_error_series_sha256':manifest['eval/'+version+'/OUTPUT/error_series.csv'],
                'old_audit_passed':record['capture']['consistency']['passed'],
                'old_horizontal_discrepancy_m':record['capture']['consistency']['horizontal_max_m'],
                'old_evaluation_result_sha256':manifest['eval/'+version+'/EVALUATION_RESULT.json']}
            for name in ('EVALUATION_RESULT.json','SPEC.json','OUTPUT/EVALUATOR_CAPTURE.json','OUTPUT/summary.json'):
                key='eval/'+version+'/'+name
                digest=sha(ep/name)
                if digest != manifest[key]:
                    raise RuntimeError('HARD_STOP_OLD_EVALUATION_HASH: '+key)
                pins[str(ep/name).replace(str(old),'$HX03')]=digest
            slots.append(slot)
        counts[(result['reused'],result['failure_class'],own)] += 1
        source=result['source_run_dir'].replace('$HX03',str(old))
        kind='OWN_EVALUATION' if own else 'NO_EVALUATION_OUTPUT'
        if not own and result['failure_class']=='NONE':
            if run['type'] in ('D43','D42','D46','D47','D50'):
                source=str(old/'RUNS'/f"BY2__{run['method']}__LIT__C00__NA")
                kind='C00_BYTE_IDENTITY_REUSE'
            elif run['method']=='LC01-BR' and run['case_id']=='C00':
                source=str(old/'RUNS/BY2__LC01__LIT__C00__NA')
                kind='BR_C00_NATIVE_IDENTITY_ONLY'
            elif result['reused']:
                kind='EXISTING_EQUIVALENCE_REUSE'
        mapping.append({**run,'native_previously_invoked':not result['reused'],
            'native_failure_class':result['failure_class'],'existing_evaluation_slots':own,
            'mapping_kind':kind,'evaluation_source_run_id':Path(source).name,
            'source_nav_sha256':result['source_nav_sha256']})
    if len(slots)!=492 or len(mapping)!=381 or sum(r['native_previously_invoked'] for r in mapping)!=285:
        raise RuntimeError('HARD_STOP_RUN_COUNT_DISAGREEMENT')
    write(control/'EVALUATION_SLOTS_R2.json',slots)
    write(control/'RUN_MAPPING_R2.json',mapping)
    write(control/'OLD_RECORD_PINS_R2.json',pins)
    write(control/'SCOPE_COUNTS_R2.json', {'run_manifest_rows':len(mapping),'original_native':285,
        'existing_evaluation_slots':492,'identity_evaluation_slots':4,'matrix_evaluation_slots':488,
        'counts':[{'reused':k[0],'failure_class':k[1],'evaluations_per_run':k[2],'runs':v} for k,v in counts.items()],
        'native_calls_this_task':0,'evaluator_calls_this_task':0,'reference_opens_this_process':0})
    print('mapped 381 rows / 285 original natives / 492 existing evaluation slots; no evaluations invoked')


if __name__=='__main__':
    main()
