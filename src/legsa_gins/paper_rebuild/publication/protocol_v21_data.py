"""Strict v2.1 publication inputs, sharing the unchanged ZIP provenance reader."""
from pathlib import Path

import numpy as np
import pandas as pd

from .protocol_v2_data import (ALL, CAL, CONFIG, LABEL, MAIN, Package as V2Package,
    Bundle as V2Bundle, EvidenceUnavailable, sha256_file)

EDITION = 'v2.1'
V21 = 'supplemental/V21/'
SEQUENCES = '13_AGGREGATE_SEQUENCES/v3/UNIQUE_EVALUATION_RESULTS.csv'
SEQUENCE_SERIES = 'sequence_error_series_subset/v3/SUBSET_MANIFEST.csv'
LADDER = V21 + 'LADDER/v3/UNIQUE_EVALUATION_RESULTS.csv'
BODY = V21 + 'SEQUENCES/v3/BODY_FRAME_BIAS.csv'
GRID = V21 + 'NOISE_GRID/v3/SENSITIVITY_GRID.csv'
RESIDUALS = V21 + 'SENSOR_RESIDUALS.csv'
COMPARISON = '13_AGGREGATE/v3/V2_V21_COMPARISON.csv'


class Package(V2Package):
    """Retain exact nonuniform display-row mappings in every figure manifest."""
    def sources(self):
        sources = super().sources()
        maps = []
        for source in sources:
            original = source.get('original_source', {})
            member = original.get('source_row_map_member')
            if not member:
                continue
            mapping = self.table(member)
            if mapping.member_csv_row.duplicated().any():
                raise ValueError('Duplicate display-to-original row mapping')
            selected = mapping[mapping.member_csv_row.isin(source['csv_rows_including_header'])]
            if set(selected.member_csv_row) != set(source['csv_rows_including_header']):
                raise ValueError('Display row lacks an exact original source row')
            source['original_source_rows'] = selected.sort_values('member_csv_row').source_csv_row.astype(int).tolist()
            source['source_row_mapping'] = 'exact retained row map; no fixed-rate/stride assumption'
            maps.append({'package_member': member, **self.manifest['members'][member],
                         'csv_rows_including_header': selected._source_csv_row.astype(int).tolist(),
                         'role': 'display_to_original_csv_row_map'})
        return sources + maps


def _bool(frame, key, *, optional=False):
    if key not in frame:
        if optional:
            return pd.Series(False, index=frame.index)
        raise ValueError('Missing v2.1 data-role field: ' + key)
    values = frame[key].fillna(False).astype(str).str.lower()
    if not values.isin(['true', 'false']).all():
        raise ValueError('Nonboolean v2.1 data-role field: ' + key)
    return values.eq('true')


def validate_roles(rows, *, domain):
    """New controlled cases disclose semisynthetic data; old F01 flags persist."""
    if _bool(rows, 'synthetic_data_used').any() or _bool(rows, 'trace_used_online').any():
        raise ValueError('Forbidden v2.1 scientific data role')
    f01 = rows.method_id.eq('F01')
    reused = _bool(rows, 'formal_F01_reused', optional=True)
    if not reused.equals(f01):
        raise ValueError('Only formal F01 may use original v2 data-role flags')
    semisynthetic = _bool(rows, 'semisynthetic_data_used')
    if domain == 'CORE':
        controlled = ~rows.case_id.eq('C00_clean_normal')
    elif domain == 'ADDENDUM':
        controlled = pd.Series(True, index=rows.index)
    elif domain == 'SEQUENCE':
        controlled = pd.Series(False, index=rows.index)
    else:
        raise ValueError('Unknown v2.1 publication domain')
    if not semisynthetic[~f01].equals(controlled[~f01]):
        raise ValueError('New v2.1 controlled-degradation data flags disagree')
    # F01's historical flags are immutable. Its observation-injection status
    # is disclosed from the case registry by Bundle.disclose, not rewritten.
    return {'formal_F01_reused_count': int(f01.sum()),
            'new_v21_count': int((~f01).sum()), 'controlled_case_rows': int(controlled.sum())}


