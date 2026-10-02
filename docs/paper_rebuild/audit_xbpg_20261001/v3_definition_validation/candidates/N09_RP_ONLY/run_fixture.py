#!/usr/bin/env python3
"""N09-only isolated build and NEW pure synthetic fixture processes; no real data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[5]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['build', 'fixtures'], required=True)
    args = parser.parse_args()
    aliases = json.loads((CODE / 'configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json').read_text())['aliases']
    base = Path(aliases['<VALIDATION_BUILD_ROOT>'])
    source = base / 'source_N09_RP_ONLY'
    build = base / 'build_N09_RP_ONLY'
    output = base / 'N09_RP_ONLY_fixture_v1'
    logs = output / 'command_logs'
    logs.mkdir(parents=True, exist_ok=True)
    ledger = HERE / 'COMMANDS.json'
    records = json.loads(ledger.read_text()) if ledger.exists() else []
    baseline = Path(aliases['<MECHANISM_BUILD_ROOT>']) / 'build_observed/liblegsa_v23_port_core.a'
    fixture = HERE / 'native_fixture.cpp'
    includes = 'cpp/legsa_v23_port_core/include'
    commands = [
        ('configure', ['cmake', '-S', str(source / 'cpp'), '-B', str(build),
                       '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
                       '-DCMAKE_CXX_FLAGS=', '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG'], False),
        ('build_candidate', ['cmake', '--build', str(build), '--target', 'legsa_v23_port_core_demo', '-j', '2'], False),
        ('compile_fixture_baseline', ['/usr/bin/g++', '-O3', '-DNDEBUG', '-std=c++17',
                                     '-I', str(Path(aliases['<OBSERVED_SOURCE>']) / includes),
                                     str(fixture), str(baseline), '-o', str(output / 'fixture_baseline')], False),
        ('compile_fixture_candidate', ['/usr/bin/g++', '-O3', '-DNDEBUG', '-std=c++17', '-DN09_CANDIDATE=1',
                                      '-I', str(source / includes), str(fixture), str(build / 'liblegsa_v23_port_core.a'),
                                      '-o', str(output / 'fixture_candidate')], False),
    ]
    if args.phase == 'fixtures':
        commands = [(name, [str(output / ('fixture_baseline' if name == 'baseline' else 'fixture_candidate')),
                            str(output / name), 'observer_on' if name == 'candidate_on' else 'observer_off'], True)
                    for name in ['baseline', 'candidate_off', 'candidate_on']]
    def portable(value):
        value = str(value)
        for alias, path in sorted(aliases.items(), key=lambda x: len(x[1]), reverse=True):
            if value == path or value.startswith(path + '/'):
                return alias + value[len(path):]
        return value
    existing = {r['label'] for r in records}
    if existing.intersection(name for name, _, _ in commands):
        raise SystemExit('Phase already attempted; no automatic retry or overwrite')
    env = os.environ.copy()
    for key in ('LEGSA_V3_OBSERVER_DIR', 'LEGSA_V3_OBSERVER_RUN_ID'):
        env.pop(key, None)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        env[key] = '1'
    for label, argv, synthetic in commands:
        log = logs / (label + '.log')
        record = dict(command_id=len(records)+1, label=label, argv=[portable(a) for a in argv],
                      started_unix=time.time(), status='STARTED', log=portable(log),
                      synthetic_native_process=synthetic, real_native_process=False,
                      evaluator_process=False, retry_of=None)
        if synthetic:
            record['binary_sha256'] = hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest()
        records.append(record)
        ledger.write_text(json.dumps(records, indent=2)+'\n')
        print('START', label, flush=True)
        with log.open('x') as stream:
            result = subprocess.run(argv, cwd=CODE, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record.update(exit_code=result.returncode, ended_unix=time.time(),
                      status='COMPLETED' if result.returncode == 0 else 'FAILED')
        ledger.write_text(json.dumps(records, indent=2)+'\n')
        print('END', label, result.returncode, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
