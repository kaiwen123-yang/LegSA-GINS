"""Metadata-only repair tests; real manifests are read-only provenance fixtures."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_degradation.common import registry
from legsa_gins.paper_rebuild.clean5_degradation.runtime import validate_identity
from legsa_gins.paper_rebuild.clean6_canonical_v2.runtime import append_sequence_runtime_role, seal_run
from legsa_gins.paper_rebuild.clean6_canonical_v2 import revalidation as repair

ROLE = 'clean2r2a_formal_clean_ablation_solver'


def test_missing_runtime_role_reports_fail_without_keyerror():
    with pytest.raises(ValueError, match='FAIL_NATIVE_IDENTITY_MISSING_CONFIG_KEYS: .*runtime_role'):
        validate_identity({}, {}, {}, {})


@pytest.mark.parametrize('ending', ['\n', ''])
def test_role_append_preserves_exact_original_prefix(ending):
    original = '# untouched transport/science formatting\nvrw: [1, 2, 3]'+ending
    derived, audit = append_sequence_runtime_role(original, ROLE)
    assert derived.startswith(original)
    assert yaml.safe_load(derived) == {'vrw': [1, 2, 3], 'runtime_role': ROLE}
    assert audit['original_bytes_preserved_as_prefix']
    assert audit['scientific_parameter_changed_keys'] == []
    assert append_sequence_runtime_role(derived, ROLE)[0] == derived
    with pytest.raises(ValueError, match='differs from preregistration'):
        append_sequence_runtime_role(derived, 'wrong')


def sealed_scene(tmp_path):
    root = tmp_path/'run'
    root.mkdir()
    record = {'output_root': str(root), 'terminal_status': 'COMPLETED', 'synthetic_data_used': True}
    (root/'P09C_RUN_TERMINAL.json').write_text(json.dumps(record))
    (root/'native.nav').write_bytes(b'preserved original bytes')
    record['output_seal'] = seal_run(root)
    record['solver_output_bytes'] = sum(x['size_bytes'] for x in record['output_seal'].values())
    return record


def test_original_seal_rechecks_all_files_and_membership(tmp_path):
    record = sealed_scene(tmp_path)
    assert repair.verify_original_seal(record)['file_count'] == 2
    root = Path(record['output_root'])
    (root/'unsealed').write_bytes(b'new')
    with pytest.raises(ValueError, match='membership changed'):
        repair.verify_original_seal(record)
    (root/'unsealed').unlink()
    (root/'native.nav').write_bytes(b'changed')
    with pytest.raises(ValueError, match='sealed file changed'):
        repair.verify_original_seal(record)


def test_original_seal_rejects_changed_terminal_record(tmp_path):
    record = sealed_scene(tmp_path)
    record['terminal_status'] = 'FAILED_TECHNICAL'
    with pytest.raises(ValueError, match='differs from sealed original terminal'):
        repair.verify_original_seal(record)


def test_revalidation_rejects_incomplete_group_before_output_creation(tmp_path):
    contract = {'restart_authorization': {'original_execution_code_commit': 'old'},
                'runtime': {'profiles': [f'M{i}' for i in range(11)]}}
    output = tmp_path/'new'
    with pytest.raises(ValueError, match='exactly the original 33'):
        repair.revalidate_existing([], contract, None, output, 'new')
    assert not output.exists()


def test_revalidation_preserves_native_provenance_and_writes_only_new_scope(tmp_path, monkeypatch):
    stage = tmp_path/'stage'; stage.mkdir()
    scratch = tmp_path/'scratch'; scratch.mkdir()
    output = stage/'restart'
    profiles = [f'M{i}' for i in range(11)]
    contract = {'stage_root': str(stage), 'restart_authorization': {
        'original_execution_code_commit': 'original_native_commit', 'sequence_runtime_role': ROLE},
        'runtime': {'profiles': profiles}}
    records = []
    originals = {}
    for dataset in ('BY2', 'BY2H', 'BY2O'):
        for method in profiles:
            root = scratch/(dataset+'_'+method); root.mkdir()
            text = 'starttime: 1\nendtime: 2\nrun_id: run\ncase_id: case\nimupath: imu\ngnsspath: gnss\n'
            (root/'PROTOCOL_V2_RUNTIME_CONFIG.yaml').write_text(text)
            (root/'RUN_MANIFEST.json').write_text('{}')
            originals[str(root)] = text
            records.append({'dataset_id': dataset, 'method_id': method, 'run_id': dataset+'_'+method,
                'code_commit': 'original_native_commit', 'config_hash': repair.sha256_file(root/'PROTOCOL_V2_RUNTIME_CONFIG.yaml'),
                'output_root': str(root), 'source_registry_row': {}, 'provider_hashes': {},
                'terminal_status': 'COMPLETED' if dataset == 'BY2' else 'FAILED_TECHNICAL',
                'failure_type': 'KeyError', 'failure': "'runtime_role'", 'expected_counters': {'test': 1},
                'exit_code': 0, 'retry_count': 0, 'output_seal': {'original': {'sha256': 'original'}}})
    before = copy.deepcopy(records)
    monkeypatch.setattr(repair, 'verify_original_seal', lambda _: {'passed': True})
    monkeypatch.setattr(repair, 'validate_identity', lambda *a: {'passed': True})
    monkeypatch.setattr(repair.np, 'loadtxt', lambda *a, **kw: [])
    monkeypatch.setattr(repair, 'expected_counts', lambda *a: {'test': 1})
    monkeypatch.setattr(repair, 'check_counters', lambda *a: {'pass': True, 'actual': {'test': 1}})
    monkeypatch.setattr(repair, 'check_auxiliary', lambda *a: {'pass': True})
    monkeypatch.setattr(repair, 'audit_solver_openat', lambda *a, **kw: {'pass': True})
    monkeypatch.setattr(repair, '_enabled_paths', lambda _: {})
    opened_config_paths = []
    monkeypatch.setattr(repair, 'validate_input_opens', lambda log, paths, reg, root, cfg: opened_config_paths.append(cfg) or {'passed': True})
    monkeypatch.setattr(repair, 'validate_run_outputs', lambda *a: {'finite': True})
    reg = SimpleNamespace(code_root=tmp_path, clean_root=stage, raw_root=tmp_path/'raw')
    results = repair.revalidate_existing(records, contract, reg, output, 'validation_commit')
    assert records == before
    assert len(results) == 33 and all(r['terminal_status'] == 'COMPLETED' for r in results)
    assert {r['code_commit'] for r in results} == {'original_native_commit'}
    assert {r['validation_code_commit'] for r in results} == {'validation_commit'}
    assert all(r['output_seal'] == o['output_seal'] and r['config_hash'] == o['config_hash'] for r, o in zip(results, records))
    assert len(list(output.glob('REVALIDATION_RUNS/*/VALIDATION_RUNTIME_CONFIG.yaml'))) == 22
    assert len(opened_config_paths) == 22 and all(scratch in p.parents for p in opened_config_paths)
    for directory, text in originals.items():
        assert (Path(directory)/'PROTOCOL_V2_RUNTIME_CONFIG.yaml').read_text() == text
        assert {p.name for p in Path(directory).iterdir()} == {'PROTOCOL_V2_RUNTIME_CONFIG.yaml', 'RUN_MANIFEST.json'}
    with pytest.raises(FileExistsError):
        repair.revalidate_existing(records, contract, reg, output, 'validation_commit')


def test_p06_15_and_retained_22_real_manifest_regression():
    local = os.environ.get('P09C_REVALIDATION_LOCAL_CONFIG')
    if not local:
        pytest.skip('Set P09C_REVALIDATION_LOCAL_CONFIG to execute the required read-only 37-real-manifest gate')
    reg = registry(local)
    path = reg.code_root/'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml'
    contract = yaml.safe_load(path.read_text())
    pin = contract['restart_authorization']['retained_evidence_pins']['BATCHES/BATCH_001/SOLVER_GROUP_0.json']
    records = json.loads(repair.pinned(pin, reg).read_text())
    report = repair.real_manifest_regression(contract, reg, records)
    assert report['status'] == 'PASS'
    assert (report['P06_count'], report['P09c_count'], report['passed_count']) == (15, 22, 37)
    assert report['read_only'] is True
    print('P09C_REAL_MANIFEST_REGRESSION: P06 15/15, retained sequence 22/22, total 37/37 PASS; read_only=true')
