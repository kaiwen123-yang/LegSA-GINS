"""Apply only the registered D61/D62 validity outages to frozen CAL providers."""
from __future__ import annotations

from pathlib import Path
import hashlib
import re

import numpy as np

from ..canonical541 import provider_generator as canonical
from ..clean5_degradation.common import FLAGS, write_json, write_csv
from ..clean5_degradation.providers import SOURCE_TO_ROLE, FILENAMES, _diff_source, _gnss_rows, _valid
from ..manifest import sha256_file

STAGE_NAME = 'CLEAN6_ADDENDUM_FAMILIES_A1_A2'
SOURCES = {'D61': ('gnss_position', 'receiver_velocity', 'raw_doppler', 'dual_yaw'),
           'D62': ('gnss_position', 'receiver_velocity', 'raw_doppler')}
DURATIONS = {'D61': (10, 20, 30), 'D62': (10, 20)}


def apply_outage(base, case):
    """Clone first; unchanged observations and sparse original yaw events survive."""
    tid = case['degradation_type_id']
    if tid not in SOURCES or float(case['duration_s']) not in DURATIONS[tid]:
        raise ValueError('Outside the pre-registered D61/D62 duration grid')
    generated = base.bundle.clone()
    components = canonical._outage(generated, case, SOURCES[tid], float(case['duration_s']))
    start, end = canonical._interval(case, float(case['duration_s']))
    checks = []
    for name, before in base.bundle.tables.items():
        after = generated.tables[name]
        if len(before.rows) != len(after.rows):
            raise ValueError('Addendum outage changed the number of observations')
        for left, right in zip(before.rows, after.rows):
            selected = name in SOURCES[tid] and start <= float(left['time']) < end
            permitted = {'valid', 'update_flag', 'status', 'source_status', 'provider_status'} if selected else set()
            changed = {key for key in set(left) | set(right) if left.get(key) != right.get(key)}
            if changed - permitted or (selected and _valid(right)) or (not selected and left != right):
                raise ValueError('Outage semantic mutation escaped its registered source/interval')
        checks.append({'source': name, 'passed': True, 'outage_selected': name in SOURCES[tid],
                       'row_count': len(after.rows), 'before_valid_count': sum(_valid(r) for r in before.rows),
                       'after_valid_count': sum(_valid(r) for r in after.rows),
                       'rows_inside_interval': sum(start <= float(r['time']) < end for r in before.rows),
                       'rows_outside_interval': sum(not start <= float(r['time']) < end for r in before.rows),
                       'before_sha256': hashlib.sha256(before.canonical_bytes()).hexdigest(),
                       'after_sha256': hashlib.sha256(after.canonical_bytes()).hexdigest()})
    rows = _gnss_rows(base, generated, tid)
    before, after = np.asarray(base.gnss_tokens, float), np.asarray(rows, float)
    if (after.shape != before.shape or after.shape[1] != 18 or not np.isfinite(after).all()
            or not np.array_equal(before[:, :15], after[:, :15])
            or not np.isin(after[:, 15:], [0, 1]).all() or np.any(after[:, 15:] > before[:, 15:])):
        raise ValueError('GNSS18 payload/time/independent-validity contract failed')
    if tid == 'D62' and not np.array_equal(before[:, 17], after[:, 17]):
        raise ValueError('D62 must retain exactly the existing effective dual-yaw events')
    diff = {name: _diff_source(base.bundle.tables[name], table, tid)
            for name, table in generated.tables.items()}
    evidence = {'status': 'PASS', 'checks': checks, 'interval': [start, end],
                'interval_endpoint_policy': 'half-open [start,end)',
                'canonical_handler': 'canonical541.provider_generator._outage',
                'finite_payload_unchanged': True, 'observation_times_unchanged': True,
                'Go2_RP_HV_unchanged': True, 'trace_opened': False, 'diff_before_after': diff}
    return generated, rows, components, evidence