class Bundle(V2Bundle):
    """v2.1 formal core + addendum + all three sequence identities.

    Only inherited methods with edition-neutral package paths are reused.
    Sequence curves/diagnostics never fall back to pre-correction CAL results.
    """
    def __init__(self, package, trace_path=None, trace_sha256=None, *, _verified_package_identity=None):
        self.p = Package(package, _verified_identity=_verified_package_identity)
        self.trace_path = Path(trace_path) if trace_path else None
        self.trace_sha256 = trace_sha256
        self.unique = self.p.table('12_OFFLINE_EVALUATION/v3/UNIQUE_EVALUATION_RESULTS.csv')
        self._validate(self.unique, 'CORE', 5951, 541)
        self.unique['profile'] = self.unique.effective_configuration_id.map({v: k for k, v in CONFIG.items()})
        self.sequences = self.p.table(SEQUENCES)
        self._validate(self.sequences, 'SEQUENCE', 33, 3)
        if (set(self.sequences.dataset_id) != {'BY2', 'BY2H', 'BY2O'} or
                set(self.sequences.groupby('dataset_id').size()) != {11}):
            raise ValueError('v2.1 requires all eleven formal profiles on each sequence')
        self.trace_used = False
        self.reference_rows = []
        self.notes = []
        self.controlled_degradation_used = False
        self.frozen_source_flags = []

    @staticmethod
    def _validate(rows, domain, count, case_count):
        keys = ['dataset_id', 'case_id', 'effective_configuration_id']
        if (len(rows) != count or rows.case_id.nunique() != case_count or
                rows.duplicated(keys).any() or set(rows.effective_configuration_id) != set(CONFIG.values()) or
                set(rows.evaluator_version) != {'v3'}):
            raise ValueError('v2.1 ' + domain + ' formal identity/count mismatch')
        if not rows.method_id.eq(rows.effective_configuration_id.map({v: k for k, v in CONFIG.items()})).all():
            raise ValueError('v2.1 method/effective-profile identity differs')
        validate_roles(rows, domain=domain)

    def addendum(self):
        probe = self.p.json('ADDENDUM_IDENTITY_PROBE.json')
        if probe.get('passed') is not True:
            raise EvidenceUnavailable('v2.1 addendum identity gate did not pass')
        rows = self.p.table('13_AGGREGATE_ADDENDUM/v3/UNIQUE_EVALUATION_RESULTS.csv')
        self._validate(rows, 'ADDENDUM', 495, 45)
        rows['profile'] = rows.effective_configuration_id.map({v: k for k, v in CONFIG.items()})
        self.disclose(rows, True)
        return rows

    def sequence_series(self, dataset, profile):
        manifest = self.p.table(SEQUENCE_SERIES)
        selected = manifest[(manifest.dataset_id == dataset) & (manifest.method_id == profile)
                            & (manifest.evaluator_version == 'v3')]
        self.p.use(selected)
        if len(selected) != 1:
            raise EvidenceUnavailable('v2.1 sequence curve identity missing: ' + dataset + '/' + profile)
        source = selected.iloc[0]
        if str(source['status']) not in ('OK', 'COMPLETED', 'AVAILABLE'):
            raise EvidenceUnavailable('v2.1 sequence curve is unavailable: ' + str(source['status']))
        member = source.get('member', source.get('package_member'))
        if not isinstance(member, str):
            raise EvidenceUnavailable('v2.1 sequence curve manifest has no member')
        series = self.p.use(self.p.table(member))
        if (series.time.duplicated().any() or not series.time.is_monotonic_increasing or
                not np.isfinite(pd.to_numeric(series.time, errors='coerce')).all()):
            raise ValueError('v2.1 sequence curve times differ from chronological support')
        self.disclose(self.sequences[(self.sequences.dataset_id == dataset) &
                                    (self.sequences.method_id == profile)], False)
        return series
