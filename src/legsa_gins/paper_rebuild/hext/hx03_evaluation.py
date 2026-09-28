"""HX-03 frozen evaluator child registered with the unchanged HX-02 launcher."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import sys

from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256
from ..clean5_sequence.evaluator_capture import install
from .hx03_injection import sha, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', type=Path, required=True)
    spec = json.loads(parser.parse_args().spec.read_text())
    evaluator = Path(spec['evaluator'])
    if sha(evaluator) != EVALUATOR_SHA256:
        raise ValueError('HARD_STOP_EVALUATOR_IDENTITY')
    out = Path(spec['outdir'])
    out.mkdir(parents=True, exist_ok=False)
    config = out / 'CAPTURE_CONFIG.json'
    write_json(config, {'evaluator': str(evaluator), 'evaluator_sha256': EVALUATOR_SHA256,
        'trace': spec['trace'], 'trace_sha256': spec['trace_sha256'], 'window': spec['window'],
        'outdir': str(out), 'STD': 'OMITTED_AS_FROZEN_EXTERNAL_CONTRACT'})
    install(config)
    sys.argv = [str(evaluator), '--trace', spec['trace'], '--nav', spec['nav'], '--outdir', str(out),
                '--base_time', str(spec['base_time']), '--yaw_truth_mode', 'enu']
    runpy.run_path(str(evaluator), run_name='__main__')


if __name__ == '__main__':
    main()
