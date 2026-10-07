#!/usr/bin/env python3
"""One BY2O local-partial x foot pilot under a disclosed position-product gap.

prepare freezes four complete-window inputs; native/evaluate reuse the existing
continuous_heading_navigation runner. No raw or reference is read by prepare.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts/paper_rebuild/carrier_phase')]
import continuous_heading_navigation as nr
from navigation_trial import clone_config

WINDOW = (3186.0, 3563.0)
GAP = (3278.598000049591, 3310.3980000019073)
ARMS = (
    ('SDK_GAP_FULL_ONLY', 'SDK_NULL', 'GAP_FULL_ONLY'),
    ('SDK_GAP_PARTIAL', 'SDK_NULL', 'GAP_PARTIAL'),
    ('FOOT_GAP_FULL_ONLY', 'REPLACE_SUPPORT', 'GAP_FULL_ONLY'),
    ('FOOT_GAP_PARTIAL', 'REPLACE_SUPPORT', 'GAP_PARTIAL'),
)
STATE_FILES = ('LegSA_PORT_NAV.nav', 'KF_GINS_Navresult.nav', 'KF_GINS_STD.txt',
               'KF_GINS_IMU_ERR.txt', 'LegSA_PORT_STD.csv')


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def csv_write(path, rows):
    with path.open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def local_carrier_inputs(rolling_path, full_path):
    rolling_bytes, full_bytes = rolling_path.read_bytes(), full_path.read_bytes()
    rolling_lines, full_lines = rolling_bytes.splitlines(keepends=True), full_bytes.splitlines(keepends=True)
    rolling = list(csv.DictReader(io.StringIO(rolling_bytes.decode())))
    full = list(csv.DictReader(io.StringIO(full_bytes.decode())))
    assert len(rolling) == len(full) == 1885
    assert len(rolling_lines) == len(rolling) + 1 and len(full_lines) == len(full) + 1
    assert rolling_lines[0] == full_lines[0]
    times = [float(r['measurement_time']) for r in rolling]
    assert times == [float(r['measurement_time']) for r in full]
    full_indices = [i for i, r in enumerate(full) if r['valid'] == '1']
    partial = [i for i, r in enumerate(rolling) if r['valid'] == '1' and full[i]['valid'] == '0']
    assert len(full_indices) == 168 and len(partial) == 117
    assert all(rolling_lines[i + 1] == full_lines[i + 1] for i in full_indices)
    candidates = []
    for left, right in zip(full_indices, full_indices[1:]):
        inside = [i for i in partial if left < i < right]
        if inside:
            candidates.append((times[right] - times[left], times[left], times[right], inside))
    selected = max(candidates, key=lambda item: item[0])
    assert tuple(selected[1:3]) == GAP and len(selected[3]) == 30
    indices = selected[3]
    altered = list(rolling_lines)
    audit = []
    for i in indices:
        assert GAP[0] < times[i] < GAP[1] and full[i]['valid'] == '0'
        altered[i + 1] = full_lines[i + 1]
        audit.append(dict(provider_row_zero_based=i, file_line_one_based=i + 2, time=times[i],
                          rolling_valid=rolling[i]['valid'], full_valid=full[i]['valid'],
                          before_row_sha256=sha_bytes(rolling_lines[i + 1]),
                          after_row_sha256=sha_bytes(altered[i + 1]),
                          changed_columns=';'.join(k for k in rolling[i] if rolling[i][k] != full[i][k])))
    changed = [i - 1 for i, (a, b) in enumerate(zip(rolling_lines, altered)) if a != b]
    assert changed == indices
    assert all(altered[i + 1] == rolling_lines[i + 1] for i in range(len(rolling)) if i not in indices)
    return rolling_bytes, b''.join(altered), audit, dict(
        selection='Longest consecutive-valid-FULL endpoint interval containing ROLLING-only partial; source-only selection',
        gap_open_interval=list(GAP), duration_s=GAP[1] - GAP[0],
        original_rolling_valid=285, original_full_valid=168, original_partial=117,
        local_partial_rows=30, outside_partial_rows_unchanged=87,
        first_affected_partial_time=times[indices[0]], last_affected_partial_time=times[indices[-1]],
        changed_provider_rows=indices, changed_rows_exactly_30=True,
        outside_rows_and_full_endpoints_byte_identical=True,
        local_full_only_is_not_whole_window_full_algorithm=True)


def position_product_gap(payload):
    output, audit, permitted_offsets = [], [], []
    offset, data_rows = 0, 0
    for line_number, line in enumerate(payload.splitlines(keepends=True), start=1):
        if not line.strip() or line.lstrip().startswith(b'#'):
            output.append(line)
            offset += len(line)
            continue
        tokens = list(re.finditer(rb'\S+', line))
        assert len(tokens) == 18
        data_rows += 1
        time = float(tokens[0].group())
        modified = line
        if GAP[0] < time < GAP[1]:
            token = tokens[15]
            assert token.group() == b'1'
            modified = line[:token.start()] + b'0' + line[token.end():]
            permitted_offsets.append(offset + token.start())
            audit.append(dict(file_line_one_based=line_number, source_time=time,
                              column_one_based=16, before='1', after='0', byte_offset=offset + token.start()))
        old_tokens, new_tokens = line.split(), modified.split()
        actual_columns = [i + 1 for i, (a, b) in enumerate(zip(old_tokens, new_tokens)) if a != b]
        assert actual_columns == ([16] if GAP[0] < time < GAP[1] else [])
        assert len(modified) == len(line)
        output.append(modified)
        offset += len(line)
    result = b''.join(output)
    differences = [i for i, (a, b) in enumerate(zip(payload, result)) if a != b]
    assert len(payload) == len(result) and differences == permitted_offsets and len(audit) == 159
    return result, audit, dict(
        interval=list(GAP), interval_semantics='open', affected_rows=159, differing_bytes=159,
        affected_column_one_based=16, change='position_valid 1 -> 0', all_18_columns_checked=True,
        original_text_tokens_and_whitespace_preserved_except_159_single_bytes=True,
        data_rows=data_rows, first_affected_position_time=audit[0]['source_time'],
        last_affected_position_time=audit[-1]['source_time'],
        position_values_and_std_unchanged=True, receiver_velocity_and_yaw_all_columns_unchanged=True,
        original_sha256=sha_bytes(payload), derived_sha256=sha_bytes(result))


def prepare(a):
    previous, parent = nr.read(a.template_plan), nr.read(a.parent_plan)
    old = previous['runs'][0]
    assert len(previous['runs']) == 1 and old['sequence_id'] == 'BY2O' and old['arm'] == 'VECTOR'
    payload = nr.checked(old['config']).read_bytes()
    cfg = yaml.safe_load(payload)
    assert cfg['runtime_contract'] == 'research_experiment' and cfg['heading_source_policy'] == 'configured'
    assert cfg['support_pose_mode'] == 'REPLACE_SUPPORT' and cfg['support_pose_observed_axes'] == 'body0_xy'
    assert cfg['go2_body_velocity_discrepancy_mode'] == 'off'
    assert (cfg['starttime'], cfg['endtime']) == WINDOW == tuple(old['window'])
    assert old['carrier'] == parent['carrier']
    rolling_path, full_path = nr.checked(old['carrier']), nr.checked(parent['full_carrier'])
    assert str(rolling_path) == cfg['external_carrier_baseline_path']
    for item in old['providers'].values():
        nr.checked(item)
    original_gnss = nr.checked(old['providers']['gnsspath'])
    assert str(original_gnss) == cfg['gnsspath']
    nr.checked(previous['scenario_masks'])
    rolling, full_only, carrier_audit, carrier_contract = local_carrier_inputs(rolling_path, full_path)
    altered_gnss, position_audit, position_contract = position_product_gap(original_gnss.read_bytes())
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / 'PROVIDERS').mkdir()
    (a.output / 'CONFIGS').mkdir()
    (a.output / 'BINARY').mkdir()
    binary = a.output / 'BINARY/legsa_v23_port_core_demo'
    shutil.copy2(a.binary, binary)
    gnss = a.output / 'PROVIDERS/GNSS18_POSITION_PRODUCT_GAP.gnss'
    gnss.write_bytes(altered_gnss)
    carriers = {}
    for name, content in (('GAP_PARTIAL', rolling), ('GAP_FULL_ONLY', full_only)):
        path = a.output / 'PROVIDERS' / (name + '.csv')
        path.write_bytes(content)
        carriers[name] = nr.pin(path)
    assert carriers['GAP_PARTIAL']['sha256'] == old['carrier']['sha256']
    csv_write(a.output / 'POSITION_VALIDITY_CHANGES.csv', position_audit)
    csv_write(a.output / 'LOCAL_PARTIAL_ROW_CHANGES.csv', carrier_audit)
    runs = []
    identity_keys = {'run_id', 'run_label', 'case_id', 'outputpath'}
    for arm, support_mode, carrier_mode in ARMS:
        rid = 'BY2O__' + arm
        fields = dict(run_id=rid, run_label=rid, case_id=rid, outputpath=str(a.output / 'NATIVE' / rid),
                      gnsspath=str(gnss), external_carrier_baseline_path=carriers[carrier_mode]['path'],
                      support_pose_mode=support_mode, data_mode='semisynthetic',
                      semisynthetic_data_used=True, synthetic_data_used=False,
                      stage_id='UNIFIED_POSITION_PRODUCT_GAP_20261007',
                      protocol_id='POSITION_PRODUCT_GAP_PARTIAL_SUPPORT_INTERACTION_V1')
        content, changes = clone_config(payload, fields)
        actual = yaml.safe_load(content)
        assert {k: v for k, v in actual.items() if k not in fields} == {k: v for k, v in cfg.items() if k not in fields}
        config = a.output / 'CONFIGS' / (rid + '.yaml')
        config.write_bytes(content)
        providers = dict(old['providers'], gnsspath=nr.pin(gnss))
        runs.append(dict(old, run_id=rid, arm=arm, config=nr.pin(config), template=old['config'],
                         changes=changes, carrier=carriers[carrier_mode], providers=providers,
                         carrier_support=nr.carrier_summary(Path(carriers[carrier_mode]['path']), WINDOW),
                         support_mode=support_mode, local_carrier_mode=carrier_mode,
                         scientific_changes=[c for c in changes if c['field'] not in identity_keys]))
    common_keys = identity_keys | {'support_pose_mode', 'external_carrier_baseline_path'}
    scientific = [{k: v for k, v in yaml.safe_load(nr.checked(r['config']).read_bytes()).items() if k not in common_keys} for r in runs]
    assert all(s == scientific[0] for s in scientific)
    plan = dict(
        schema='position_product_gap_local_partial_support.v1', runner=nr.pin(__file__),
        template_plan=nr.pin(a.template_plan), parent_plan=nr.pin(a.parent_plan), binary=nr.pin(binary),
        source_pins=[nr.pin(ROOT / p) for p in [
            'scripts/paper_rebuild/carrier_phase/continuous_heading_navigation.py',
            'scripts/paper_rebuild/carrier_phase/navigation_trial.py',
            'cpp/legsa_v23_port_core/src/config/port_config_loader.cpp']],
        runs=runs, sequences=previous['sequences'], evaluator=previous['evaluator'],
        aliases=previous['aliases'], scenario_masks=previous['scenario_masks'],
        original_gnss=old['providers']['gnsspath'], original_rolling_carrier=old['carrier'],
        original_full_carrier=parent['full_carrier'], position_intervention=position_contract,
        local_carrier_intervention=carrier_contract,
        change_tables=[nr.pin(a.output / name) for name in ('POSITION_VALIDITY_CHANGES.csv', 'LOCAL_PARTIAL_ROW_CHANGES.csv')],
        window=list(WINDOW), native_budget=4, evaluator_budget=4, reference_online=False,
        data_mode='semisynthetic', semisynthetic_data_used=True, synthetic_data_used=False,
        controlled_receiver_position_product_interruption=True, natural_gnss_outage=False,
        science='MOTION is the common full-window background. Only 30 in-gap partial rows differ within each support-mode pair; all four arms share the same 159 position-validity changes.',
        frozen_inputs=['PVT velocity/yaw values and validity', 'raw Doppler', 'foot endpoints/events',
                       'SDK body velocity', 'RP', 'IMU', 'initialization', 'all noise and gates',
                       'full time window', 'carrier full endpoints and all outside-gap rows'],
        required_pre_partial_identity=dict(before_time=carrier_contract['first_affected_partial_time'],
            pairs=[['SDK_GAP_FULL_ONLY', 'SDK_GAP_PARTIAL'], ['FOOT_GAP_FULL_ONLY', 'FOOT_GAP_PARTIAL']],
            files=list(STATE_FILES), requirement='All saved rows strictly before the first changed partial are byte-identical within each pair.'),
        contrasts=['SDK partial minus SDK local-full-only', 'FOOT partial minus FOOT local-full-only',
                   'Difference of those two paired effects; support mode also changes the prescribed SDK replacement schedule.'],
        interpretation='Controlled position-product availability on real motion/carrier/support inputs; not raw-GNSS extinction, natural outage, whole-window FULL-vs-ROLLING, or independent-truth validation.',
        evaluation_context='Reuse parent evaluator and full-window context; no reference access by prepare/native and no source-window selection from errors.')
    nr.emit(a.output / 'PLAN.json', plan)
    print(json.dumps(dict(prepared=str(a.output), plan_sha256=nr.digest(a.output / 'PLAN.json'),
                         binary=plan['binary'], arms=[r['arm'] for r in runs],
                         position_changes=159, local_partial_changes=30,
                         first_affected_partial_time=carrier_contract['first_affected_partial_time']), indent=2))


def pre_partial_identity(stage, plan):
    before = plan['required_pre_partial_identity']['before_time']
    runs = {r['arm']: r for r in plan['runs']}
    records = []
    for names in plan['required_pre_partial_identity']['pairs']:
        roots = [stage / 'NATIVE' / runs[name]['run_id'] for name in names]
        statuses = [nr.read(root / 'RESULT.json')['status'] for root in roots]
        if statuses != ['COMPLETED', 'COMPLETED']:
            records.append(dict(arms=names, status='UNAVAILABLE_NATIVE_FAILURE', native_status=statuses))
            continue
        all_lines = [[line for line in (root / 'KF_GINS_Navresult.nav').read_bytes().splitlines(keepends=True) if line.strip()] for root in roots]
        counts = [sum(float(line.split()[1]) < before for line in lines) for lines in all_lines]
        files = []
        for name in STATE_FILES:
            prefixes = []
            for root, count in zip(roots, counts):
                lines = (root / name).read_bytes().splitlines(keepends=True)
                header = 1 if name in ('LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv') else 0
                prefixes.append(b''.join(lines[:count + header]))
            files.append(dict(file=name, rows=counts, byte_equal=counts[0] == counts[1] and prefixes[0] == prefixes[1],
                              sha256=[sha_bytes(value) for value in prefixes]))
        passed = counts[0] > 0 and all(item['byte_equal'] for item in files)
        records.append(dict(arms=names, status='PASS' if passed else 'PRE_PARTIAL_STATE_MISMATCH', files=files))
    report = dict(status='PASS' if all(r['status'] == 'PASS' for r in records) else 'REQUIRES_INSPECTION',
                  before_time=before, pairs=records, plan_sha256=nr.digest(stage / 'PLAN.json'))
    nr.emit(stage / 'PRE_PARTIAL_STATE_IDENTITY.json', report)
    print('PRE_PARTIAL_STATE_IDENTITY', report['status'], flush=True)


def execute(a):
    plan = nr.read(a.output / 'PLAN.json')
    assert len(plan['runs']) == plan['native_budget'] == plan['evaluator_budget'] == 4
    nr.checked(plan['runner'])
    for item in [plan['template_plan'], plan['parent_plan'], plan['original_gnss'],
                 plan['original_rolling_carrier'], plan['original_full_carrier'], *plan['source_pins'], *plan['change_tables']]:
        nr.checked(item)
    for run in plan['runs']:
        for item in run['providers'].values():
            nr.checked(item)
    args = SimpleNamespace(output=a.output, timeout=a.timeout)
    if a.command == 'native':
        nr.native(args)
        pre_partial_identity(a.output, plan)
    else:
        identity = nr.read(a.output / 'PRE_PARTIAL_STATE_IDENTITY.json')
        if identity['status'] != 'PASS' or identity['plan_sha256'] != nr.digest(a.output / 'PLAN.json'):
            raise RuntimeError('Inspect pre-partial paired state identity before evaluation')
        nr.evaluate(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'native', 'evaluate'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--template-plan', type=Path)
    parser.add_argument('--parent-plan', type=Path)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--timeout', type=float, default=1200.)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.command == 'prepare':
        if any(value is None for value in (args.template_plan, args.parent_plan, args.binary)):
            parser.error('prepare requires --template-plan, --parent-plan and --binary')
        prepare(args)
    else:
        execute(args)
