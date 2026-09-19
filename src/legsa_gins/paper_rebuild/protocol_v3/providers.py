"""Heading-only byte transforms. Real I/O is explicit and requires a pushed freeze.

The unchanged T5a provider generates the three clean R5 tables. Frozen injected
heading events are lifted by preregistered time cells; all other provider bytes,
including case-specific yaw standard deviations and HV files, are preserved.
"""
from __future__ import annotations

import bisect
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

import numpy as np
import yaml

from ..hext import heading_provider as hp
from ..hext.t5a_provider import raw_yaw_from_ned, build_t5a_variants
from ..hext.sequence_paths import load_sequence_paths, REGISTRY, CALIBRATED_CONTRACT
from ..clean5_parity.input_audit import decode_receiver
from ..horizontal_literature.ext05_provider import fixed_ecef_to_ned_rotation
from ..manifest import sha256_file

YAW, VALID = 13, 17
PERTURBED = {'D32', 'D33', 'D34', 'D35', 'D38', 'D41', 'D58', 'D60'}
CELL_DROPOUT = {'D11', 'D12'}
OUTAGE = {'D06', 'D30', 'D31', 'D39', 'D61'}
FLAGS = dict(synthetic_data_used=False, semisynthetic_data_used=False,
    trace_used_online=False, receiver_imu_as_body_imu=False,
    final_v23_output_solver_input=False, LegSA_output_solver_input=False,
    per_case_tuning=False, output_only_correction=False,
    epoch_deleted_for_metric=False, old_runtime_input_count=0)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def byte_gate(before, after):
    """Independently prove every non-heading token and whitespace byte identical."""
    old, width = hp._rows(before)
    new, new_width = hp._rows(after)
    if width != 18 or new_width != 18 or len(old) != len(new):
        raise ValueError('HARD_STOP_V3_PROVIDER_SHAPE')
    if len(before.splitlines(keepends=True)) != len(after.splitlines(keepends=True)):
        raise ValueError('HARD_STOP_V3_PROVIDER_LINE_COUNT')
    changed = [0] * 18
    normalized = after.splitlines(keepends=True)
    for left, right in zip(old, new):
        if left['line_index'] != right['line_index']:
            raise ValueError('HARD_STOP_V3_PROVIDER_ROW_IDENTITY')
        for column, (a, b) in enumerate(zip(left['tokens'], right['tokens'])):
            changed[column] += a != b
            if column not in (YAW, VALID) and a != b:
                raise ValueError(f'HARD_STOP_V3_NON_HEADING_COLUMN_{column + 1}')
        normalized[right['line_index']] = hp._replace_tokens(right,
            {YAW: left['tokens'][YAW], VALID: left['tokens'][VALID]})
    if b''.join(normalized) != before:
        raise ValueError('HARD_STOP_V3_NON_HEADING_WHITESPACE')
    return dict(passed=True, rows=len(old), changed_tokens_by_column=changed,
        allowed_columns_zero_based=[YAW, VALID], all_other_bytes_identical=True,
        before_sha256=digest(before), after_sha256=digest(after))


def frozen_cells(clean_bytes, fault_rows):
    """Recover realized scalar input perturbations, never estimator errors."""
    clean, _ = hp._rows(clean_bytes)
    base = [r for r in clean if float(r['tokens'][VALID]) == 1]
    times = [float(r['tokens'][0]) for r in base]
    if len(times) < 2 or any(abs((b-a)-1.) > 1e-6 for a,b in zip(times,times[1:])):
        raise ValueError('HARD_STOP_V3_FROZEN_A1_CELL_SCHEDULE')
    if len(fault_rows) != len(base):
        raise ValueError('HARD_STOP_V3_FROZEN_A1_AUDIT_ROW_COUNT')
    result = []
    for index, (reference, fault) in enumerate(zip(base, fault_rows)):
        if abs(float(fault['time']) - times[index]) > 1e-6:
            raise ValueError('HARD_STOP_V3_FROZEN_A1_AUDIT_TIME')
        delta = (float(fault['yaw_deg'])-float(reference['tokens'][YAW])+180.) % 360.-180.
        result.append(dict(start_s=times[index], end_s=times[index+1] if index+1<len(times) else times[index]+1.,
            delta_deg=delta, valid=str(fault['valid']).lower() in ('1','true')))
    return result


