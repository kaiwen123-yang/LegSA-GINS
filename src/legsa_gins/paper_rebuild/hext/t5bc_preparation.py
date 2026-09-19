"""Pinned, trace-free T5bc input preparation; no solver or evaluator calls.

Scientific choices are caller inputs. This module cannot select a subset,
decide a vector calibration convention, or infer cross-sequence calibration.
All writes are exclusive and confined to explicitly supplied new directories.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import heading_provider as hp
from .t5bc_calibration import (scalar_pair_calibration, vector_pair_calibration,
                               calibration_bin_report, BASELINE_M, PAIR_POLICY)
from .t5bc_provider import (raw_yaw_from_ned, prepare_heading_weights,
                           build_heading_variants, build_baseline3d_sidecar,
                           build_baseline3d_gnss, prepared_raw_rows)
from .t5bc_runtime import _safe, _within, _pin, _json, STAGE
from ..clean5_parity.input_audit import decode_receiver
from ..horizontal_literature.ext05_provider import fixed_ecef_to_ned_rotation
from ..manifest import sha256_file

CONVERTER_RELATIVE = 'src/legsa_gins/input_generation/status_yaw_builder.py'
CONVERTER_SHA256 = '4435dd71593b1447152986ab91e2fe0394177470791a4c09815a851b75504193'


def _write(path, payload):
    with _safe(path).open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}


def _document(path, value):
    return _write(path, (_json(value) + '\n').encode('utf-8'))


def _reference(reference, root):
    path = _safe(reference['path'])
    if not _within(path, _safe(root)):
        raise ValueError('Input reference is outside its declared immutable root')
    _pin(reference)
    return path


def _output(output_root, scratch_root, relative):
    root, scratch = _safe(output_root), _safe(scratch_root)
    if scratch.name != STAGE or root != scratch / relative:
        raise ValueError('Preparation output must occupy its exact T5bc scratch slot')
    if root.exists():
        raise FileExistsError('Existing preparation evidence is never overwritten')
    return root


def _scratch(sequence, scratch_root):
    scratch = _safe(scratch_root)
    if scratch.name != STAGE or any(_within(scratch, _safe(root)) for root in
            (sequence.raw_root, sequence.clean_root, sequence.code_root)):
        raise ValueError('Preparation requires independent scratch storage outside protected roots')
    return scratch


def decode_observations(sequence, *, scratch_root, output_root):
    """Decode only the two hash-locked raw CSVs, never a reference trace.

    The fixed-frame origin and unchanged A1 adapter are exactly the T5a R5
    construction. Accuracy comes separately from decoded HPPOSECEF pAcc.
    """
    scratch = _scratch(sequence, scratch_root)
    root = _output(output_root, scratch, f'01_CALIBRATION/{sequence.sequence_id}/RAW_OBSERVATIONS')
    converter = {'path': str(_safe(sequence.code_root) / CONVERTER_RELATIVE),
                 'sha256': CONVERTER_SHA256}
    _pin(converter)
    lock = {'path': str(sequence.hash_lock), 'sha256': sequence.hash_lock_sha256}
    lock_path = _reference(lock, sequence.clean_root)
    records = list(csv.DictReader(io.StringIO(lock_path.read_text(encoding='utf-8-sig'))))
    index = {}
    for record in records:
        name = record['relative_path']
        if name in index:
            raise ValueError('Duplicate immutable raw lock identity')
        index[name] = record['sha256']
    references = []
    for path in (sequence.gnss1_raw, sequence.gnss2_raw):
        path = _safe(path)
        if path.name not in ('gnss1-raw.csv', 'gnss2-raw.csv'):
            raise ValueError('Only the two receiver raw CSVs are admitted here')
        relative = path.relative_to(sequence.raw_root).as_posix()
        reference = {'path': str(path), 'sha256': index[relative]}
        _reference(reference, sequence.raw_root)
        references.append(reference)
    first, second = (decode_receiver(Path(ref['path']))[0] for ref in references)
    keys = sorted(first.keys() & second.keys())
    if not keys:
        raise ValueError('No simultaneous HPPOSECEF observations')
    origin = np.asarray(first[keys[0]]['ecef_m'], float)
    rotation = fixed_ecef_to_ned_rotation(origin)
    positions = [np.asarray([rotation @ (np.asarray(receiver[key]['ecef_m']) - origin)
                            for key in keys]) for receiver in (first, second)]
    flags = [hp.pvt_flags_from_csv_bytes(Path(ref['path']).read_bytes(),
                                       expected_sha256=ref['sha256']) for ref in references]
    root.mkdir(parents=True, exist_ok=False)
    raw_yaw, adapter = raw_yaw_from_ned(*positions, itow_ms=keys, gps_week=2408,
                                      base_time=sequence.base_time, adapter_root=root / 'A1_ADAPTER')
    observations = dict(sequence_id=sequence.sequence_id, baseline_m=BASELINE_M,
                        raw_yaw_rows=raw_yaw,
                        pacc1_m={key: row['pAcc_m'] for key, row in first.items()},
                        pacc2_m={key: row['pAcc_m'] for key, row in second.items()},
                        pvt_flags1=flags[0], pvt_flags2=flags[1])
    for reference in (*references, lock, converter):
        _pin(reference)
    manifest = dict(status='PREPARED_OBSERVATIONS_NO_EXECUTION', data_mode='real_raw',
                    synthetic_data_used=False, semisynthetic_data_used=False,
                    trace_used_online=False, native_invocations=0, evaluator_invocations=0,
                    trace_open_count=0, raw_source_hashes=references, raw_lock=lock,
                    frozen_heading_conversion=converter,
                    origin_ecef_m=origin.tolist(), ecef_to_ned=rotation.tolist(),
                    adapter=adapter, raw_common_epoch_count=len(keys),
                    pacc_units='m', pacc_source='HPPOSECEF_PACC_0P1MM_TIMES_1E_MINUS_4',
                    files={p.relative_to(root).as_posix(): sha256_file(p)
                           for p in sorted(root.rglob('*')) if p.is_file()})
    pin = _document(root / 'OBSERVATION_MANIFEST.json', manifest)
    observations['observation_manifest'] = pin
    observations['raw_source_hashes'] = {r['path']: r['sha256'] for r in references}
    return observations, pin


def calibrate_scalar(sequence, observations, *, imu_reference, rp_reference,
                     scratch_root, output_root, denominator_policy):
    """Report both lags, installed gyro-z primary and Euler projection report only."""
    if observations['sequence_id'] != sequence.sequence_id:
        raise ValueError('Observation sequence mismatch')
    scratch = _scratch(sequence, scratch_root)
    root = _output(output_root, scratch, f'01_CALIBRATION/{sequence.sequence_id}/SCALAR')
    imu_path = _reference(imu_reference, sequence.clean_root)
    rp_path = _reference(rp_reference, sequence.clean_root)
    imu = np.loadtxt(imu_path)
    rp = pd.read_csv(rp_path)[['time', 'roll_rad', 'pitch_rad']].to_numpy(float)
    selected = {key: observations[key] for key in
                ('raw_yaw_rows', 'pacc1_m', 'pacc2_m', 'pvt_flags1', 'pvt_flags2')}
    report = scalar_pair_calibration(**selected, baseline_m=BASELINE_M,
                                    imu=imu, rp=rp, window=sequence.window,
                                    nominal_variance_policy=denominator_policy)
    _pin(imu_reference)
    _pin(rp_reference)
    report.update(sequence_id=sequence.sequence_id, data_mode='real_raw', synthetic_data_used=False,
                  semisynthetic_data_used=False, immutable_inputs=[imu_reference, rp_reference],
                  trace_used_online=False, native_invocations=0, evaluator_invocations=0,
                  observation_manifest=observations.get('observation_manifest'),
                  raw_source_hashes=observations.get('raw_source_hashes', {}),
                  applied_cross_sequence=False, primary_method='INSTALLED_GYRO_Z')
    root.mkdir(parents=True, exist_ok=False)
    pin = _document(root / 'SCALAR_CALIBRATION.json', report)
    return report, pin


def calibrate_vector(sequence, observations, *, imu_reference, rp_reference,
                     scratch_root, output_root):
    """Persist D3 vector calibration, with exact user denominator factor six."""
    if observations['sequence_id'] != sequence.sequence_id:
        raise ValueError('Observation sequence mismatch')
    scratch = _scratch(sequence, scratch_root)
    root = _output(output_root, scratch, f'01_CALIBRATION/{sequence.sequence_id}/VECTOR')
    imu_path, rp_path = (_reference(r, sequence.clean_root) for r in (imu_reference, rp_reference))
    selected = {key: observations[key] for key in
                ('raw_yaw_rows', 'pacc1_m', 'pacc2_m', 'pvt_flags1', 'pvt_flags2')}
    report = vector_pair_calibration(**selected, baseline_m=BASELINE_M, imu=np.loadtxt(imu_path),
        rp=pd.read_csv(rp_path)[['time', 'roll_rad', 'pitch_rad']].to_numpy(float), window=sequence.window)
    for reference in (imu_reference, rp_reference): _pin(reference)
    report.update(sequence_id=sequence.sequence_id, data_mode='real_raw', synthetic_data_used=False,
        semisynthetic_data_used=False, immutable_inputs=[imu_reference, rp_reference],
        observation_manifest=observations.get('observation_manifest'), raw_source_hashes=observations.get('raw_source_hashes', {}),
        trace_used_online=False, native_invocations=0, evaluator_invocations=0)
    root.mkdir(parents=True, exist_ok=False)
    return report, _document(root / 'VECTOR_CALIBRATION.json', report)


def select_scalar_calibration(reports, *, sigma_application='BY2_UNIFIED'):
    """Apply BY2 1 s gyro-z sigma/k unchanged to all sequences and all cases."""
    if sigma_application != 'BY2_UNIFIED':
        raise ValueError('Explicit R5sigma application must be BY2_UNIFIED')
    if set(reports) != {'BY2', 'BY2H', 'BY2O'}:
        raise ValueError('All three scalar calibration reports are required')
    primary = {}
    for sequence, report in reports.items():
        if report.get('sequence_id') != sequence:
            raise ValueError('Scalar calibration report identity mismatch')
        rows = [row for row in report['reports'] if row['lag_ms'] == 1000]
        if len(rows) != 1 or sequence == 'BY2' and rows[0]['status'] != 'AVAILABLE':
            raise ValueError('Primary scalar calibration unavailable; no fallback is allowed')
        if report.get('primary_method') != 'INSTALLED_GYRO_Z':
            raise ValueError('Scalar primary must use installed gyro-z')
        primary[sequence] = rows[0].get('z', {})
    return {sequence: dict(k=primary['BY2']['k'], k_source_sequence='BY2',
                           sigma_deg=primary['BY2']['sigma_deg'], sigma_source_sequence='BY2',
                           sigma_application=sigma_application, calibration_lag_ms=1000,
                           primary_method='INSTALLED_GYRO_Z', baseline_m=BASELINE_M)
            for sequence in reports}


def select_vector_calibration(reports):
    if set(reports) != {'BY2', 'BY2H', 'BY2O'}:
        raise ValueError('All three vector calibration reports are required')
    for sequence, report in reports.items():
        if report.get('sequence_id') != sequence or report.get('user_denominator_factor') != 6:
            raise ValueError('Vector calibration sequence/factor identity mismatch')
    rows = [r for r in reports['BY2']['reports'] if r['lag_ms'] == 1000]
    if len(rows) != 1 or rows[0]['status'] != 'AVAILABLE':
        raise ValueError('BY2 primary vector calibration unavailable; no fallback')
    return {sequence: dict(k_b=rows[0]['k_b'], k_b_source_sequence='BY2',
        calibration_lag_ms=1000, baseline_m=BASELINE_M, user_denominator_factor=6) for sequence in reports}


def write_provider_bundle(sequence, observations, selection, *, frozen_gnss, r5_reference,
                          output_root, scratch_root, data_mode, subset_case_id=None,
                          f04_yaw_std_min_deg, allow_unmatched_times=False):
    """Replace original yaw faults with D2, without inventing vector faults."""
    if observations['sequence_id'] != sequence.sequence_id:
        raise ValueError('Observation sequence mismatch')
    if subset_case_id is not None:
        import re
        if sequence.sequence_id != 'BY2' or not re.fullmatch(r'[A-Za-z0-9_-]+', subset_case_id):
            raise ValueError('Invalid BY2 subset identity')
    relative = ('03_PROVIDER_TABLES/' + sequence.sequence_id if subset_case_id is None else
                '03_PROVIDER_TABLES/SUBSET61/' + subset_case_id)
    scratch = _scratch(sequence, scratch_root)
    root = _output(output_root, scratch, relative)
    if data_mode not in ('real_raw', 'real_clean', 'semisynthetic', 'synthetic') or subset_case_id is None and data_mode in ('semisynthetic', 'real_clean'):
        raise ValueError('Injected cases cannot be placed in real sequence slots')
    if data_mode == 'real_clean' and subset_case_id != 'C00_clean_normal':
        raise ValueError('Only the frozen C00 subset has the real_clean data role')
    if (selection.get('k_source_sequence') != 'BY2' or selection.get('calibration_lag_ms') != 1000
            or selection.get('sigma_application') != 'BY2_UNIFIED'
            or selection.get('sigma_source_sequence') != 'BY2'
            or selection.get('primary_method') != 'INSTALLED_GYRO_Z'):
        raise ValueError('Unresolved or inconsistent calibration application')
    base_path, r5_path = (_reference(ref, sequence.clean_root) for ref in (frozen_gnss, r5_reference))
    base_bytes, r5_bytes = base_path.read_bytes(), r5_path.read_bytes()
    values = {key: observations[key] for key in
              ('raw_yaw_rows', 'pacc1_m', 'pacc2_m', 'pvt_flags1', 'pvt_flags2')}
    weights = prepare_heading_weights(**values, baseline_m=BASELINE_M,
                                      k=selection['k'], sigma_deg=selection['sigma_deg'])
    tables, audit = build_heading_variants(base_bytes, expected_sha256=frozen_gnss['sha256'],
        gps_week=2408, base_time=sequence.base_time, weights=weights, r5_reference_bytes=r5_bytes,
        r5_reference_sha256=r5_reference['sha256'], window=sequence.window, data_mode=data_mode,
        f04_yaw_std_min_deg=f04_yaw_std_min_deg, allow_unmatched_times=allow_unmatched_times,
        subset_case_id=subset_case_id)
    prepared = prepared_raw_rows(base_bytes, expected_sha256=frozen_gnss['sha256'], gps_week=2408,
        base_time=sequence.base_time, weights=weights, r5_reference_bytes=r5_bytes,
        r5_reference_sha256=r5_reference['sha256'], allow_unmatched_times=allow_unmatched_times,
        subset_case_id=subset_case_id)
    sidecar, sidecar_audit = build_baseline3d_sidecar(base_bytes, expected_sha256=frozen_gnss['sha256'],
        gps_week=2408, base_time=sequence.base_time, weights=weights, data_mode=data_mode,
        prepared_rows=prepared, allow_unmatched_times=allow_unmatched_times, subset_case_id=subset_case_id)
    b3_gnss, b3_gnss_audit = build_baseline3d_gnss(base_bytes, expected_sha256=frozen_gnss['sha256'])
    root.mkdir(parents=True, exist_ok=False)
    prepared_manifest = dict(schema_version='t5bc.prepared_raw.v1', sequence_id=sequence.sequence_id,
        subset_case_id=subset_case_id, data_mode=data_mode, synthetic_data_used=data_mode == 'synthetic',
        semisynthetic_data_used=data_mode == 'semisynthetic', source_sha256=frozen_gnss['sha256'],
        pinned_r5_source=r5_reference, weights_sha256=weights.sha256, baseline_m=BASELINE_M,
        selection=selection, observation_manifest=observations.get('observation_manifest'),
        raw_source_hashes=observations.get('raw_source_hashes', {}), rows=prepared,
        allow_unmatched_times=allow_unmatched_times, time_roundtrip_tolerance_s=1e-6,
        interpolation_used=False, old_yaw_faults_replaced=True, invented_vector_faults=False)
    refs = {'prepared_raw_manifest': _document(root / 'PREPARED_RAW_MANIFEST.json', prepared_manifest)}
    for variant, payload in tables.items():
        (root / variant).mkdir()
        refs[variant] = _write(root / variant / 'GNSS18.txt', payload)
    (root / 'B3').mkdir()
    refs['B3_GNSS'] = _write(root / 'B3' / 'GNSS18.txt', b3_gnss)
    refs['B3'] = _write(root / 'B3' / 'baseline3d.csv', sidecar)
    for reference in (frozen_gnss, r5_reference):
        _pin(reference)
    manifest = dict(sequence_id=sequence.sequence_id, subset_case_id=subset_case_id, data_mode=data_mode,
                    synthetic_data_used=data_mode == 'synthetic', semisynthetic_data_used=data_mode == 'semisynthetic',
                    original_table=frozen_gnss, r5_reference=r5_reference,
                    selection=selection, weights_sha256=weights.sha256, baseline_m=BASELINE_M,
                    scalar_byte_gates=audit, baseline3d_audit=sidecar_audit, b3_gnss_byte_gate=b3_gnss_audit,
                    providers=refs, prepared_raw_manifest=refs['prepared_raw_manifest'],
                    native_invocations=0, evaluator_invocations=0, trace_open_count=0,
                    trace_used_online=False, per_case_tuning=False, output_only_correction=False,
                    epoch_deleted_for_metric=False, old_runtime_input_count=0)
    manifest_ref = _document(root / 'PROVIDER_MANIFEST.json', manifest)
    return refs, manifest_ref
