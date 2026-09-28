#!/usr/bin/env python3
"""Three input integrations and three audited relative-pose children; no solver."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from legsa_gins.paper_rebuild.hext.hx05_common import paths, sha, dump, disk_guard, forbid_reference_open, resolve
from legsa_gins.paper_rebuild.hext.hx05_leg_dr import compute, compare_c4_metrics
from legsa_gins.paper_rebuild.hext.hx02_evaluation_process import run_child


def main():
    forbid_reference_open()
    def guard(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0]))
            if 'trace_vrtk' in p.name or p.suffix.lower() in ('.bag', '.fpl'):
                raise RuntimeError('HARD_STOP_CONTROLLER_REFERENCE_OPEN')
    sys.addaudithook(guard)
    p = paths(); control = p['HX05']/'00_CONTROL'
    contract_path = p['W']/'configs/paper_rebuild/hext/HX05_CONTRACT.json'
    contract = json.loads(contract_path.read_text())
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert subprocess.check_output(['git', 'show', '-s', '--format=%s', commit], text=True).strip() == 'prereg(hx05): closeout definitions'
    assert not subprocess.check_output(['git', 'diff', '--name-only']).strip()
    assert all(sha(p['W']/f) == h for f, h in contract['code_sha256'].items())
    assert all(sha(resolve(f, p)) == h for f, h in json.loads((control/'SOURCE_PINS.json').read_text()).items())
    assert json.loads((control/'VERIFY_REGISTRATION.json').read_text())['passed']
    ledger = control/'EXECUTION_LEDGER.jsonl'
    assert not ledger.exists(), 'NO_AUTOMATIC_REPLAY'
    counts = {'legsa_native': 0, 'legsa_evaluation': 0, 'external_native': 0,
              'leg_dr_integrations': 0, 'relative_pose_evaluation': 0, 'reference_opens': 0}
    def event(status, **extra):
        record = {'status': status, 'counts': dict(counts), **extra}
        with ledger.open('a') as f:
            f.write(json.dumps(record, ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())
        dump(control/'STATE.json', record, exclusive=False)
        (control/'PROGRESS.txt').write_text(json.dumps(record, ensure_ascii=False)+'\n')
        print(json.dumps(record, ensure_ascii=False), flush=True)
    try:
        for seq, sequence in contract['sequences'].items():
            disk = disk_guard(p)
            out = p['SCRATCH']/'RUNS'/seq
            out.mkdir(parents=True, exist_ok=False)
            counts['leg_dr_integrations'] += 1
            event('INTEGRATION_INTENT', sequence=seq, disk=disk)
            start = time.monotonic()
            receipt = compute(p, seq, sequence, out)
            nav = out/'NAV.csv'
            trace = p['RAW_ROOT']/sequence['trace_relative_path']
            spec = {k: sequence[k] for k in ('base_time', 'window', 'baseline_median_m', 'trace_sha256')}
            spec.update(sequence_id=seq, trace=str(trace), branches={'LEG-DR': {'nav': str(nav), 'nav_sha256': sha(nav)}})
            counts['relative_pose_evaluation'] += 1
            event('EVALUATOR_INTENT', sequence=seq)
            ev = run_child('RELATIVE_POSE', spec, workdir=out/'eval', code_root=p['W'],
                           raw_root=p['RAW_ROOT'], clean_root=p['CLEAN_ROOT'], trace=trace, timeout_seconds=600)
            counts['reference_opens'] += ev['audit']['trace_open_count']
            evaluation = json.loads((Path(ev['outdir'])/'RELATIVE_POSE_METRICS.json').read_text())
            assert evaluation['trace_sha256_observed'] == sequence['trace_sha256']
            metrics = evaluation['branches']['LEG-DR']
            assert metrics['evaluation_status'] == 'EVALUATED'
            # Long-table naming aliases; original evaluator keys are retained.
            metrics.update(aligned_horizontal_rmse_m=metrics['horizontal_rmse_m'],
                           aligned_up_rmse_m=metrics['up_rmse_m'], aligned_yaw_rmse_deg=metrics['yaw_rmse_deg'])
            gate = compare_c4_metrics(p, metrics) if seq == 'BY2' else {'status': 'BY2_ONLY_GATE'}
            result = {'sequence': seq, 'role': 'INPUT_REFERENCE', 'code_commit': commit,
                      'contract_sha256': sha(contract_path), 'nav_sha256': sha(nav), 'metrics': metrics,
                      'integration': receipt, 'C4_metric_gate': gate, 'audit': ev['audit'],
                      'wall_seconds': time.monotonic()-start}
            dump(out/'RESULT.json', result)
            hashes = {str(f.relative_to(out)): sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
            dump(out/'OUTPUT_HASHES.json', hashes)
            destination = p['HX05']/'RUNS'/seq
            shutil.copytree(out, destination)
            assert all(sha(destination/f) == h for f, h in hashes.items())
            assert sha(out/'OUTPUT_HASHES.json') == sha(destination/'OUTPUT_HASHES.json')
            event('ARCHIVE_VERIFIED', sequence=seq, files=len(hashes)+1, C4_metric_gate=gate)
            shutil.rmtree(out)
            assert gate.get('passed', True), 'HARD_STOP_LEG_DR_C4_METRIC_MISMATCH'
        assert counts['relative_pose_evaluation'] == counts['reference_opens'] == 3
        assert all(sha(p['W']/f) == h for f, h in contract['code_sha256'].items())
        dump(control/'EXECUTION_COUNTS.json', counts)
        event('LEG_DR_COMPLETE', code_commit=commit)
    except Exception as exc:
        event('HARD_STOP', exception=type(exc).__name__, reason=str(exc), no_retry=True)
        dump(control/'HARD_STOP.json', {'exception': type(exc).__name__, 'reason': str(exc), 'counts': counts})
        raise


if __name__ == '__main__':
    main()