def fault_intervals(components, type_id):
    intervals = []
    if type_id not in OUTAGE | {'D58', 'D60'}:
        return intervals
    for component in components:
        details = component.get('details', {})
        source = component.get('affected_source', '')
        if type_id == 'D39' or 'yaw' in source or (type_id == 'D58' and source == 'gnss_position'):
            values = details.get('intervals', [])
            if 'interval' in details:
                values = [details['interval']]
            for value in values:
                if isinstance(value,dict):
                    value = (value['start_s'],value['end_s'])
                pair = tuple(map(float, value))
                if pair not in intervals:
                    intervals.append(pair)
    if not intervals:
        raise ValueError('HARD_STOP_V3_MISSING_FROZEN_HEADING_INTERVAL_'+type_id)
    return sorted(intervals)


def lift_heading(template, clean_r5, clean_frozen, *, type_id='CLEAN', fault_rows=(), components=(), base_time=1772784000., anchor_time_s=None):
    """Overlay yaw/valid only on an immutable case table with exact raw keys.

    The cell lift preserves original seeded event realizations and half-open
    durations. It is not independently sampled 5 Hz noise. D57 never matches a
    neighbour or repairs a timestamp. Inherited case std exposure stays intact.
    """
    original, width = hp._rows(template)
    raw_rows, _ = hp._rows(clean_r5)
    if width != 18:
        raise ValueError('HARD_STOP_V3_EXPECTED_GNSS18')
    raw_map = {hp.time_to_itow_ms(r['tokens'][0], gps_week=2408, base_time=base_time):r for r in raw_rows}
    cells = frozen_cells(clean_frozen, fault_rows) if type_id in PERTURBED | CELL_DROPOUT else []
    starts = [c['start_s'] for c in cells]
    intervals = fault_intervals(components, type_id)
    keep_keys = None
    if type_id in {'D08','D09','D10'}:
        if anchor_time_s is None:
            raise ValueError('HARD_STOP_V3_MISSING_DOWNSAMPLE_ANCHOR')
        rate = {'D08':5.,'D09':2.,'D10':1.}[type_id]
        valid_items = [(k,r) for k,r in raw_map.items() if float(r['tokens'][VALID]) == 1.]
        times = np.array([float(r['tokens'][0]) for k,r in valid_items])
        keep_keys = {k for k,r in valid_items}
        if len(times) >= 2 and 1./float(np.median(np.diff(times))) > rate+1e-9:
            phase = float(anchor_time_s) % (1./rate)
            slots = np.floor((times-phase)*rate+1e-9).astype(np.int64)
            first = np.unique(slots,return_index=True)[1]
            keep_keys = {valid_items[i][0] for i in first}
    lines = template.splitlines(keepends=True)
    active = matched = changed_by_fault = 0
    for row in original:
        t = float(row['tokens'][0])
        try:
            key = hp.time_to_itow_ms(row['tokens'][0], gps_week=2408, base_time=base_time)
        except hp.HeadingProviderError:
            if type_id != 'D57':
                raise
            key = None
        raw = raw_map.get(key)
        valid = raw is not None and float(raw['tokens'][VALID]) == 1.
        replacements = {VALID: b'1' if valid else b'0'}
        if valid:
            matched += 1
            replacements[YAW] = raw['tokens'][YAW]
        i = bisect.bisect_right(starts, t+1e-7)-1
        cell = cells[i] if i >= 0 and t < cells[i]['end_s']-1e-7 else None
        inside = any(a <= t < b for a,b in intervals)
        if valid and ((type_id in OUTAGE and inside) or
                      (type_id in CELL_DROPOUT and cell and not cell['valid']) or
                      (keep_keys is not None and key not in keep_keys)):
            valid = False; replacements[VALID] = b'0'; changed_by_fault += 1
        if valid and type_id in PERTURBED and cell and (type_id not in {'D58','D60'} or inside):
            delta = cell['delta_deg']
            if delta != 0.:
                value = (float(raw['tokens'][YAW])+delta) % 360.
                token = f'{value:.6f}'.encode()
                replacements[YAW] = b'0.000000' if token == b'360.000000' else token
                changed_by_fault += 1
        active += valid
        lines[row['line_index']] = hp._replace_tokens(row, replacements)
    payload = b''.join(lines)
    gate = byte_gate(template, payload)
    if type_id == 'D57' and active:
        raise ValueError('HARD_STOP_V3_D57_NONZERO_VALID_HEADING')
    return payload, {**gate, 'type_id':type_id, 'valid_heading_rows':active,
        'raw_matched_valid_rows':matched, 'rows_affected_by_heading_fault':changed_by_fault,
        'frozen_fault_intervals':intervals, 'fault_cells':cells,
        'time_mapping':'FROZEN_A1_HALF_OPEN_TIME_CELLS_NO_RNG_REDRAW',
        'all_case_std_bytes_preserved':True, 'HV_regenerated':False}


