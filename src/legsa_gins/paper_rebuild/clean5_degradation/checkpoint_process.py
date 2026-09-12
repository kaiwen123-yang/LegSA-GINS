"""Explicitly authorized hash-only checkpoint; never imported by the solver."""
from __future__ import annotations

from pathlib import Path
from collections import Counter

from ..manifest import sha256_file
from .common import read_csv, write_json


def audit_locked_opens(records, expected_paths):
    """Audit only raw-root open records from one independent hash session."""
    expected = set(map(str, expected_paths))
    observed = Counter(r['path'] for r in records)
    writes = [r for r in records if any(flag in r['flags'] for flag in
              ('O_WRONLY', 'O_RDWR', 'O_CREAT', 'O_TRUNC', 'O_APPEND'))]
    readonly = all(r['return_code'] >= 0 and 'O_RDONLY' in r['flags'] for r in records)
    once = all(observed[p] == 1 for p in expected)
    return {'passed': len(expected) == 22 and set(observed) == expected and once and readonly and not writes,
            'expected_raw_paths': sorted(expected), 'observed_raw_paths': sorted(observed),
            'per_member_open_counts': {p: observed[p] for p in sorted(expected | set(observed))},
            'all_member_open_counts_equal_one': once, 'raw_open_count': len(records),
            'raw_write_open_count': len(writes), 'all_raw_opens_successful_readonly': readonly,
            'hash_only': True, 'scientific_values_parsed': False}


def hash_members(raw_lock, raw_root, output, resolution):
    if resolution.get('mode') != 'independent_hash_all' or not resolution.get('human_instruction'):
        raise ValueError('Independent raw hashing requires the explicit human checkpoint instruction')
    entries = [r for r in read_csv(raw_lock) if r['dataset'] == 'BY2']
    if len(entries) != 22 or len({r['relative_path'] for r in entries}) != 22:
        raise ValueError('Expected exactly22 unique frozen BY2 members')
    rows = []
    raw_root = Path(raw_root)
    for entry in entries:
        relative = Path(entry['relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid raw-lock relative member')
        source = raw_root / relative
        if any(p.is_symlink() for p in (source, *source.parents)) or not source.is_file():
            raise ValueError('Missing/symlink raw checkpoint member')
        digest = sha256_file(source)
        rows.append({'relative_path': entry['relative_path'], 'expected_sha256': entry['sha256'],
                     'actual_sha256': digest, 'verification': 'LIVE_SHA256_IN_AUTHORIZED_CHECKPOINT_CHILD',
                     'passed': digest == entry['sha256'] and source.stat().st_size == int(entry['size_bytes'])})
    write_json(output, {'members': rows, 'member_count': 22, 'passed_count': sum(r['passed'] for r in rows),
                       'live_hash_count': 22, 'resolution': resolution, 'hash_only': True,
                       'scientific_values_parsed': False, 'solver_or_provider_input': False})
