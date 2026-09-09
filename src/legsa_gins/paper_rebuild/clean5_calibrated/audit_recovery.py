"""Audit-only classification correction for the single completed P06 calibration.

No calibration loader, mathematical module, provider, solver or evaluator is
imported or invoked here. Existing outputs are only hashed as opaque bytes.
The original failed audit remains immutable and explicitly referenced.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml

from ..evidence import STRACE_OPENAT_RE
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..manifest import sha256_file

SOURCE_COMMIT = '8ea4076bb3a6c259ceddc225533b0d522620da00'
METADATA_PID = 26265
METADATA_ARGV = ['git', 'status', '--porcelain=v1', '--untracked-files=all']
# Exact relative-path SHA -> exact frozen file/blob SHA. Full historical path
# names are recorded only in the external provenance audit, never as evidence.
METADATA_PINS = {
    '890860214b8c4f79b5614a80c952ce88de4203013a634c04a0bc392daebb2080':
        '2c4356af0e9948580c84fc3da7ce7353e1c3f6a838dc8ad72839625e721fb935',
    '4c50c3950bb8bcc7f862a183e39f8cdd582bb5c107e551eb077c73c83c1a0ae7':
        'b70c96b8e5acd3d467a1dd8c5fafc989b498a000f847891c10f7f58e2f0f8c4a',
    '83fcc36031674175545b46996990c1df7e43d686a0c6ebd0da64bef8e35596a6':
        '15a93bf51838ced75116ea99ba34cee959804f8776a94d140e3e6ad13341c4a0',
}
ORIGINAL_PINS = {
    'CALIBRATION_OPENAT.strace': '5d13faf56cf29dae95b2a66aff745b1411a9da64d378217f5eae843b6d3617f9',
    'CALIBRATION_CHILD_TERMINAL.json': '8ae01c3cebbf2d0154bf6338ba121268ce7ae4e12ee7438502cca34d7fe6676e',
    'CALIBRATION_EXECUTION_AUDIT.json': 'd1cf871d604605a48ae911550525d0924f4279cd39070bd5f9f53cc835a40529',
    'CALIBRATION_FAILURE.json': '0d7c80ec8f01345d32a084f338e94ea4e272c58fc5b7854fc3fb848548059d2c',
    'CALIBRATION_STARTED.json': '899a23b3303a51942ad7a1abbc5afdf212d1336f5f01a71e60c989c9a7905bfe',
}
CONTRACT = 'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL_CONTRACT.yaml'
WRITE_FLAGS = ('O_WRONLY', 'O_RDWR', 'O_CREAT', 'O_TRUNC', 'O_APPEND')
SUCCESSFUL_EXEC = re.compile(r'^\s*(\d+)\s+execve\(("(?:\\.|[^"\\])*"),\s*(\[.*?\]),.*\)\s*=\s*0\s*$')
PID = re.compile(r'^\s*(\d+)\s+')


def _read_json(path):
    return json.loads(Path(path).read_text())


def _write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _within(path, root):
    return path == root or root in path.parents


def _regular_no_symlinks(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Nonregular/symlink review source: '+str(path))
    return path


def _git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def verify_source_blobs(source_code_root, source_map):
    """Check exact tracked blobs at the already executed scientific code commit."""
    source_code_root = Path(source_code_root)
    if _git(source_code_root, 'rev-parse', 'HEAD').decode().strip() != SOURCE_COMMIT:
        raise ValueError('Original calibration snapshot HEAD changed')
    ledger = []
    for relative, expected in sorted(source_map.items()):
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unconfined source-map member')
        path = _regular_no_symlinks(source_code_root/rel)
        blob = _git(source_code_root, 'show', SOURCE_COMMIT+':'+relative)
        blob_sha = hashlib.sha256(blob).hexdigest()
        actual = sha256_file(path)
        if blob_sha != actual or (expected is not None and actual != expected):
            raise ValueError('Original source file/blob mismatch: '+relative)
        ledger.append({'relative_path': relative, 'sha256': actual, 'git_blob_sha256': blob_sha,
                       'git_blob_id': _git(source_code_root, 'rev-parse', SOURCE_COMMIT+':'+relative).decode().strip(),
                       'source_commit': SOURCE_COMMIT})
    return ledger


def attributed_open_records(log, cwd):
    """Attach the latest successful exec for each PID without trusting filenames."""
    records = audited_open_records(log, cwd)
    commands = {}
    index = 0
    for line_number, line in enumerate(Path(log).read_text().splitlines(), 1):
        match = SUCCESSFUL_EXEC.match(line)
        if match:
            commands[int(match[1])] = {'executable': ast.literal_eval(match[2]),
                                      'argv': ast.literal_eval(match[3]), 'exec_line': line_number}
        if STRACE_OPENAT_RE.search(line):
            pid_match = PID.match(line)
            if not pid_match:
                raise ValueError('Missing strace PID attribution')
            pid = int(pid_match[1])
            records[index].update(pid=pid, open_line=line_number,
                                  successful_exec=commands.get(pid))
            index += 1
    if index != len(records):
        raise ValueError('PID/open record association mismatch')
    return records


def _trace_name(path):
    name = path.name.lower()
    return name.startswith('trace_') or name == 'trace' or name.startswith('trace.')


def _archive_name(path):
    suffixes = [s.lower() for s in path.suffixes]
    return '.bag' in suffixes or '.fpl' in suffixes


def metadata_sources_from_records(records, source_code_root):
    sources = {}
    for record in records:
        path = Path(record['path'])
        if _within(path, source_code_root):
            relative = path.relative_to(source_code_root).as_posix()
            key = hashlib.sha256(relative.encode()).hexdigest()
            if key in METADATA_PINS:
                sources[relative] = METADATA_PINS[key]
    if len(sources) != len(METADATA_PINS):
        raise ValueError('Three exact pinned metadata paths not present in original log')
    return sources


def corrected_classification(records, *, source_code_root, raw_root, clean_root,
                             calibration_root, input_paths):
    source_code_root, raw_root, clean_root, calibration_root = map(Path, (
        source_code_root, raw_root, clean_root, calibration_root))
    allowed = {Path(p).resolve() for p in input_paths}
    metadata = {source_code_root/p for p in metadata_sources_from_records(records, source_code_root)}
    exceptions, denied, forbidden, git_metadata = [], [], [], []
    for record in records:
        path = Path(record['path'])
        lexical = Path(record.get('lexical_path', record['path']))
        command = record.get('successful_exec') or {}
        git_status = (record.get('pid') == METADATA_PID and command.get('executable') == '/usr/bin/git'
                      and command.get('argv') == METADATA_ARGV)
        read_only = not any(flag in record['flags'] for flag in WRITE_FLAGS)
        is_metadata = (path == lexical and path in metadata and git_status and read_only
                       and not _within(path, raw_root) and not _within(path, clean_root))
        if git_status and read_only and _within(path, source_code_root):
            git_metadata.append(record)
        if is_metadata:
            exceptions.append({**record, 'classification': 'CODE_FREEZE_METADATA_ONLY',
                               'legacy_markdown': path.suffix == '.md',
                               'content_used_as_calibration_or_performance_evidence': False})
        if any(_archive_name(p) or (_trace_name(p) and not is_metadata) for p in (path, lexical)):
            forbidden.append(record)
        for p in (path, lexical):
            if (_within(p, raw_root) or _within(p, clean_root)) and not _within(p, calibration_root) and p.resolve() not in allowed:
                denied.append(record)
                break
    if len(exceptions) != len(metadata) or {Path(r['path']) for r in exceptions} != metadata:
        raise ValueError('Expected exactly three pinned Git metadata open exceptions')
    writes = write_scope_audit(records, raw_root=raw_root, clean_root=clean_root,
                               allowed_write_roots=[calibration_root])
    counts = {'trace': 0, 'bag': 0, 'fpl': 0}
    for record in forbidden:
        suffixes = [s.lower() for s in Path(record['path']).suffixes]
        key = 'bag' if '.bag' in suffixes else 'fpl' if '.fpl' in suffixes else 'trace'
        counts[key] += 1
    return {'pass': not forbidden and not denied and writes['pass'],
            'forbidden_open_counts': counts, 'forbidden_open_records': forbidden,
            'undeclared_protected_open_records': denied, 'write_scope': writes,
            'metadata_exception_records': exceptions,
            'legacy_markdown_exception_records': [r for r in exceptions if r['legacy_markdown']],
            'git_status_code_tree_open_count': len(git_metadata),
            'git_status_code_tree_open_records': git_metadata,
            'failed_open_attempts_also_audited': True,
            'source_metadata_is_not_active_performance_evidence': True}


def verify_existing_artifacts(calibration_root):
    root = Path(calibration_root)
    for name, expected in ORIGINAL_PINS.items():
        if sha256_file(_regular_no_symlinks(root/name)) != expected:
            raise ValueError('Original calibration review pin changed: '+name)
    child = _read_json(root/'CALIBRATION_CHILD_TERMINAL.json')
    old_audit = _read_json(root/'CALIBRATION_EXECUTION_AUDIT.json')
    failure = _read_json(root/'CALIBRATION_FAILURE.json')
    if (child.get('status') != 'CALIBRATION_COMPLETE' or child.get('code_commit') != SOURCE_COMMIT
            or old_audit.get('exit_code') != 0 or old_audit.get('pass') is not False
            or failure.get('status') != 'FAILED'):
        raise ValueError('Original child/failure state differs from reviewed classification case')
    if old_audit.get('strace_sha256') != ORIGINAL_PINS['CALIBRATION_OPENAT.strace']:
        raise ValueError('Original audit/log binding mismatch')
    if (old_audit.get('undeclared_protected_open_records') or not old_audit['write_scope']['pass']
            or old_audit['forbidden_open_counts'] != {'trace': 3, 'bag': 0, 'fpl': 0}):
        raise ValueError('Original failure contains an unreviewed issue')
    output_pins = dict(child['tables'])
    output_pins['CLEAN5_CALIBRATED_SENSOR_MODEL.yaml'] = child['model_sha256']
    for name, expected in output_pins.items():
        if Path(name).name != name:
            raise ValueError('Unconfined output table member')
        if sha256_file(_regular_no_symlinks(root/name)) != expected:
            raise ValueError('Original completed output hash mismatch: '+name)
    return child, output_pins


def review_existing(*, calibration_root, source_code_root, review_code_root, raw_root, clean_root):
    root = Path(calibration_root)
    output = root/'AUDIT_CLASSIFICATION_REVIEW'
    if output.exists() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Review output exists or source root is a symlink')
    # Hash original top-level artifacts without interpreting any scientific table.
    original_hashes = {p.name: sha256_file(_regular_no_symlinks(p)) for p in sorted(root.iterdir()) if p.is_file()}
    child, output_pins = verify_existing_artifacts(root)
    source_code_root = Path(source_code_root)
    contract_path = _regular_no_symlinks(source_code_root/CONTRACT)
    if sha256_file(contract_path) != child['contract_sha256']:
        raise ValueError('Original contract binding changed')
    contract = yaml.safe_load(contract_path.read_text())
    records = attributed_open_records(root/'CALIBRATION_OPENAT.strace', source_code_root)
    source_map = dict(child['process_source_sha256'])
    source_map[CONTRACT] = child['contract_sha256']
    source_map.update(metadata_sources_from_records(records, source_code_root))
    source_ledger = verify_source_blobs(source_code_root, source_map)
    input_paths = []
    for role, pin in contract['calibration']['inputs'].items():
        if child['input_sha256'][role] != {'path': pin['path'], 'sha256': pin['sha256']}:
            raise ValueError('Frozen input declaration binding changed: '+role)
        path = Path(pin['path'].replace('<RAW_ROOT>', str(raw_root)).replace('<CLEAN_ROOT>', str(clean_root)))
        if '<' in str(path) or not path.is_absolute():
            raise ValueError('Unresolved original input alias')
        input_paths.append(path)  # No input/raw data file is opened or rehashed.
    audit = corrected_classification(records, source_code_root=source_code_root, raw_root=raw_root,
                                      clean_root=clean_root, calibration_root=root, input_paths=input_paths)
    if not audit['pass']:
        raise ValueError('Corrected audit still fails; original outputs remain unaccepted')
    after = {name: sha256_file(root/name) for name in original_hashes}
    if after != original_hashes:
        raise ValueError('Original calibration artifacts changed during review')
    review_code_root = Path(review_code_root)
    review_sources = {'src/legsa_gins/paper_rebuild/clean5_calibrated/audit_recovery.py': sha256_file(Path(__file__)),
                      'scripts/paper_rebuild/clean5_review_calibration_audit.py': sha256_file(review_code_root/'scripts/paper_rebuild/clean5_review_calibration_audit.py')}
    output.mkdir(exist_ok=False)
    review = {'status': 'PASS_CORRECTED_AUDIT_NO_RECOMPUTATION', 'classification_audit': audit,
              'original_source_commit': SOURCE_COMMIT, 'original_artifact_sha256': original_hashes,
              'source_blob_ledger': source_ledger, 'review_source_sha256': review_sources,
              'review_repository_head': _git(review_code_root, 'rev-parse', 'HEAD').decode().strip(),
              'review_source_identity': 'explicit source SHA256; repository HEAD is context only',
              'original_failure_preserved': True, 'original_failed_audit_preserved': True,
              'calibration_computation_count_this_review': 0, 'raw_file_open_count_this_review': 0,
              'solver_invocation_count': 0, 'evaluator_invocation_count': 0,
              'scientific_tables_read_only_as_opaque_hash_bytes': True,
              'data_mode': 'real_by2_raw_trace_free_calibration_audit_review',
              'synthetic_data_used': False, 'semisynthetic_data_used': False, 'trace_used_online': False}
    review_path = output/'CALIBRATION_AUDIT_CLASSIFICATION_REVIEW.json'
    _write_json(review_path, review)
    acceptance = {'status': 'PASS_CORRECTED_AUDIT_NO_RECOMPUTATION', 'ready_for_model_freeze': True,
                  'calibration_status': child['status'], 'calibration_code_commit': SOURCE_COMMIT,
                  'model_sha256': child['model_sha256'], 'completed_output_sha256': output_pins,
                  'original_child_terminal_sha256': ORIGINAL_PINS['CALIBRATION_CHILD_TERMINAL.json'],
                  'original_failed_audit_sha256': ORIGINAL_PINS['CALIBRATION_EXECUTION_AUDIT.json'],
                  'original_failure_sha256': ORIGINAL_PINS['CALIBRATION_FAILURE.json'],
                  'original_strace_sha256': ORIGINAL_PINS['CALIBRATION_OPENAT.strace'],
                  'classification_review_sha256': sha256_file(review_path),
                  'calibration_count': 1, 'calibration_computation_count_this_review': 0,
                  'forbidden_open_counts': audit['forbidden_open_counts'],
                  'metadata_exception_count': len(audit['metadata_exception_records']),
                  'original_failure_preserved': True, 'original_artifacts_unchanged': True,
                  'synthetic_data_used': False, 'semisynthetic_data_used': False, 'trace_used_online': False}
    _write_json(output/'CALIBRATION_ACCEPTANCE.json', acceptance)
    return acceptance


def main(argv=None):
    parser = argparse.ArgumentParser(description='Review existing P06 audit only; never recompute calibration')
    for name in ('code-root', 'source-code-root', 'paths-config'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(argv)
    local = yaml.safe_load(args.paths_config.read_text())['paths']
    clean_root, raw_root = Path(local['clean_root']).resolve(), Path(local['raw_root']).resolve()
    root = clean_root/'stages/CLEAN5_CALIBRATED_SENSOR_MODEL/00_CALIBRATION'
    result = review_existing(calibration_root=root, source_code_root=args.source_code_root.resolve(),
                              review_code_root=args.code_root.resolve(), raw_root=raw_root, clean_root=clean_root)
    print(result['status']+'; calibration recomputations=0; original failure preserved', flush=True)
    return 0