def _checked(reference, resolve):
    path = resolve(reference['path'])
    if path.is_symlink() or not path.is_file() or sha256_file(path) != reference['sha256']:
        raise ValueError('HARD_STOP_V3_SOURCE_PIN:'+str(path))
    return path


def prepare_providers(local_config, registry, code_freeze, contract):
    """Generate once below v3 scratch, after caller verified pushed code freeze."""
    paths = yaml.safe_load(Path(local_config).read_text())['paths']
    scratch = Path(paths['protocol_v3_scratch'])
    code = Path(paths['code_root'])
    def resolve(value):
        for key, root in paths.items():
            value = value.replace('<'+key.upper()+'>', str(root))
        return Path(value) if Path(value).is_absolute() else code/value
    out = scratch/'02_PROVIDERS'
    if out.exists():
        raise FileExistsError('Existing v3 providers must be verified, never overwritten')
    out.mkdir(parents=True)
    source_index = json.loads(_checked(contract['provider_source_index'], resolve).read_text())
    references = contract['frozen']['r5_providers']
    archive_pin = contract['frozen']['t5a_handoff']
    archive_path = _checked(archive_pin, resolve)
    with zipfile.ZipFile(archive_path) as archive:
        member = archive.read(archive_pin['by2_r5_member'])
    if digest(member) != references['BY2']['sha256']:
        raise ValueError('HARD_STOP_V3_T5AR_HANDOFF_MEMBER_HASH')
    bases, raw_tables, provenance = {}, {}, {}
    diffs = []
    for name in ('BY2','BY2H','BY2O'):
        seq = load_sequence_paths(name, local_config=local_config,
            registry_path=code/REGISTRY, calibrated_contract_path=code/CALIBRATED_CONTRACT)
        _checked(dict(path=str(seq.hash_lock), sha256=seq.hash_lock_sha256), resolve)
        lock = {r['relative_path']:r['sha256'] for r in csv.DictReader(seq.hash_lock.open())}
        sources = []
        for p in (seq.gnss1_raw, seq.gnss2_raw):
            pin = dict(path=str(p), sha256=lock[p.relative_to(seq.raw_root).as_posix()])
            _checked(pin, resolve); sources.append(pin)
        first, second = (decode_receiver(Path(p['path']))[0] for p in sources)
        keys = sorted(set(first)&set(second))
        origin = np.asarray(first[keys[0]]['ecef_m'])
        rotation = fixed_ecef_to_ned_rotation(origin)
        positions = [np.array([rotation@(np.asarray(receiver[k]['ecef_m'])-origin) for k in keys]) for receiver in (first, second)]
        rows, adapter = raw_yaw_from_ned(*positions, itow_ms=keys, gps_week=2408, base_time=seq.base_time,
            adapter_root=out/name/'RAW_ADAPTER')
        flags = [hp.pvt_flags_from_csv_bytes(Path(p['path']).read_bytes(), expected_sha256=p['sha256']) for p in sources]
        base_pin = source_index['base_gnss'][name]
        frozen = _checked(base_pin, resolve).read_bytes()
        tables, audit, diagnostic = build_t5a_variants(frozen, expected_sha256=base_pin['sha256'],
            gps_week=2408, base_time=seq.base_time, raw_yaw_rows=rows, pvt_flags1=flags[0], pvt_flags2=flags[1],
            sequence=name, window=seq.window, variants=['R5'])
        gate = byte_gate(frozen,tables['R5'])
        if digest(tables['R5']) != references[name]['sha256']:
            raise ValueError('HARD_STOP_V3_T5AR_'+name+'_TABLE_HASH')
        target = out/name/'R5.gnss'
        with target.open('xb') as stream:
            stream.write(tables['R5'])
        bases[name] = frozen; raw_tables[name] = tables['R5']
        provenance[name] = dict(raw_source_hashes=sources, base_gnss=base_pin,
            adapter=adapter, t5a_audit=audit, data_mode='real_raw', **FLAGS,
            code_commit=code_freeze, config_hash=contract['config_hash'], provider_hashes={'gnsspath':digest(tables['R5'])})
        write_json(out/name/'BASE_MANIFEST.json', {**provenance[name], 'byte_gate':gate})
        diffs += [dict(provider_key=name+':C00_BASE', column_1based=i+1, changed_tokens=n,
            byte_identity_required=i not in (YAW,VALID), passed=i in (YAW,VALID) or n==0) for i,n in enumerate(gate['changed_tokens_by_column'])]
    result = {}
    for spec in registry:
        provider_key = spec['provider_key']
        if provider_key in result:
            continue
        name, case = spec['sequence_id'], spec['case_id']
        pin = spec['frozen_providers']['gnsspath']
        template = _checked(pin,resolve).read_bytes()
        type_id = spec.get('degradation_type_id') or (spec.get('case_meta') or {}).get('degradation_type_id','CLEAN')
        if name != 'BY2' or case == 'C00_clean_normal':
            type_id = 'CLEAN'
        fault_rows, components, anchor = [], [], None
        if type_id != 'CLEAN':
            bundle_pin = source_index['case_bundles'][case]
            bundle = json.loads(_checked(bundle_pin,resolve).read_text())
            seal = json.loads(_checked(source_index['provider_seals'][case],resolve).read_text())
            if seal['status'] != 'SEALED' or seal['files_sha256']['PROVIDER_BUNDLE.json'] != bundle_pin['sha256']:
                raise ValueError('HARD_STOP_V3_FROZEN_PROVIDER_SEAL')
            components = bundle['components']
            anchor = bundle['case_meta'].get('anchor_time_s')
            if type_id in PERTURBED | CELL_DROPOUT:
                audit_pin = bundle.get('audit_payloads',{}).get('dual_yaw')
                if audit_pin:
                    fault_rows = list(csv.DictReader(_checked(audit_pin,resolve).open()))
                else:
                    raise ValueError('HARD_STOP_V3_MISSING_FROZEN_HEADING_AUDIT:'+case)
        payload, gate = lift_heading(template,raw_tables[name],bases[name],type_id=type_id,
            fault_rows=fault_rows,components=components,base_time=spec['evaluation']['base_time'],anchor_time_s=anchor)
        folder = out/'CASES'/provider_key.replace(':','__')
        folder.mkdir(parents=True)
        target = folder/'GNSS18.gnss'
        with target.open('xb') as stream:
            stream.write(payload)
        record = dict(path=str(target),sha256=digest(payload),byte_gate=gate,
            data_mode='real_raw' if type_id=='CLEAN' else 'semisynthetic',
            **{**FLAGS,'semisynthetic_data_used':type_id!='CLEAN'},
            raw_source_hashes=provenance[name]['raw_source_hashes'],
            frozen_gnss=pin, code_commit=code_freeze,config_hash=contract['config_hash'],
            provider_hashes={**{k:p['sha256'] for k,p in spec['frozen_providers'].items()},'gnsspath':digest(payload)})
        write_json(folder/'PROVIDER_MANIFEST.json',record)
        result[provider_key]=record
        diffs += [dict(provider_key=provider_key,column_1based=i+1,changed_tokens=n,
            byte_identity_required=i not in (YAW,VALID),passed=i in (YAW,VALID) or n==0) for i,n in enumerate(gate['changed_tokens_by_column'])]
    with (out/'COLUMN_DIFF.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(diffs[0]));writer.writeheader();writer.writerows(diffs)
    write_json(out/'PROVIDER_REGISTRY.json',result)
    write_json(out/'GATES_2A_2B.json',dict(status='PASS',gate_2a='PASS',gate_2b='PASS',
        providers=len(result),code_freeze=code_freeze,three_sequence_sha256={s:digest(p) for s,p in raw_tables.items()},
        t5a_handoff=archive_pin,by2_handoff_member_sha256=digest(member)))
    return result
