#!/usr/bin/env python3
"""Small reproducible pure fixtures; no runtime files or external data."""
import hashlib
import json
from pathlib import Path
from covariance_snapshot_supplement import describe, find_covariances

HERE = Path(__file__).resolve().parent
p = [0.0] * 441
for i in range(15):
    p[21 * i + i] = 1.0
results = []
r = describe(p)
assert r['finite_entries'] == 441 and r['max_absolute_asymmetry'] == 0
assert json.loads(r['scale_rows_all_zero']) == json.loads(r['scale_cols_all_zero']) == [True] * 6
results.append({'case': '21x21 diagonal; first 15 ones and six zero scale states', 'passed': True,
                'expected': '441 finite; asymmetry 0; six scale rows/cols zero; no PD PASS'})
p[1] = 1e-15
r = describe(p)
assert r['max_absolute_asymmetry'] == 1e-15 and (r['max_row'], r['max_col']) == (1, 0)
results.append({'case': 'set P[0,1]=1e-15 only', 'passed': True,
                'expected': 'max absolute asymmetry 1e-15 at [1,0]; no tolerance classification'})
p[1] = float('nan')
r = describe(p)
assert r['finite_entries'] == 440 and r['max_absolute_asymmetry'] == 'UNKNOWN'
results.append({'case': 'replace P[0,1] with NaN', 'passed': True,
                'expected': '440 finite; asymmetry UNKNOWN'})
a = list(find_covariances({'data': {'snapshot': {'P_before': {'rows': 21, 'cols': 21, 'data': [0.0] * 441}}}}))
assert len(a) == 1 and a[0][0] == '/data/snapshot/P_before'
results.append({'case': 'nested full P_before object', 'passed': True,
                'expected': 'one matrix with exact JSON field pointer'})
receipt = dict(fixture_cases=4, passed=4, cases=results,
               data_mode='synthetic_fixture_only', synthetic_data_used=True, semisynthetic_data_used=False,
               prior_inline_fixture_cases=4, total_fixture_case_executions=8,
               repeat_reason='persist reproducible tests and bind final script after read-identity gate correction',
               script_sha256=hashlib.sha256((HERE / 'covariance_snapshot_supplement.py').read_bytes()).hexdigest(),
               native_calls=0, evaluator_calls=0, event_payload_reads=0, reference_reads=0, new_tolerance=False)
(HERE / 'P_SUPPLEMENT_TEST.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('4/4 pure fixtures; initial four inline executions retained in accounting')
