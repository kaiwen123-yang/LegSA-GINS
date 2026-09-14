"""Synthetic-only finalization joins, source gates, and display schema tests."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import finalize as f
from legsa_gins.paper_rebuild.clean6_sensor_v21 import pack


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def test_final_closures_require_every_native_and_evaluator_slot_and_no_pending():
    def fixture(n, prefix):
        records = [{'run_id': prefix+str(i), 'case_id': 'c'+str(i), 'method_id': 'A04',
                    'dataset_id': 'BY2', 'terminal_status': 'COMPLETED'} for i in range(n)]
        rows = [dict(r, evaluator_version=v, evaluation_status='COMPLETED', finite_output=True)
                for r in records for v in pack.VERSIONS]
        return records, rows
    records, evaluations = fixture(5880, 'main')
    down_records, down_evaluations = fixture(21, 'down')
    main = {'status': 'PASS', 'native_terminals': 5880, 'evaluator_terminals': 11760,
            'verified_receipts': 5880, 'pending': 0}
    down = {'status': 'PASS', 'native_calls': 21, 'evaluator_terminals': 42,
            'verified_archives': 21, 'archive': {'pending_run_ids': []}, 'grid_origin_gate_status': 'PASS'}
    assert f.closure_gate(main, down, records, evaluations, down_records, down_evaluations)['status'] == 'PASS'
    with pytest.raises(ValueError, match='zero pending'):
        f.closure_gate(dict(main, pending=1), down, records, evaluations, down_records, down_evaluations)
    with pytest.raises(ValueError, match='bijectively'):
        f.closure_gate(main, down, records, evaluations[:-1]+[evaluations[0]], down_records, down_evaluations)
    bad = [dict(r, finite_output=False) if i == 0 else r for i, r in enumerate(down_evaluations)]
    with pytest.raises(ValueError, match='nonfinite'):
        f.closure_gate(main, down, records, evaluations, down_records, bad)


def test_receipt_pins_are_independent_and_consumed_file_mutation_is_detected(tmp_path):
    root = tmp_path/'archive/run'
    source = root/'solver/summary.csv'
    source.parent.mkdir(parents=True)
    source.write_text('value\n1.00\n')
    receipt = put(root/'ARCHIVE_RECEIPT.json', {'status': 'ARCHIVE_VERIFIED', 'run_id': 'r',
        'retained_files': {'solver/summary.csv': {'sha256': f.sha256_file(source)}}})
    resolved = tmp_path/'resolved'
    put(resolved/'r/RECEIPT_REFERENCE.json', {'path': str(receipt), 'sha256': f.sha256_file(receipt)})
    pins = f.Pins()
    actual = f.receipt_catalog([{'run_id': 'r', 'archive_receipt': str(receipt)}], pins, resolved_root=resolved)
    assert actual['r'][0] == root
    assert pins.check(source) == source
    source.write_text('value\n2.00\n')
    with pytest.raises(ValueError, match='input changed'):
        pins.check(source)
    receipt.write_text('{}')
    with pytest.raises(ValueError, match='input changed'):
        f.receipt_catalog([{'run_id': 'r', 'archive_receipt': str(receipt)}], f.Pins(), resolved_root=resolved)


def test_unconsumed_receipt_members_are_metadata_only_but_consumption_checks_safety(tmp_path, monkeypatch):
    root = tmp_path/'archive'
    outside = tmp_path/'outside.csv'
    outside.write_text('outside')
    root.mkdir()
    (root/'linked.csv').symlink_to(outside)
    receipt = put(root/'ARCHIVE_RECEIPT.json', {'status': 'ARCHIVE_VERIFIED', 'run_id': 'r',
        'retained_files': {'missing.csv': {'sha256': 'a'*64},
                           'linked.csv': {'sha256': f.sha256_file(outside)}}})
    resolved = tmp_path/'resolved'
    put(resolved/'r/RECEIPT_REFERENCE.json', {'path': str(receipt), 'sha256': f.sha256_file(receipt)})
    original, checked = pack.safe_file, []
    def observe(path):
        checked.append(Path(path))
        return original(path)
    monkeypatch.setattr(pack, 'safe_file', observe)
    pins = f.Pins()
    f.receipt_catalog([{'run_id': 'r', 'archive_receipt': str(receipt)}], pins, resolved_root=resolved)
    assert root/'missing.csv' not in checked and root/'linked.csv' not in checked
    for name in ('missing.csv', 'linked.csv'):
        with pytest.raises(ValueError, match='absolute regular file'):
            pins.check(root/name)


def test_retained_registration_requires_receipt_rejects_escape_and_conflicting_pins(tmp_path):
    receipt = put(tmp_path/'ARCHIVE_RECEIPT.json', {})
    pins = f.Pins()
    with pytest.raises(ValueError, match='verified producer receipt'):
        pins.register_retained(receipt, 'a.csv', 'a'*64)
    pins.capture_metadata(receipt, 'resolved_archive_receipt')
    for name in ('../outside.csv', '/absolute.csv', 'x/../../outside.csv'):
        with pytest.raises(ValueError, match='Unsafe ZIP member'):
            pins.register_retained(receipt, name, 'a'*64)
    pins.register_retained(receipt, 'a.csv', 'a'*64)
    with pytest.raises(ValueError, match='Conflicting independently sealed'):
        pins.register_retained(receipt, 'a.csv', 'b'*64)


def test_metadata_capture_hashes_once_and_later_consumption_detects_change(tmp_path, monkeypatch):
    source = put(tmp_path/'checked.json', {'value': 1})
    original, calls = f.sha256_file, []
    def observe(path):
        calls.append(Path(path))
        return original(path)
    monkeypatch.setattr(f, 'sha256_file', observe)
    pins = f.Pins()
    pins.capture_metadata(source, 'already_parsed_metadata')
    assert calls == [source]
    source.write_text('{"value": 2}')
    with pytest.raises(ValueError, match='input changed'):
        pins.check(source)


def test_final_index_exact_match_binds_all_metrics_and_scalar_types_to_producer(tmp_path):
    native = {'run_id': 'r', 'nested': {'provider': ['one', 'two']}, 'flag': True}
    evaluations = [{'run_id': 'r', 'evaluator_version': version, 'metric': 1.25,
                    'metadata': {'source': 'synthetic_producer'}} for version in pack.VERSIONS]
    put(tmp_path/'r/RUN_RECORD.json', native)
    put(tmp_path/'r/EVALUATION_RECORDS.json', list(reversed(evaluations)))
    pins = f.Pins()
    result = f.verify_resolved_indices([native], evaluations, tmp_path, pins)
    assert result['status'] == 'PASS' and result['evaluation_rows'] == 2
    assert len(pins.values) == 2
    with pytest.raises(ValueError, match='native row differs'):
        f.verify_resolved_indices([dict(native, flag=1)], evaluations, tmp_path, f.Pins())
    changed = [dict(r, metric=1.25000001) if r['evaluator_version'] == 'v3' else r for r in evaluations]
    with pytest.raises(ValueError, match='evaluation row differs'):
        f.verify_resolved_indices([native], changed, tmp_path, f.Pins())
    changed = [dict(r, metadata={'source': 'different'}) for r in evaluations]
    with pytest.raises(ValueError, match='evaluation row differs'):
        f.verify_resolved_indices([native], changed, tmp_path, f.Pins())
    assert json.loads((tmp_path/'r/RUN_RECORD.json').read_text()) == native


def test_v21_hypothesis_contract_is_bound_to_execution_freeze_not_current_capture(tmp_path):
    reg = SimpleNamespace(code_root=tmp_path/'code')
    source = reg.code_root/'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml'
    source.parent.mkdir(parents=True)
    source.write_text('sensor_model_group_hash: test\nhypothesis_threshold: 10\n')
    stage = tmp_path/'stage'
    put(stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json', {'status': 'COMMITTED_PUSHED_EXECUTION_FREEZE',
        'contract_hash': f.sha256_file(source), 'sensor_model_group_hash': 'test'})
    assert f.frozen_v21_contract(reg, stage, f.Pins())['hypothesis_threshold'] == 10
    source.write_text('sensor_model_group_hash: test\nhypothesis_threshold: 11\n')
    with pytest.raises(ValueError, match='input changed'):
        f.frozen_v21_contract(reg, stage, f.Pins())


def test_new_diagnostic_join_matches_archived_payloads_and_complete_window_counts(tmp_path):
    records, receipts = [], {}
    pins = f.Pins()
    for dataset in f.diagnostics.DATASETS:
        for method in f.diagnostics.PROFILES:
            run = dataset+'_'+method
            record = {'run_id': run, 'method_id': method, 'dataset_id': dataset,
                      'case_id': f.pack.C00 if dataset == 'BY2' else dataset+'_natural'}
            records.append(record)
            payload = {key: [] for key in ('evaluations', 'consistency_rows', 'segment_rows', 'body_rows')}
            root, retained = tmp_path/'archive'/run, {}
            for version in pack.VERSIONS:
                identity = {**record, 'evaluator_version': version}
                archived = {'evaluation': identity,
                    'consistency_rows': [dict(identity, item=i) for i in range(4)],
                    'segment_rows': [dict(identity, item=i) for i in range(20 if dataset == 'BY2O' else 4)],
                    'body_rows': [dict(identity, item=0)]}
                relative = version+'/P13_DIAGNOSTICS/DIAGNOSTIC_ROWS.json'
                path = put(root/relative, archived)
                retained[relative] = {'sha256': f.sha256_file(path)}
                pins.add(path, retained[relative]['sha256'], 'synthetic_sealed_sidecar')
                payload['evaluations'].append(identity)
                for key in ('consistency_rows', 'segment_rows', 'body_rows'):
                    payload[key].extend(archived[key])
            receipts[run] = root, {'retained_files': retained}
            put(tmp_path/'DIAGNOSTICS'/f'{run}.json', payload)
    result = f.load_new_diagnostics(tmp_path, records, receipts, pins)
    assert len(result['segment_rows']) == 560 and len(result['body_rows']) == 60
    path = tmp_path/'DIAGNOSTICS'/f"{records[0]['run_id']}.json"
    payload = json.loads(path.read_text())
    payload['body_rows'][0]['item'] = 100
    put(path, payload)
    with pytest.raises(ValueError, match='differs from archived sidecar'):
        f.load_new_diagnostics(tmp_path, records, receipts, pins)


def residual_fixture():
    p11, p12, validations = {'sequences': {}}, {'sequences': {}}, {}
    pins = {name: {'path': '/synthetic/'+name+'.json', 'sha256': 'a'*64}
            for name in ('p11b', 'p12', *f.diagnostics.DATASETS)}
    for dataset in f.diagnostics.DATASETS:
        hv = {'n': 10, 'sigma_HV_mps': .30, 'mean_NE_norm_mps': .05,
              'axes_mps': {'N': {'n': 10, 'mean': .10}, 'E': {'n': 10, 'mean': .20}}}
        p11['sequences'][dataset] = {'hypotheses': {'H-C': hv}}
        windows = [('first_1000', [1, 2], 1000)]
        if dataset == 'BY2O':
            windows.append(('BY2O_standing', [3, 5], 20))
        old, new = [], []
        for name, interval, n in windows:
            before = {'roll': {'n': n, 'mean': .2}, 'pitch': {'n': n, 'mean': 2.2}}
            after = {'roll': {'n': n, 'mean': .2}, 'pitch': {'n': n, 'mean': -.42}}
            old.append({'name': name, 'interval_s': interval, 'n': n, 'RP_frozen_minus_gravity_deg': before})
            new.append({'name': name, 'interval_s': interval, 'n': n, 'residual_deg': after})
        p12['sequences'][dataset] = {'static_windows': old}
        validations[dataset] = {'passed': True, 'maximum_absolute_difference': 1e-10,
            'HV_final_scaled': dict(hv, sigma_HV_mps=.13), 'RP_static': new}
    return p11, p12, validations, pins


def test_sensor_residuals_bind_final_scaled_hv_and_four_separate_rp_windows():
    from legsa_gins.paper_rebuild.publication.protocol_v21_figures import residual_pairs
    p11, p12, validations, pins = residual_fixture()
    rows = f.residual_rows(p11, p12, validations, input_pins=pins)
    frame = pd.DataFrame(rows)
    _, hv = residual_pairs(frame, 'HV', 'horizontal', 'sigma_HV_mps')
    _, rp = residual_pairs(frame, 'RP', 'pitch', 'mean')
    assert len(hv) == 3 and hv.v21_final.eq(.13).all()
    assert len(rp) == 4 and rp.v21_final.eq(-.42).all()
    assert set(frame.loc[frame.sensor == 'HV', 'correction_detail']) == {'before', 'v21_scaled'}
    assert 'source_sha256' in frame
    validations['BY2O']['RP_static'][1]['n'] = 99
    with pytest.raises(ValueError, match='support differs'):
        f.residual_rows(p11, p12, validations, input_pins=pins)


def test_quality_projection_keeps_raw_tokens_and_requires_nominal_yaw_std(tmp_path):
    source = tmp_path/'GNSS18.gnss'
    tokens = ['100.000', *['0']*12, '12.000', '2.933193', '1', '1', '0']
    source.write_text('# source header\n'+'  '.join(tokens)+'\n')
    assert f.quality_rows(source) == [{'time': '100.000', 'yaw_deg': '12.000', 'yaw_std_deg': '2.933193', 'valid': '0', 'source_row': 2}]
    tokens[14] = '1.5'
    source.write_text(' '.join(tokens)+'\n')
    with pytest.raises(ValueError, match='nominal corrected'):
        f.quality_rows(source)


def test_downstream_tables_preserve_each_variant_noise_and_complete_grid():
    rows = []
    for version in pack.VERSIONS:
        for variant in f.downstream.LADDER:
            for method in f.downstream.METHODS:
                rows.append({'evaluator_version': version, 'diagnostic_family': 'LADDER', 'variant_id': variant,
                             'method_id': method, 'effective_profile': pack.CONFIG[method], 'unchanged_extra_metric': 1.234})
        for i in range(9):
            rows.append({'evaluator_version': version, 'diagnostic_family': 'NOISE_GRID', 'variant_id': f'N0{i}',
                         'method_id': 'A04', 'effective_profile': pack.CONFIG['A04'],
                         'grid_cell': {'abstd_mGal': 10+i, 'vrw_mps_sqrt_hour': 2+i}})
    original = copy.deepcopy(rows)
    tables = f.downstream_tables(rows)
    assert rows == original
    assert len(tables['v3']['ladder']) == 12 and tables['v3']['ladder'][0]['unchanged_extra_metric'] == 1.234
    assert [r['abstd_mGal'] for r in tables['v2']['grid']] == list(range(10, 19))
    with pytest.raises(ValueError, match='nine original'):
        f.downstream_tables(rows[:-1])


def test_exclusive_output_and_sealed_resume_do_not_overwrite(tmp_path):
    pins = f.Pins()
    path = tmp_path/'output/value.json'
    f.write_once(path, {'x': 1}, pins)
    before = path.read_bytes()
    f.write_once(path, {'x': 1}, pins)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match='output differs'):
        f.write_once(path, {'x': 2}, pins)
    assert path.read_bytes() == before


def test_cli_resolves_handoff_alias_and_dispatches_tables_only_without_execution(tmp_path, monkeypatch, capsys):
    local = tmp_path/'local.yaml'
    paths = {'code_root': str(tmp_path/'code'), 'raw_root': str(tmp_path/'raw'),
             'clean_root': str(tmp_path/'clean'), 'handoff_root': str(tmp_path/'handoff')}
    local.write_text(f.yaml.safe_dump({'paths': paths}))
    calls = []
    monkeypatch.setattr(f, 'run_finalize', lambda **kwargs: calls.append(kwargs) or {'status': 'MOCK_NO_EXECUTION'})
    f.main(['--local-config', str(local), '--handoff-zip', '<HANDOFF_ROOT>/c541_v21_handoff.zip',
            '--immutable-package', '<HANDOFF_ROOT>/c541_v2_handoff_v3.zip', '--code-commit', 'test', '--tables-only'])
    assert calls[0]['handoff_zip'] == Path(paths['handoff_root'])/'c541_v21_handoff.zip'
    assert calls[0]['build_package'] is False
    assert calls[0]['immutable_package_sha256'] == f.OLD_PACKAGE_SHA256
    assert json.loads(capsys.readouterr().out)['status'] == 'MOCK_NO_EXECUTION'


def test_package_publication_three_domain_and_sequence_curve_schema_close(tmp_path):
    """Synthetic package schema fixture, never a real-data artifact or figure."""
    from legsa_gins.paper_rebuild.publication.protocol_v21_data import Bundle
    def cells(dataset, cases, controlled):
        return [{'run_id': dataset+'_'+case+'_'+method, 'case_id': case, 'dataset_id': dataset,
                 'method_id': method, 'effective_configuration_id': config, 'evaluator_version': 'v3',
                 'formal_F01_reused': method == 'F01', 'synthetic_data_used': False,
                 'semisynthetic_data_used': controlled and case != pack.C00 and method != 'F01',
                 'trace_used_online': False, 'evaluation_status': 'COMPLETED', 'horizontal_rmse_m': 1.}
                for case in cases for method, config in pack.CONFIG.items()]
    core = cells('BY2', [pack.C00]+[f'D04_fixture_{i}' for i in range(540)], True)
    seq = [r for r in core if r['case_id'] == pack.C00]+cells('BY2H', ['H_natural'], False)+cells('BY2O', ['O_natural'], False)
    addendum = cells('BY2', [f'D61_fixture_{i}' for i in range(45)], True)
    writer = pack.PackageWriter(tmp_path/'schema-only-synthetic.zip', synthetic=True)
    writer.generated('12_OFFLINE_EVALUATION/v3/UNIQUE_EVALUATION_RESULTS.csv', pack._csv_bytes(core))
    writer.generated('13_AGGREGATE_SEQUENCES/v3/UNIQUE_EVALUATION_RESULTS.csv', pack._csv_bytes(seq))
    writer.generated('13_AGGREGATE_ADDENDUM/v3/UNIQUE_EVALUATION_RESULTS.csv', pack._csv_bytes(addendum))
    writer.generated('ADDENDUM_IDENTITY_PROBE.json', {'passed': True, 'synthetic_test_only': True})
    source = tmp_path/'synthetic_errors.csv'
    source.write_text('time,horizontal_err_m,yaw_err_deg\n0.000,1.000,2.000\n0.025,3.000,4.000\n0.105,5.000,6.000\n')
    member = 'error_series_subset/v3/example.csv.gz'
    pack.display_series(writer, source, member, f.sha256_file(source), source_protocol=pack.PROTOCOL, run_id='example')
    manifest = [dict(next(r for r in seq if r['dataset_id'] == 'BY2' and r['method_id'] == 'F04'), member=member, status='OK')]
    writer.generated('sequence_error_series_subset/v3/SUBSET_MANIFEST.csv', pack._csv_bytes(manifest))
    writer.close({'passed': True, 'protocol_id': pack.PROTOCOL, 'synthetic_test_only': True})
    bundle = Bundle(writer.path)
    assert len(bundle.unique) == 5951 and len(bundle.sequences) == 33 and len(bundle.addendum()) == 495
    frame = bundle.sequence_series('BY2', 'F04')
    assert frame.time.tolist() == [0., .105]
    identity = next(row for row in bundle.p.sources() if row['package_member'] == member)
    assert identity['original_source_rows'] == [2, 4]
