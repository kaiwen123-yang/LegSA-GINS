#!/usr/bin/env python3
"""Explicit H-EXT-02 stage actions; one authorized attempt, no scientific retries."""
import argparse
import json
import os

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'

from legsa_gins.paper_rebuild.hext import execution

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=('preflight', 'identity', 'freeze', 'native', 'evaluate', 'aggregate', 'figures'))
args = parser.parse_args()
actions = dict(preflight=execution.preflight, identity=execution.identity_recheck,
               freeze=execution.freeze_receipt, native=execution.run_native_matrix,
               evaluate=execution.run_evaluation_matrix, aggregate=execution.aggregate_results,
               figures=execution.render_results)
try:
    result = actions[args.action]()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
except Exception as exc:
    _, scratch, _ = execution.stage_roots()
    execution.write_json(scratch / ('HARD_STOP_' + args.action.upper() + '.json'),
                         dict(action=args.action, status='HARD_STOP', error_type=type(exc).__name__, error=str(exc)))
    raise
