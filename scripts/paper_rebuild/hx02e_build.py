#!/usr/bin/env python3
"""Build an unchanged official checkout copy and the HX-02E API-only driver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--official', type=Path, required=True)
    p.add_argument('--scratch', type=Path, required=True)
    p.add_argument('--driver', type=Path, required=True)
    a = p.parse_args()
    assert subprocess.check_output(['git', '-C', str(a.official), 'status', '--porcelain']) == b''
    assert subprocess.check_output(['git', '-C', str(a.official), 'rev-parse', 'HEAD']).decode().strip() == 'ef16e8a1df72f9272111a488880e3fe9d161f59f'
    base = a.scratch / 'BUILD'
    base.mkdir(exist_ok=False)
    source = base / 'official'
    source.mkdir()
    files = subprocess.check_output(['git', '-C', str(a.official), 'ls-files', '-z']).decode().split('\0')[:-1]
    pins = {}
    for rel in files:
        dst = source / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.official / rel, dst)
        pins[rel] = sha(a.official / rel)
        assert sha(dst) == pins[rel]
    tmp = base / 'tmp'
    tmp.mkdir()
    environment = {**os.environ, 'TMPDIR': str(tmp), 'OMP_NUM_THREADS': '1'}
    commands = [
        ['cmake', '-S', str(source), '-B', str(base / 'cmake'), '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON'],
        ['cmake', '--build', str(base / 'cmake'), '--target', 'inekf', 'kinematics', 'landmarks', '-j', '2'],
        ['g++', '-std=c++17', '-O3', '-DEIGEN_NO_DEBUG', '-DINEKF_USE_MUTEX=false', '-march=native',
         '-I' + str(source / 'include'), '-I/usr/include/eigen3', str(a.driver), '-L' + str(source / 'lib'),
         '-Wl,-rpath,' + str(source / 'lib'), '-linekf', '-o', str(base / 'hx02e_official_driver')],
    ]
    records = []
    for i, argv in enumerate(commands):
        with (base / f'command_{i}.stdout.log').open('x') as out, (base / f'command_{i}.stderr.log').open('x') as err:
            done = subprocess.run(argv, env=environment, stdout=out, stderr=err)
        records.append({'argv': argv, 'returncode': done.returncode})
        (base / 'BUILD_COMMANDS.json').write_text(json.dumps(records, indent=2) + '\n')
        if done.returncode:
            raise RuntimeError(f'Build command {i} failed; see retained logs')
    assert all(sha(source / p) == h == sha(a.official / p) for p, h in pins.items())
    assert subprocess.check_output(['git', '-C', str(a.official), 'status', '--porcelain']) == b''
    result = {'official_files': pins, 'source_copy_identical': True, 'commands': records,
              'driver_sha256': sha(a.driver), 'executables': {
                  str(p.relative_to(base)): sha(p) for p in [base / 'hx02e_official_driver', source / 'bin/kinematics', source / 'bin/landmarks', source / 'lib/libinekf.so']}}
    (base / 'BUILD_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: unchanged official library and driver built', flush=True)


if __name__ == '__main__':
    main()
