#!/usr/bin/env python3
"""Read-only P4 verification against the preregistered V3-R protection index."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.clean6_canonical_v2.io_recovery import _metadata_bytes


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(8 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def check(pin, code):
    row = dict(pin)
    try:
        path = Path(pin['path'])
        for parent in (path, *path.parents):
            if parent.is_symlink():
                raise ValueError('SYMLINK_DENIED')
        if pin.get('kind') == 'historical_git_source':
            payload = subprocess.check_output(['git', 'show', pin['commit'] + ':' + pin['relative_path']], cwd=code)
            actual = hashlib.sha256(payload).hexdigest()
            size = len(payload)
            current = subprocess.check_output(['git', 'show', pin['current_science_freeze'] + ':' + pin['relative_path']], cwd=code)
            if path.read_bytes() != current:
                raise ValueError('CURRENT_SCIENCE_SOURCE_DIFFERS')
            row['current_science_sha256'] = hashlib.sha256(current).hexdigest()
        else:
            actual = digest(path)
            size = path.stat().st_size
        row.update(actual_sha256=actual, actual_size_bytes=size)
        if actual != pin['sha256'] or ('size_bytes' in pin and size != pin['size_bytes']):
            raise ValueError('HASH_OR_SIZE_MISMATCH')
        row['status'] = 'PASS'
    except Exception as exc:
        row.update(status='FAIL', error=str(exc))
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text())
    if not index.get('verification_pins'):
        raise ValueError('EMPTY_VERIFICATION_INDEX_DENIED')
    start = time.time()
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(check, pin, index['code_root']) for pin in index['verification_pins']]
        for future in as_completed(jobs):
            row = future.result()
            rows.append(row)
            if row['status'] != 'PASS' or len(rows) % 100 == 0:
                print('P4_VERIFY', len(rows), len(jobs), row['status'], row['path'], flush=True)
    bad = sum(row['status'] != 'PASS' for row in rows)
    result = dict(status='PASS' if not bad else 'FAIL', verification_complete=True,
                  failed=bad, verified=len(rows)-bad, total=len(rows),
                  index_sha256=digest(args.index), elapsed_seconds=time.time()-start,
                  ledger_sha256=os.environ.get('V3R_PURGE_LEDGER_SHA256'),
                  data_mode='storage_provenance_only', synthetic_data_used=False,
                  semisynthetic_data_used=False, native_invocations=0, evaluator_invocations=0,
                  checks=sorted(rows, key=lambda row: (row['path'], row.get('kind', ''))))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    _metadata_bytes(args.receipt, (json.dumps(result, indent=2)+'\n').encode(), append=False)
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}), flush=True)
    raise SystemExit(0 if not bad else 1)


if __name__ == '__main__':
    main()
