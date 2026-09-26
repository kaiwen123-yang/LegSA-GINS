"""Read retained R2 artifacts only; no solver, evaluator, or raw-data access."""
import builtins
import io
import os
from pathlib import Path

def guarded(fn):
    def call(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            name = os.fsdecode(file)
            if '/data/raw/' in name or 'trace_vrtk' in Path(name).name or name.endswith(('.bag', '.fpl')):
                raise RuntimeError('FORBIDDEN_REFERENCE_ACCESS')
        return fn(file, *args, **kwargs)
    return call
builtins.open = guarded(builtins.open)
io.open = guarded(io.open)

import csv
import gzip
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records

W = Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair')
R = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL')
C = R / '00_CONTROL'
S = Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN9_EXTERNAL_COMPARISON/HX03R2/FINAL_AUDIT_R2')

def digest(path, compressed=False):
    h = hashlib.sha256()
    with (gzip.open(path, 'rb') if compressed else path.open('rb')) as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_text())

def one(slot):
    d = R / 'RUNS' / slot['run_id'] / (slot['version'] + '_R2')
    receipt = read(d / 'ARCHIVE_RECEIPT_R2.json')
    assert receipt['verified']
    for name, expected in receipt['files_sha256'].items():
        assert digest(d / name) == expected, (slot['slot_id'], name)
    for name, expected in receipt['uncompressed_sha256'].items():
        assert digest(d / name, True) == expected, (slot['slot_id'], name, 'decompressed')
    result = read(d / 'RESULT_R2.json')
    audit = read(d / 'EVALUATOR_STRACE_AUDIT_R2.json')
    capture = read(d / 'EVALUATOR_CAPTURE_R2.json')
    detail = read(d / 'AUDIT_DETAIL_R2.json')
    identity = result['scientific_identity']
    for key in ('summary_json', 'error_series_csv'):
        assert identity[key]['R1'] == identity[key]['R2']
    assert digest(d / 'summary_R2.json') == identity['summary_json']['R2']
    assert receipt['uncompressed_sha256']['error_series_R2.csv.gz'] == identity['error_series_csv']['R2']
    assert receipt['uncompressed_sha256']['EVALUATOR_OPENAT_R2.strace.gz'] == audit['strace_sha256']
    assert audit['passed'] and audit['exit_code'] == 0 and not audit['failures']
    assert audit['trace_open_count'] == audit['raw_open_count'] == 1
    assert audit['write_scope']['pass'] and audit['write_scope']['outside_run_write_open_count'] == 0
    tr = audit['trace_open_records'][0]
    assert tr['return_code'] >= 0 and 'O_RDONLY' in tr['flags']
    assert tr['pid'] == capture['pid']
    assert capture['trace_handle_hash_count'] == 1
    assert capture['trace_sha256'] == result['trace_sha256']
    assert capture['evaluator_sha256'] == 'aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da'
    assert audit['module'] == 'legsa_gins.paper_rebuild.hext.hx03r2_observer'
    assert audit['execve_programs'] == ['/usr/bin/python3']
    assert all(audit['environment'][k] == '1' for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'))
    assert detail['reference_extra_opens'] == 0 and detail['unchanged_observer_calls'] == 2
    assert detail['residuals_sha256'] == result['residuals_sha256'] == receipt['files_sha256']['AUDIT_RESIDUALS_R2.csv.gz']
    assert result['old_available_metrics_identity']['passed']
    maxima = []
    for axis, item in detail['extrema'].items():
        maxima.append({'slot_id': slot['slot_id'], 'version': slot['version'], 'role': slot['role'],
                       'axis': axis, 'maximum': item['maximum'], 'time_s': item['time_s'],
                       'index_zero_based': item['index_zero_based'], 'matched_epoch_count': detail['rows'], **item['row']})
    return {'slot': slot['slot_id'], 'files_verified': len(receipt['files_sha256']),
            'uncompressed_verified': len(receipt['uncompressed_sha256']),
            'status': result['audit_status_R2'], 'discrepancy': result['observer_discrepancy_R2'],
            'old_metric_fields': result['old_available_metrics_identity']['field_count'],
            'runtime_seconds': result['runtime_seconds'], 'role': slot['role'],
            'detail': detail, 'audit': audit, 'maxima': maxima}

def write(name, data):
    with (S / name).open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def main():
    assert (C / 'MATRIX_EXIT_CODE_R2.txt').read_text().strip() == '0'
    slots = read(C / 'EVALUATION_SLOTS_R2.json')
    assert len(slots) == len({s['slot_id'] for s in slots}) == 492
    S.mkdir(exist_ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, slots))
    parent = []
    for name in ('VALIDATION_CONTROLLER_OPENAT_R2.strace', 'VALIDATION_CONTROLLER_MAIN_R2.strace',
                 'MATRIX_CONTROLLER_MAIN_R2.strace', 'REPORT_OPENAT_R2.strace'):
        path = C / name
        opens = audited_open_records(path, W)
        raw = [o for o in opens if '/data/raw/' in o['path'] or 'trace_vrtk' in Path(o['path']).name or o['path'].endswith(('.bag', '.fpl'))]
        e_writes = [o for o in opens if o['path'].startswith('/mnt/e/') and ('O_WRONLY' in o['flags'] or 'O_RDWR' in o['flags'])]
        assert not raw and not e_writes, name
        parent.append({'log': name, 'sha256': digest(path), 'raw_opens': 0, 'E_write_opens': 0,
                       'coverage': 'initial failed launch used -f; later controller traces cover main thread, with Python open guard also covering worker threads'})
    events = [json.loads(line) for line in (C / 'LEDGER_R2.jsonl').read_text().splitlines()]
    counts = Counter(e['event'] for e in events)
    assert counts['ARCHIVED'] == 492 and counts['RESERVED'] - counts['PREEXEC_NOT_STARTED'] == 492
    assert len({e['slot_id'] for e in events if e['event'] == 'ARCHIVED'}) == 492
    maxima = [m for r in records for m in r['maxima']]
    with (S / 'AUDIT_MAXIMA_R2.csv').open('x', newline='') as f:
        out = csv.DictWriter(f, fieldnames=list(maxima[0]), lineterminator='\n')
        out.writeheader(); out.writerows(maxima)
    write('AUDIT_SLOT_DETAIL_R2.json', {r['slot']: r['detail'] for r in records})
    write('EVALUATOR_AUDITS_R2.json', {r['slot']: r['audit'] for r in records})
    receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'passed': True,
               'slots': 492, 'scientific_files_equal': 984,
               'archive_files_reverified': sum(r['files_verified'] for r in records),
               'compressed_files_decompressed_and_reverified': sum(r['uncompressed_verified'] for r in records),
               'trace_opens_readonly_hash_checked': 492, 'child_pid_verified': 492,
               'audit_status_counts': dict(Counter(r['status'] for r in records)),
               'maximum_discrepancy': {k: max(r['discrepancy'][k] for r in records) for k in ('horizontal_max_m', 'up_max_m', 'yaw_max_deg')},
               'old_available_slots_with_numeric_fields': sum(r['old_metric_fields'] > 0 for r in records),
               'old_available_numeric_fields_equal': sum(r['old_metric_fields'] for r in records),
               'launch_attempts': counts['RESERVED'], 'preexec_failures': counts['PREEXEC_NOT_STARTED'],
               'scientific_evaluation_calls': 492, 'native_calls': 0, 'legsa_native': 0, 'legsa_evaluation': 0,
               'parent_trace_checks': parent, 'audit_script_sha256': digest(Path(__file__)),
               'files_sha256': {p.name: digest(p) for p in S.iterdir() if p.is_file()}}
    write('ARTIFACT_VERIFICATION_R2.json', receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('parent_trace_checks','files_sha256')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
