#!/usr/bin/env python3
"""HX-02 identity gate (read-only): frozen v3 table values and the 65-item table seal.

Reads MAIN_TABLE_V3.csv / FULL_ABLATION_TABLE_V3.csv rows and compares the SHA-256 of
every file under 07_AGGREGATE/, 07C_FAILURE_FAMILY_CONFIG/ and 07D_CLASSIFICATION_PROVENANCE/
with BASELINE.json. Never runs a solver or evaluator and never opens a reference trajectory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

V3_REL = 'stages/CLEAN8_PROTOCOL_V3'
BASELINE_REL = '00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BASELINE.json'
BASELINE_SHA256_PREFIX = '7830a1a5'
SEALED_DIRS = ('07_AGGREGATE', '07C_FAILURE_FAMILY_CONFIG', '07D_CLASSIFICATION_PROVENANCE')
# (table, 1-based line incl. header, expected identity columns, expected yaw token as registered)
VALUE_CHECKS = (
    ('07_AGGREGATE/MAIN_TABLE_V3.csv', 17, {'sequence_id': 'BY2', 'method_id': 'LC01', 'config': 'LIT', 'start_convention': 'FILE_START'}, '2.994827460'),
    ('07_AGGREGATE/MAIN_TABLE_V3.csv', 18, {'sequence_id': 'BY2', 'method_id': 'EXT05C', 'config': 'LIT', 'start_convention': 'FILE_START'}, '12.048642'),
    ('07_AGGREGATE/MAIN_TABLE_V3.csv', 4, {'sequence_id': 'BY2', 'method_id': 'F04'}, '1.886272'),
    ('07_AGGREGATE/MAIN_TABLE_V3.csv', 9, {'sequence_id': 'BY2H', 'method_id': 'F04'}, '1.933770'),
    ('07_AGGREGATE/MAIN_TABLE_V3.csv', 13, {'sequence_id': 'BY2O', 'method_id': 'F04'}, '2.433815'),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def clean_root(paths_config: Path) -> Path:
    for line in paths_config.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith('clean_root:'):
            return Path(stripped.split(':', 1)[1].strip())
    raise KeyError('clean_root missing from local paths config')


def csv_line(path: Path, line_number: int) -> dict:
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.reader(handle))
    header = rows[0]
    return dict(zip(header, rows[line_number - 1]))


def rounded(token: str, expected: str) -> str:
    places = len(expected.split('.', 1)[1]) if '.' in expected else 0
    return str(Decimal(token).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN))


def run(paths_config: Path) -> dict:
    v3 = clean_root(paths_config) / V3_REL
    baseline_path = v3 / BASELINE_REL
    baseline_sha = sha256_file(baseline_path)
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    registered = baseline['files_sha256']
    values = []
    for table, line, identity, expected in VALUE_CHECKS:
        row = csv_line(v3 / table, line)
        identity_ok = all(row.get(k) == v for k, v in identity.items())
        token = row.get('yaw_rmse_deg', '')
        value_ok = identity_ok and rounded(token, expected) == expected
        values.append({'table': table, 'line': line, 'identity': identity, 'identity_ok': identity_ok,
                       'yaw_rmse_deg_token': token, 'rounded': rounded(token, expected) if token else None,
                       'expected': expected, 'pass': value_ok})
    on_disk = {}
    for directory in SEALED_DIRS:
        for item in sorted((v3 / directory).rglob('*')):
            if item.is_file():
                on_disk[item.relative_to(v3).as_posix()] = sha256_file(item)
    files = []
    for rel in sorted(set(registered) | set(on_disk)):
        state = ('MATCH' if registered.get(rel) == on_disk.get(rel) else
                 'MISSING' if rel not in on_disk else
                 'UNREGISTERED' if rel not in registered else 'MISMATCH')
        files.append({'path': rel, 'registered_sha256': registered.get(rel), 'current_sha256': on_disk.get(rel), 'state': state})
    csv_files = [f for f in files if f['path'].endswith('.csv')]
    counts = {s: sum(1 for f in files if f['state'] == s) for s in ('MATCH', 'MISMATCH', 'MISSING', 'UNREGISTERED')}
    seal_ok = (baseline_sha.startswith(BASELINE_SHA256_PREFIX) and len(registered) == 65 and counts['MATCH'] == 65
               and counts['MISMATCH'] == counts['MISSING'] == counts['UNREGISTERED'] == 0)
    return {'utc': datetime.now(timezone.utc).isoformat(), 'baseline_json': baseline_path.as_posix(),
            'baseline_json_sha256': baseline_sha, 'registered_count': len(registered), 'counts': counts,
            'csv_count': len(csv_files), 'csv_match': sum(1 for f in csv_files if f['state'] == 'MATCH'),
            'value_checks': values, 'values_pass': all(v['pass'] for v in values), 'seal_pass': seal_ok,
            'status': 'PASS' if seal_ok and all(v['pass'] for v in values) else 'HARD_STOP', 'files': files,
            'solver_calls': 0, 'evaluator_calls': 0, 'reference_trajectory_opens': 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths-config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='new JSON record (never overwritten)')
    args = parser.parse_args()
    result = run(args.paths_config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    summary = {k: result[k] for k in ('utc', 'status', 'baseline_json_sha256', 'counts', 'csv_count', 'csv_match', 'values_pass', 'seal_pass')}
    print(json.dumps(summary, indent=2))
    for v in result['value_checks']:
        print(v['table'], v['line'], v['yaw_rmse_deg_token'], '->', v['rounded'], 'expected', v['expected'], 'PASS' if v['pass'] else 'FAIL')
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
