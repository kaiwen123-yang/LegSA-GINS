"""One bounded continuation of the sealed two-run P02 attempt; no old writes."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import yaml
from ..manifest import sha256_file
from ..clean5_sequence.solver_validation import validate_run_outputs
from .runtime import RUN_ORDER, expected_counts, check_counters, write_json

ORIGINAL_COMMIT = 'd6581ae44e41d7e0640a39381ed76fbe66dea92f'
ORIGINAL_CONTRACT_SHA = '33d3f3b0fc48bf50b5cc42c5fdf014737085bdc125d10ad3dbf7231b25fa3540'
ORIGINAL_SEAL_SHA = '94f90e213378665fbff9ef32e02fb20302ccd004ed1be5b327f7a4e9fff644fb'
ORIGINAL_BUNDLE_SHA = '85b3ed069c30df31a78b2d64a1946721eb845c06dc840d51867ef92462f70e5c'


def _read(path):
    return json.loads(Path(path).read_text())


def confined_file(root, value):
    root = Path(root).resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    if '..' in path.parts or path.is_symlink() or not path.is_file():
        raise RuntimeError('Recovery file missing, symlink or traversal')
    path.resolve().relative_to(root)
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise RuntimeError('Recovery symlink parent')
    return path


def verify_previous(stage):
    """Verify pinned metadata, every sealed byte and all provider hashes."""
    stage = Path(stage)
    started = _read(stage/'P02_EXECUTION_STARTED.json')
    terminal = _read(stage/'P02_TERMINAL.json')
    seal_path = confined_file(stage, '04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json')
    bundle_path = confined_file(stage, '02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json')
    original_contract = confined_file(stage, '01_PARITY_EXECUTION_AUDIT/code_validation/PRE_EXECUTION_CONTRACT.yaml')
    if (started.get('code_commit') != ORIGINAL_COMMIT or terminal.get('code_commit') != ORIGINAL_COMMIT
            or started.get('contract_sha256') != ORIGINAL_CONTRACT_SHA
            or sha256_file(original_contract) != ORIGINAL_CONTRACT_SHA
            or sha256_file(seal_path) != ORIGINAL_SEAL_SHA or sha256_file(bundle_path) != ORIGINAL_BUNDLE_SHA):
        raise RuntimeError('Original P02 identity mismatch')
    seal, bundle = _read(seal_path), _read(bundle_path)
    records = terminal.get('runs', [])
    if (terminal.get('status') != 'PARTIAL' or terminal.get('run_count') != 2
            or len(records) != 2 or seal.get('run_count') != 2
            or seal.get('code_commit') != ORIGINAL_COMMIT or bundle.get('code_commit') != ORIGINAL_COMMIT
            or seal.get('records') != records):
        raise RuntimeError('Continuation requires exact sealed PARTIAL two-run attempt')
    for index, (variant, method) in enumerate(RUN_ORDER[:2]):
        row = records[index]
        expected_status = 'COMPLETED' if index == 0 else 'FAILED_COUNTER_AUDIT'
        if (row.get('run_id') != f'CLEAN5_PARITY_{variant}_{method}' or row.get('terminal_status') != expected_status
                or row.get('exit_code') != 0 or row.get('code_commit') != ORIGINAL_COMMIT
                or not row.get('strace_audit', {}).get('pass')):
            raise RuntimeError('Prior run status/identity is not the authorized continuation case')
    files = seal.get('files_sha256', {})
    if not files:
        raise RuntimeError('Empty original seal')
    for relative, digest in files.items():
        path = confined_file(stage/'03_PARITY_RUNS', stage/relative)
        if sha256_file(path) != digest:
            raise RuntimeError(f'Original sealed file changed: {relative}')
    actual = {p.relative_to(stage).as_posix() for p in (stage/'03_PARITY_RUNS').rglob('*') if p.is_file()}
    if actual != set(files):
        raise RuntimeError('Unsealed prior run files or prior continuation')
    for variant, method in RUN_ORDER[2:]:
        if (stage/'03_PARITY_RUNS'/f'CLEAN5_PARITY_{variant}_{method}').exists():
            raise RuntimeError('Previously unexecuted run already exists')
    for value in bundle['variants'].values():
        for entry in value['providers'].values():
            if sha256_file(confined_file(stage/'02_PARITY_PROVIDERS', entry['path'])) != entry['sha256']:
                raise RuntimeError('Original provider changed')
    return bundle, records


def prepare_continuation(*, stage, contract_sha256, code_commit, state):
    stage = Path(stage)
    bundle, originals = verify_previous(stage)
    directory = stage/'01_PARITY_EXECUTION_AUDIT'/'continuation'
    directory.mkdir(exist_ok=False)
    write_json(stage/'P02_CONTINUATION_STARTED.json', {
        'code_commit': code_commit, 'state': state, 'contract_sha256': contract_sha256,
        'original_code_commit': ORIGINAL_COMMIT, 'original_contract_sha256': ORIGINAL_CONTRACT_SHA,
        'original_seal_sha256': ORIGINAL_SEAL_SHA, 'original_bundle_sha256': ORIGINAL_BUNDLE_SHA,
        'prior_native_invocations': 2, 'remaining_native_invocations': 6, 'prior_reruns': 0,
        'data_mode': 'real_by2_raw', 'synthetic_data_used': False, 'semisynthetic_data_used': False})
    records = copy.deepcopy(originals)
    audits = []
    for row in records:
        root = confined_file(stage/'03_PARITY_RUNS', Path(row['output_root'])/'PARITY_RUNTIME_CONFIG.yaml').parent
        cfg = yaml.safe_load((root/'PARITY_RUNTIME_CONFIG.yaml').read_text())
        native = _read(root/'RUN_MANIFEST.json')
        expected = expected_counts(cfg)
        counter = check_counters(native, cfg, expected)
        if not counter['pass']:
            raise RuntimeError(f'Revalidation counter mismatch: {row["run_id"]}')
        validation = validate_run_outputs(root, {'window_contract': {'t_start': 66, 't_end': 340}})
        original_status = row['terminal_status']
        row.update(validation)
        row.update(terminal_status='COMPLETED', expected_counters=expected, counter_audit=counter,
                   counters=counter['actual'], revalidation_code_commit=code_commit,
                   original_terminal_status=original_status, native_rerun=False,
                   revalidation_path=str(directory/'REVALIDATION.json'))
        for role, name in [('nav','KF_GINS_Navresult.nav'), ('std','KF_GINS_STD.txt')]:
            row[role+'_path'] = str(root/name)
            row[role+'_sha256'] = sha256_file(root/name)
        audits.append({'run_id': row['run_id'], 'original_terminal_status': original_status,
                       'counter_audit': counter, 'outputs': validation,
                       'original_manifest_sha256': sha256_file(root/'PARITY_RUN_MANIFEST.json')})
    write_json(directory/'REVALIDATION.json', {'status': 'PASS', 'code_commit': code_commit,
        'original_code_commit': ORIGINAL_COMMIT, 'native_invocations': 0, 'original_files_unchanged': True,
        'audits': audits, 'records': records, 'data_mode':'real_by2_raw',
        'synthetic_data_used':False, 'semisynthetic_data_used':False})
    return bundle, records
