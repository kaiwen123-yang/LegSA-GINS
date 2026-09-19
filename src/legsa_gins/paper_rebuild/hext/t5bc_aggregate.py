"""Persist T5bc reports from pinned comparators and sealed run outputs only.

No raw observation, reference trace, solver, or evaluator is opened or invoked.
Input checks precede exclusive output creation; original CSV tokens are retained
in FROZEN_SOURCE_ROWS.json alongside the report's explicit role annotations.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from . import t5bc_reporting as report
from . import t5bc_runtime as runtime
from .aggregate import H03_PRIMARY_STARTS, _write_csv
from .t5bc_calibration import calibration_bin_report
from .t5bc_preparation import _document


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


class PinnedInputs:
    def __init__(self, ctx):
        self.ctx = ctx
        self.hashes = {}

    def alias(self, value):
        roots = {**self.ctx.roots, 't5bc_scratch': self.ctx.scratch}
        if isinstance(value, str):
            for key, path in sorted(roots.items(), key=lambda item: -len(str(item[1]))):
                value = value.replace(str(path), '<'+key.upper()+'>')
            return value
        if isinstance(value, dict):
            return {self.alias(key): self.alias(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.alias(item) for item in value]
        return value

    def read(self, ref):
        path = runtime._safe(ref['path'])
        if not any(runtime._within(path, runtime._safe(root)) for root in
                   (self.ctx.scratch, self.ctx.roots['clean_root'], self.ctx.roots['code_root'])):
            raise ValueError('Aggregation input outside scratch/clean/code roots')
        if (runtime._within(path, runtime._safe(self.ctx.roots['raw_root']))
                or path.name.lower().startswith('trace_') or path.suffix.lower() in ('.bag','.fpl','.nav','.imu','.gnss')):
            raise PermissionError('Aggregation cannot read raw data, reference traces, NAV or provider payloads')
        payload = path.read_bytes()
        if _sha(payload) != ref['sha256']:
            raise RuntimeError('HARD_STOP_T5BC_AGGREGATE_INPUT_HASH: '+str(path))
        key = str(path)
        if key in self.hashes and self.hashes[key] != ref['sha256']:
            raise RuntimeError('Conflicting aggregation source pin')
        self.hashes[key] = ref['sha256']
        return payload

    def document(self, ref):
        return json.loads(self.read(ref))

    def csv(self, ref):
        payload = self.read(ref)
        if str(ref['path']).endswith('.gz'):
            payload = gzip.decompress(payload)
        return list(enumerate(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))), 2))

    def terminal(self, reference, root, filename):
        if hasattr(self.ctx, 'read_terminal'):
            # Explicit T5bc-R registry checks old/new freezes and report-only D57.
            record = self.ctx.read_terminal(reference, root, filename)
            self.read(reference)
            return record
        if runtime._safe(reference['path']) != root / filename:
            raise ValueError('Sealed terminal occupies an unexpected slot')
        record = self.document(reference)
        if record.get('status') == 'HARD_STOP' or (root/'HARD_STOP.json').exists():
            raise RuntimeError('Hard-stop result cannot enter T5bc aggregation')
        files = record['file_hashes']
        seal = self.document(dict(path=str(root/'OUTPUT_SEAL.json'), sha256=files['OUTPUT_SEAL.json']))
        if seal.get('status') != 'SEALED' or seal['files'] != {k:v for k,v in files.items() if k != 'OUTPUT_SEAL.json'}:
            raise RuntimeError('Sealed terminal file inventory differs')
        for name in files:
            if not runtime._within(runtime._safe(root/name), root):
                raise ValueError('Sealed member escapes run output root')
        return record

    def frame(self, root, record, name):
        """Read only exact sealed CSV names; dual exports must be byte equal."""
        candidates = [candidate for candidate in (name, name+'.gz') if candidate in record['file_hashes']]
        if not candidates:
            return None
        payloads = []
        for candidate in candidates:
            payload = self.read(dict(path=str(root/candidate), sha256=record['file_hashes'][candidate]))
            payloads.append(gzip.decompress(payload) if candidate.endswith('.gz') else payload)
        if len(payloads) == 2 and payloads[0] != payloads[1]:
            raise RuntimeError('Sealed plain/gzip CSV bytes disagree')
        return pd.read_csv(io.BytesIO(payloads[0]))

    def recheck(self):
        for path, digest in list(self.hashes.items()):
            self.read(dict(path=path, sha256=digest))


def _roles(rows, mode, *, source_table, overrides=None):
    result = []
    for line, original in rows:
        row = deepcopy(original)
        role = (overrides or {}).get(row.get('case_id', row.get('subset_case_id')),
                                     report._mode(mode))
        # Roles are explicit source-index metadata, not inferred from metrics.
        report._checked_role(original,role['data_mode'],csv_source=True)
        row.update(role)
        row['frozen_source_table'] = source_table
        result.append((line, row))
    return result


def _flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        label = prefix+key
        if isinstance(item, dict):
            result.update(_flatten(item, label+'_'))
        else:
            result[label] = item
    return result


def case_input_effects(ctx, case_ids):
    """Record original fault metadata and literal replacement policy, no inference."""
    rows=[]
    for case in case_ids:
        metadata=ctx.metadata[case]
        registry=metadata['source_registry_row']
        rows.append(dict(case_id=case,case_meta_json=deepcopy(metadata['case_meta']),
            source_registry_family_type_json={key:deepcopy(value) for key,value in registry.items()
                if 'family' in key.lower() or 'type' in key.lower()},
            original_metadata_source='Pinned frozen subset terminal, ctx.metadata[case]',
            retained_components='All non-yaw GNSS bytes and IMU/RD/RP/HV inputs are retained unchanged',
            replaced_components='yaw/yaw_std/yaw_valid are replaced by the newly prepared inputs',
            baseline3d_components='B3 uses the new baseline3d sidecar and scalar yaw_valid=0',
            original_heading_injection_preserved_claim=False,
            original_heading_injection_statement='No claim that the original heading injection is preserved',
            fault_presence_inferred=False,new_fault_injection_designed=False,
            d57_exact_time_join_without_repair=case=='D57_seed_00',
            time_policy='D57 exact-time join, unmatched valid=0; no timestamp repair or interpolation'
                if case=='D57_seed_00' else 'Original GNSS timestamps retained unchanged',
            **deepcopy(ctx.index['subset_sources'][case]['data_roles'])))
    return rows


def _frozen_native_binding(frozen, core, runtime_sources):
    """Same source NAV and registered core row, independent of metric values."""
    indexed = dict(core)
    for _, row in frozen:
        seq, profile = row['sequence_id'], row['method_id']
        source = runtime_sources[seq+'_'+profile]
        original = indexed.get(int(source['frozen_table_line']))
        if original is None or original.get('run_id') != source['frozen_run_id']:
            raise ValueError('Frozen horizontal/core registered row identity differs')
        if original.get('dataset_id',original.get('sequence_id')) != seq or original.get('method_id') != profile:
            raise ValueError('Frozen horizontal/core sequence or profile differs')
        nav = original.get('native_nav_sha256',original.get('source_nav_sha256'))
        if not isinstance(nav,str) or len(nav)!=64 or row.get('source_nav_sha256') != nav:
            raise ValueError('Frozen horizontal/core source NAV identity differs')


def calibration_tables(readers, summary):
    """Six sequence/lag rows; complete scalar/vector pair records stay separate."""
    scalars, vectors = {}, {}
    for ref in summary['pins']:
        name = Path(ref['path']).name
        if name not in ('SCALAR_CALIBRATION.json', 'VECTOR_CALIBRATION.json'):
            continue
        value = readers.document(ref)
        target = scalars if name.startswith('SCALAR') else vectors
        seq = value['sequence_id']
        if seq in target:
            raise ValueError('Duplicate calibration report pin')
        target[seq] = value
    if set(scalars) != set(report.SEQUENCES) or set(vectors) != set(scalars):
        raise ValueError('All three scalar/vector reports are required')
    rows, pairs = [], []
    for seq in report.SEQUENCES:
        for lag in (1000, 200):
            scalar = [r for r in scalars[seq]['reports'] if r['lag_ms'] == lag]
            vector = [r for r in vectors[seq]['reports'] if r['lag_ms'] == lag]
            if len(scalar) != 1 or len(vector) != 1:
                raise ValueError('Calibration lag identity changed')
            s, v = scalar[0], vector[0]
            row = dict(sequence_id=seq, lag_ms=lag, baseline_m=.35, applied_source_sequence='BY2',
                       primary_method='INSTALLED_GYRO_Z', user_denominator_factor=6,
                       sigma_deg=s['z'].get('sigma_deg', report.UNAVAILABLE),
                       k=s['z'].get('k', report.UNAVAILABLE), k_b=v.get('k_b', report.UNAVAILABLE),
                       scalar_status=s['status'], vector_status=v['status'],
                       **report._mode(scalars[seq]['data_mode']))
            row.update(_flatten(s, 'scalar_')); row.update(_flatten(v, 'vector_'))
            row.update(_flatten(summary['selections'][seq], 'applied_'))
            rows.append(row)
        for family, source in (('scalar', scalars[seq]), ('vector', vectors[seq])):
            pairs.extend(dict(sequence_id=seq, family=family, **pair) for pair in source['pairs'])
    bins = []
    for lag in (1000, 200):
        diagnostic = calibration_bin_report(scalars, vectors, lag_ms=lag)
        bins.extend(dict(boundary_policy=diagnostic['boundary_policy'], **row) for row in diagnostic['rows'])
    return rows, pairs, bins


def aggregate_t5bc(ctx, *, contract=None, execution_summary_ref=None):
    """Persist reports into a new 07_AGGREGATE; never launch or resume science."""
    scratch = runtime._safe(ctx.scratch)
    if scratch.name != runtime.STAGE or any(runtime._within(scratch, runtime._safe(ctx.roots[k]))
            for k in ('raw_root', 'clean_root', 'code_root')):
        raise ValueError('Aggregation requires independent registered scratch')
    output = scratch/'07_AGGREGATE'
    if output.exists():
        raise FileExistsError('Existing aggregate evidence is never overwritten')
    contract = contract if contract is not None else ctx.registered(prepared=True)
    inputs = PinnedInputs(ctx)
    summary_path = getattr(ctx, 'execution_summary_path', scratch/'09_HANDOFF/EXECUTION/FINAL_EXECUTION_SUMMARY.json')
    if execution_summary_ref is None:
        execution_summary_ref = dict(path=str(summary_path), sha256=runtime.sha256_file(summary_path))
    if runtime._safe(execution_summary_ref['path']) != summary_path:
        raise ValueError('Execution summary is not the registered scratch terminal')
    summary = inputs.document(execution_summary_ref)
    if summary.get('status') not in ('COMPLETE_REGISTERED_EXECUTION', 'COMPLETE_REGISTERED_EXECUTION_ARCHIVE_PENDING'):
        raise RuntimeError('Complete registered execution required for aggregate persistence')
    if summary['code_freeze'] != ctx.freeze or summary['contract_sha256'] != runtime.scientific_contract_sha256(contract):
        raise RuntimeError('Execution code-freeze/contract mismatch')
    specs = contract['registered_runs']
    matrix = {key:spec for key,spec in specs.items() if spec['variant'] != 'IDENTITY'}
    if set(summary['native_terminals']) != set(specs) or set(summary['evaluation_terminals']) != {
            key+'__'+version for key in matrix for version in ('v3','v2')}:
        raise ValueError('Execution terminal matrix is incomplete or contains extra slots')
    native, evaluations = {}, {'v3':[], 'v2':[]}
    gating, nis, nis_series, new_segments = [], [], [], {'v3':[], 'v2':[]}
    for run_id, spec in matrix.items():
        root = scratch/runtime._native_relative(spec)
        record = inputs.terminal(summary['native_terminals'][run_id], root, 'T5BC_NATIVE_SUMMARY.json')
        if (any(record[k] != spec[k] for k in runtime.IDENTITY_KEYS) or
                (not hasattr(ctx, 'read_terminal') and (record['code_commit'] != ctx.freeze
                or record['contract_sha256'] != summary['contract_sha256']))):
            raise ValueError('Native identity differs from registered run')
        native[run_id] = record
        identity = {**{k:spec[k] for k in runtime.IDENTITY_KEYS}, **{k:record[k] for k in
                    ('data_mode','synthetic_data_used','semisynthetic_data_used')}}
        identity.update(native_status=record['status'],native_failure_classification=record.get('failure_classification','NONE'))
        window = ctx.contexts[spec['sequence_id']].window
        b3 = inputs.frame(root,record,'BASELINE3D_DIAGNOSTICS.csv') if spec['variant']=='B3' else None
        log = inputs.frame(root,record,'PORT_GNSS_UPDATE_TRACE.csv') if spec['variant']!='B3' else None
        rows = report.gating_nis_rows(log,identity=identity,window=window,
                                      source=inputs.alias(str(root)),baseline3d=b3)
        gating.extend(rows)
        source = b3 if spec['variant']=='B3' else inputs.frame(root,record,'SOURCE_AWARE_WEIGHT_TRACE.csv')
        nrows, series = report.nis_consistency(source,identity=identity,window=window,
                                  attempts={r['segment_id']:r['attempted'] for r in rows})
        nis.extend(nrows)
        if spec['subset_case_id'] is None and spec['configuration_id']=='F04' and spec['variant'] in ('R5W','B3'):
            nis_series.extend(series)
        for version in ('v3','v2'):
            eroot = scratch/'06_EVAL'/version/run_id
            ev = inputs.terminal(summary['evaluation_terminals'][run_id+'__'+version], eroot,
                                  'T5BC_EVALUATION_SUMMARY.json')
            if (ev['native_summary'] != summary['native_terminals'][run_id] or
                    (not hasattr(ctx, 'read_terminal') and (ev['code_commit'] != ctx.freeze
                    or ev['contract_sha256'] != summary['contract_sha256']))):
                raise ValueError('Evaluator native/code-freeze binding differs')
            if any(ev['row'][k] != spec[k] for k in runtime.IDENTITY_KEYS) or ev['row']['evaluator_contract'] != 'evaluator_contract_'+version:
                raise ValueError('Evaluator row identity differs')
            evaluations[version].append(ev)
            if spec['sequence_id']=='BY2O' and spec['subset_case_id'] is None:
                status = ev['row']['evaluation_status']
                errors = inputs.frame(eroot,ev,'FROZEN_EVALUATOR/error_series.csv') if status in report.AVAILABLE else None
                if status in report.AVAILABLE and errors is None:
                    raise ValueError('Admitted BY2O evaluator lacks sealed full-rate errors')
                new_segments[version].extend(report.derive_by2o_segments(errors,profile=spec['configuration_id'],
                    variant=spec['variant'],version=version,window=window,source=inputs.alias(str(eroot)),
                    evaluation_status=status,data_mode=record['data_mode']))
    tables, original_rows, pilots, subset_all, segments = {}, {}, {}, {}, []
    modes = {r['data_mode'] for key,r in native.items() if matrix[key]['subset_case_id'] is None}
    if len(modes)!=1 or not modes <= {'real_raw','synthetic'}:
        raise ValueError('Sequence pilot data modes must be uniform and explicit')
    pilot_mode = next(iter(modes))
    cases = tuple(contract['matrix']['subset']['case_ids'])
    effects=case_input_effects(ctx,cases)
    for version in ('v3','v2'):
        horizontal_ref = ctx.index['hext04l']['HORIZONTAL_TABLE_'+version.upper()+'_THREE_SEQUENCES.csv']
        horizontal = inputs.csv(horizontal_ref)
        original_rows['horizontal_'+version] = horizontal
        rows = _roles(horizontal,pilot_mode,source_table=inputs.alias(horizontal_ref['path']))
        frozen = [(n,r) for n,r in rows if r.get('method_id') in report.PROFILES and r.get('start_convention') == report.FROZEN]
        core_ref=ctx.index['sequence_tables'][version]
        original_rows['core_sequence_'+version] = inputs.csv(core_ref)
        _frozen_native_binding(frozen,original_rows['core_sequence_'+version],ctx.index['runtime_sources'])
        literature = [(n,r) for n,r in rows if r.get('method_id') in ('LC01','LC01-S') and
                       r.get('start_convention') == H03_PRIMARY_STARTS[r['sequence_id']]]
        t5a_ref = ctx.index['t5a_r']['tables']['SENSITIVITY_TABLE_'+version.upper()+'.csv']
        t5a = inputs.csv(t5a_ref); original_rows['t5a_'+version] = t5a
        pilot = report.pilot_rows(frozen,_roles(t5a,pilot_mode,source_table=inputs.alias(t5a_ref['path'])),
            [v for v in evaluations[version] if v['row']['subset_case_id'] is None],literature,version=version,data_mode=pilot_mode)
        for row in pilot:
            matches = [n for n in nis if n['subset_case_id'] is None and n['sequence_id']==row['sequence_id'] and
                       n['configuration_id']==row['configuration_id'] and n['variant']==row['variant'] and n['segment_id']=='full']
            if len(matches)==1:
                for key in ('nis_mean','nis_coverage_95','nis_selection_coverage'):
                    row[key] = matches[0].get(key,report.UNAVAILABLE)
        pilots[version] = pilot
        tables['PILOT_TABLE_'+version.upper()+'.csv'] = pilot
        source = ctx.index['subset_tables'][version]
        frozen_subset = inputs.csv(source); original_rows['subset_'+version] = frozen_subset
        overrides = {case:ctx.index['subset_sources'][case]['data_roles'] for case in cases}
        selected_subset = [(line,row) for line,row in frozen_subset
            if row.get('case_id',row.get('subset_case_id')) in cases and report._profile(row)=='F04'
            and row.get('evaluator_contract')=='evaluator_contract_'+version]
        subset, pending = report.subset_rows(_roles(selected_subset,'semisynthetic',source_table=inputs.alias(source['path']),overrides=overrides),
            [v for v in evaluations[version] if v['row']['subset_case_id'] is not None],case_ids=cases,version=version,
            case_data_modes={case:role['data_mode'] for case,role in overrides.items()})
        if pending: raise ValueError('No pending cases exist in the authorized all-61 matrix')
        for row in subset:
            row.update(heading_columns_replaced_by_design=row['variant'] != report.FROZEN,
                case_input_effects_source=inputs.alias(str(output/'CASE_INPUT_EFFECTS.csv')),
                case_input_effects_case_id=row['case_id'])
        subset_all[version] = subset
        tables['SUBSET61_TABLE_'+version.upper()+'.csv'] = subset
        segment_ref = ctx.index['hext04l']['hext04l_segments']
        frozen_segments = inputs.csv(segment_ref); original_rows['hext04l_segments'] = frozen_segments
        t5a_segment_ref = ctx.index['t5a_r']['tables']['BY2O_SEGMENTS_BY_VARIANT.csv']
        t5a_segments = inputs.csv(t5a_segment_ref); original_rows['t5a_segments'] = t5a_segments
        segments.extend(report.by2o_segment_rows(
            _roles(frozen_segments,pilot_mode,source_table=inputs.alias(segment_ref['path'])),
            _roles(t5a_segments,pilot_mode,source_table=inputs.alias(t5a_segment_ref['path'])),
            new_segments[version],version=version,data_mode=pilot_mode))
    calibration = ctx._verified_calibration()
    calibration_ref = dict(path=str(scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json'),
                          sha256=runtime.sha256_file(scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json'))
    if inputs.document(calibration_ref) != calibration:
        raise ValueError('Calibration summary changed during aggregation')
    crows, pairs, bins = calibration_tables(inputs,calibration)
    tables.update({'CALIBRATION_SUMMARY.csv':crows,'CALIBRATION_PAIRS.csv':pairs,'S3_CALIBRATION_BINS.csv':bins,
        'CASE_INPUT_EFFECTS.csv':effects,
        'LC01_CROSSCHECK.csv':[row for version in ('v3','v2') for row in report.lc01_crosscheck(pilots[version])],
        'SUBSET61_SUMMARY.csv':report.subset_absolute_summary(subset_all['v3'],case_ids=cases),
        'SUBSET61_PAIRED_DISTRIBUTIONS.csv':report.subset_distributions(subset_all['v3'],case_ids=cases),
        'BY2O_SEGMENTS_BY_VARIANT.csv':segments,'GATING_COUNTS.csv':gating,'NIS_CONSISTENCY.csv':nis,
        'NIS_SERIES.csv':nis_series,'ATTITUDE.csv':[r for version in ('v3','v2') for r in report.attitude_rows(pilots[version])]})
    inputs.recheck()
    output.mkdir(parents=True,exist_ok=False)
    for name,rows in tables.items():
        fields = ('sequence_id','configuration_id','variant','run_id','subset_case_id','data_mode',
                  'synthetic_data_used','semisynthetic_data_used','native_status','native_failure_classification',
                  'time','nis','dof') if name=='NIS_SERIES.csv' else None
        _write_csv(output/name,inputs.alias(rows),fields=fields)
    _document(output/'FROZEN_SOURCE_ROWS.json',dict(original_csv_rows=original_rows,
        data_role_overrides=ctx.index['subset_sources'],unchanged_csv_tokens=True))
    files = {p.name:runtime.sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()}
    manifest = dict(status='PASS_T5BC_AGGREGATE',code_commit=ctx.freeze,
        contract_sha256=summary['contract_sha256'],execution_summary=inputs.alias(execution_summary_ref),
        data_mode=summary['data_mode'],synthetic_data_used=summary['synthetic_data_used'],
        semisynthetic_data_used=summary['semisynthetic_data_used'],subset_case_ids=list(cases),
        files_sha256=files,row_counts={name:len(rows) for name,rows in tables.items()},
        input_sha256=inputs.alias(inputs.hashes),trace_payload_reads=0,native_invocations=0,evaluator_invocations=0,
        main_chain_replaced=False,full_subset_metrics_preserved=True,
        nis_series_scope='Formal sequence F04 R5W/B3 only; actual covariance diagnostics',
        calibration_primary='Installed gyro-z; vector user denominator factor 6; L=.35; BY2 applied uniformly')
    inputs.recheck()
    return _document(output/'AGGREGATE_MANIFEST.json',manifest)
