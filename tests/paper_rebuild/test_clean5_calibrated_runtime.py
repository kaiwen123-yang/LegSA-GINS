"""Runtime byte restoration and fail-closed serial-attempt fixtures."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_calibrated import runtime
from legsa_gins.paper_rebuild.clean5_sequence.runtime_config import METHODS

ORIGINAL = ('# keep every token\nimupath: old.imu\ngnsspath: old.gnss\nrun_id: original\n'
            'vrw: [0.077, 0.077, 0.077]  # original units\nabstd: [77.8, 77.8, 77.8]\n'
            'arw: [0.985, 0.985, 0.985]\ngbstd: [9.38, 9.38, 9.38]\n'
            'initbastd: [77.8, 77.8, 77.8]\ncorrtime: 1.0\nstarttime: 66.0\nendtime: 340.0\n')
MODEL = {'vrw': [1., 2., 3.], 'abstd': [11., 12., 13.], 's': 1.03}


def test_exact_two_noise_vectors_and_complete_reverse_byte_identity():
    text, audit = runtime.patch_calibrated_config(ORIGINAL, {'imupath': 'new.imu', 'run_id': 'calibrated'}, MODEL,
                                                 model_sha256='a'*64, model_commit='b'*40)
    actual = yaml.safe_load(text)
    assert actual['vrw'] == MODEL['vrw'] and actual['abstd'] == MODEL['abstd']
    assert actual['initbastd'] == [77.8]*3 and actual['arw'] == [.985]*3
    restored = text.splitlines(keepends=True)
    for row in audit['parameter_byte_diff']:
        restored[row['line_index']] = row['before']
    assert ''.join(restored) == ORIGINAL
    assert audit['scientific_parameter_changed_keys'] == ['abstd', 'vrw']
    assert audit['non_calibrated_parameter_hash'] == audit['reference_frozen_parameter_hash']
    assert audit['frozen_parameter_hash'] != audit['reference_frozen_parameter_hash']


def test_unauthorized_config_override_and_duplicate_noise_rejected():
    with pytest.raises(ValueError, match='parameter override'):
        runtime.patch_calibrated_config(ORIGINAL, {'arw': [1, 1, 1]}, MODEL, model_sha256='a'*64, model_commit='b'*40)
    with pytest.raises(ValueError, match='duplicate'):
        runtime.patch_calibrated_config(ORIGINAL+'vrw: [1, 1, 1]\n', {}, MODEL, model_sha256='a'*64, model_commit='b'*40)


def test_exact_fifteen_order():
    contract = {'dataset_order': ['BY2', 'BY2H', 'BY2O'], 'run_profiles': list(METHODS)}
    order = runtime.run_order(contract)
    assert len(order) == 15 and order[:5] == [('BY2', m) for m in METHODS]
    contract['run_profiles'] = ['A04']
    with pytest.raises(ValueError, match='fifteen'):
        runtime.run_order(contract)


def test_prepare_exception_records_attempt_and_seals_without_launch(tmp_path, monkeypatch):
    stage = tmp_path/'stage'
    stage.mkdir()
    executable = tmp_path/'binary'
    executable.write_text('not executable; must never run\n')
    real_hash = runtime.sha256_file
    monkeypatch.setattr(runtime, 'sha256_file', lambda p: runtime.EXE_SHA if Path(p) == executable else real_hash(p))
    monkeypatch.setattr(runtime, 'verify_bundle', lambda b: None)
    def fail_checked(*args):
        raise ValueError('prepared fixture input gate failure')
    monkeypatch.setattr(runtime, 'checked', fail_checked)
    def no_launch(*args, **kwargs):
        raise AssertionError('No solver execution authorized in this test')
    monkeypatch.setattr(runtime, 'run_process_group', no_launch)
    registry = SimpleNamespace(code_root=tmp_path, clean_root=tmp_path/'clean', raw_root=tmp_path/'raw',
                                sequences={d: SimpleNamespace(data_mode='synthetic_unit_test_only') for d in ('BY2', 'BY2H', 'BY2O')})
    contract = {'dataset_order': ['BY2', 'BY2H', 'BY2O'], 'run_profiles': list(METHODS),
                'model': {'sha256': 'a'*64}, 'model_freeze_commit': 'b'*40,
                'sequences': {d: {'window_seconds': [66., 340.], 'original_configs': {
                    m: {'runtime_config': 'not_read.yaml', 'runtime_config_sha256': '0'*64} for m in METHODS}}
                    for d in ('BY2', 'BY2H', 'BY2O')}}
    records = runtime.run_chain(registry=registry, contract=contract, stage_root=stage,
                               bundles={'BY2': {}}, model=MODEL, executable=executable, code_commit='c'*40)
    assert len(records) == 1 and not records[0]['launch_attempted']
    assert records[0]['terminal_status'] == 'FAILED_CONFIG_PREPARATION_EXCEPTION'
    path = stage/'03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2_F01/CALIBRATED_RUN_MANIFEST.json'
    assert json.loads(path.read_text()) == records[0]
    seal = json.loads((stage/'04_CALIBRATED_SEAL/CALIBRATED_OUTPUT_SEAL.json').read_text())
    assert seal['run_count'] == 1 and seal['completed_count'] == 0 and not seal['all_native_success']
    assert runtime.verify_seal(stage, records)['file_count'] == 1


def test_evaluation_seal_covers_all_versions_datasets_and_robustness(tmp_path):
    stage = tmp_path/'stage'
    roots = [stage/'07_OFFLINE_EVALUATION', stage/'08_AGGREGATE']
    roots += [stage/d/'08_AGGREGATE' for d in ('BY2', 'BY2H', 'BY2O')]
    for root in roots:
        (root/'v3').mkdir(parents=True)
        (root/'v2_fixture.csv').write_text('opaque fixed evaluation fixture\n')
        (root/'v3/v3_fixture.csv').write_text('opaque fixed v3 fixture\n')
    (stage/'08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.json').write_text('{}\n')
    (stage/'04_CALIBRATED_SEAL').mkdir()
    solver_seal = stage/'04_CALIBRATED_SEAL/CALIBRATED_OUTPUT_SEAL.json'
    solver_seal.write_text('original solver seal\n')
    result = runtime.seal_evaluation_artifacts(stage, 'c'*40)
    seal = json.loads(Path(result['path']).read_text())
    assert result['file_count'] == 11
    assert '08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.json' in seal['files_sha256']
    assert len([p for p in seal['files_sha256'] if '/v3/' in p]) == 5
    assert solver_seal.read_text() == 'original solver seal\n'
    with pytest.raises(FileExistsError):
        runtime.seal_evaluation_artifacts(stage, 'c'*40)