def generate_case(base, case, output_root, *, code_commit, config_hash):
    """Exclusive case output. No raw reader, native run, evaluation, or retries."""
    if base.data_mode != 'synthetic_test' and (not re.fullmatch(r'[0-9a-f]{40}', code_commit)
                                              or not re.fullmatch(r'[0-9a-f]{64}', config_hash)):
        raise ValueError('Real provider requires full committed code/config identities')
    root = Path(output_root)
    if not root.is_absolute() or '..' in root.parts or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Provider destination requires an absolute, non-symlink owned path')
    if base.data_mode != 'synthetic_test' and STAGE_NAME not in root.parts:
        raise ValueError('Real addendum provider requires the addendum stage namespace')
    for pin in (*base.providers.values(), *base.auxiliary_roles.values()):
        source = Path(pin['path'])
        if root == source.parent or root.is_relative_to(source.parent) or source.is_relative_to(root):
            raise ValueError('Provider destination overlaps immutable inputs')
    generated, rows, components, evidence = apply_outage(base, case)
    case_root = root / case['case_id']
    case_root.mkdir(parents=True, exist_ok=False)
    providers = {role: {**pin, 'storage_mode': 'pinned_unchanged_pointer'} for role, pin in base.providers.items()}
    lines = list(base.gnss_lines)
    for i, row in enumerate(rows):
        if row != base.gnss_tokens[i]:
            lines[base.gnss_data_line_indices[i]] = ' '.join(row)+'\n'
    target = case_root / FILENAMES['gnsspath']
    with target.open('xb') as stream:
        stream.write(''.join(lines).encode())
    providers['gnsspath'] = {'path': str(target), 'sha256': sha256_file(target), 'storage_mode': 'materialized'}
    for source, role in SOURCE_TO_ROLE.items():
        table = generated.tables[source]
        if table.canonical_bytes() == base.bundle.tables[source].canonical_bytes():
            continue
        target = case_root / FILENAMES[role]
        with target.open('xb') as stream:
            stream.write(table.canonical_bytes())
        providers[role] = {'path': str(target), 'sha256': sha256_file(target), 'storage_mode': 'materialized'}
    result = {**FLAGS, 'schema_version': 'clean6.addendum_provider.v1', 'protocol_id': STAGE_NAME,
              'case_id': case['case_id'], 'case_root': str(case_root), 'chain': 'CAL',
              'data_mode': 'synthetic_test' if base.synthetic_data_used else 'semisynthetic',
              'synthetic_data_used': base.synthetic_data_used, 'semisynthetic_data_used': not base.synthetic_data_used,
              'controlled_degradation_applied': True, 'providers': providers, 'components': components,
              'base_provider_pins': base.providers, 'auxiliary_source_pins': base.auxiliary_roles,
              'raw_input_hashes': dict(base.bundle.raw_input_hashes), 'a1_association': base.a1_audit,
              'code_commit': code_commit, 'config_hash': config_hash, 'case_meta': case,
              'semantic_equivalence': evidence, 'runtime_contract': {'gnss_columns': 18,
                  'gnss_row_count': len(rows), 'position_valid_count': sum(int(r[15]) for r in rows),
                  'rv_valid_count': sum(int(r[16]) for r in rows), 'a1_valid_count': sum(int(r[17]) for r in rows)},
              'solver_execution_count': 0, 'evaluator_execution_count': 0}
    mapping = []
    for check in evidence['checks']:
        source = check['source']
        role = SOURCE_TO_ROLE.get(source, 'gnsspath' if source in ('gnss_position', 'receiver_velocity', 'dual_yaw') else None)
        mapping.append({'case_id': case['case_id'], 'source': source, 'solver_input_role': role,
            'base_provider_sha256': base.providers[role]['sha256'] if role else None,
            'generated_provider_sha256': providers[role]['sha256'] if role else None,
            'outage_start_s': evidence['interval'][0], 'outage_end_s': evidence['interval'][1], **check})
    write_csv(case_root/'PROVIDER_MAPPING.csv', mapping)
    write_json(case_root / 'PROVIDER_DIFF_SUMMARY.json', evidence)
    write_json(case_root / 'PROVIDER_BUNDLE.json', result)
    return result
