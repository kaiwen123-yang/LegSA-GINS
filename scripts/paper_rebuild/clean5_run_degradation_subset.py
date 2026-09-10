#!/usr/bin/env python3
"""P-07: committed contract -> providers -> sealed solves -> v2/v3 -> tables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

CODE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_ROOT / 'src'))

from legsa_gins.paper_rebuild.clean5_degradation.common import (
    FLAGS, registry, resolve, write_json, seal_roots, verify_seal)
from legsa_gins.paper_rebuild.clean5_degradation.runtime import prepare, run_all, checkpoint
from legsa_gins.paper_rebuild.clean5_degradation.evaluation import evaluate_all, horizontal
from legsa_gins.paper_rebuild.clean5_degradation.statistics import build_comparison
from legsa_gins.paper_rebuild.clean5_degradation.report import render
from legsa_gins.paper_rebuild.manifest import sha256_file


def git(*args):
    return subprocess.check_output(['git', *args], cwd=CODE_ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--contract', default=str(CODE_ROOT / 'configs/paper_rebuild/clean5/CLEAN5_DEGRADATION_SUBSET_CONTRACT.yaml'))
    parser.add_argument('--checkpoint-resolution', required=True, help='Local JSON containing mode and literal human_instruction; never assume approval.')
    parser.add_argument('--phase', choices=('prepare', 'solve', 'evaluate'), required=True)
    args = parser.parse_args()
    reg = registry(args.local_config)
    if reg.code_root != CODE_ROOT:
        raise ValueError('Execution code_root differs from ignored local path registry')
    contract_path = Path(args.contract)
    contract = yaml.safe_load(contract_path.read_text())
    stage = resolve(contract['stage_root'], reg)
    if stage.name != 'CLEAN5_DEGSUBSET_BY2' or reg.clean_root not in stage.parents:
        raise ValueError('P-07 output must stay in its exclusive CLEAN5_DEGSUBSET family')
    commit = git('rev-parse', 'HEAD')
    if git('diff', '--name-only', 'HEAD'):
        raise ValueError('Tracked code must be committed before execution')
    contract_rel = contract_path.relative_to(CODE_ROOT).as_posix()
    committed = subprocess.check_output(['git', 'show', 'HEAD:' + contract_rel], cwd=CODE_ROOT)
    if committed != contract_path.read_bytes():
        raise ValueError('Preregistered contract differs from Git')
    contract_commit = git('log', '-1', '--format=%H', '--', contract_rel)
    if contract_commit == commit:
        raise ValueError('Separate later code commit required before provider generation')
    # No untracked implementation can slip through a clean tracked diff.
    implementations = [Path(__file__)] + sorted((CODE_ROOT / 'src/legsa_gins/paper_rebuild/clean5_degradation').glob('*.py'))
    for path in implementations:
        expected = subprocess.check_output(['git', 'show', 'HEAD:' + path.relative_to(CODE_ROOT).as_posix()], cwd=CODE_ROOT)
        if expected != path.read_bytes():
            raise ValueError('Uncommitted P-07 implementation')
    resolution = json.loads(Path(args.checkpoint_resolution).read_text())
    if args.phase == 'prepare':
        runs, bundles = prepare(contract, reg, stage, commit, resolution, args.local_config, contract_path)
        dependency_hashes = {}
        for module in list(sys.modules.values()):
            filename = getattr(module, '__file__', None)
            if filename and str(filename).startswith(str(CODE_ROOT)) and str(filename).endswith('.py'):
                source = Path(filename)
                dependency_hashes[source.relative_to(CODE_ROOT).as_posix()] = sha256_file(source)
        write_json(stage / '00_PREREGISTRATION/EXECUTION_FREEZE.json', {
            **FLAGS, 'data_mode': 'real_base_controlled_degradation', 'code_commit': commit,
            'contract_commit': contract_commit, 'contract_hash': sha256_file(contract_path),
            'source_sha256': dependency_hashes, 'checkpoint_resolution': resolution,
            'case_count': 61, 'solver_limit': 1342, 'run_registry_rows': runs})
        print('PREPARE_COMPLETE', flush=True)
        return
    freeze = json.loads((stage / '00_PREREGISTRATION/EXECUTION_FREEZE.json').read_text())
    if freeze['code_commit'] != commit or freeze['contract_hash'] != sha256_file(contract_path):
        raise ValueError('Phase source/contract freeze mismatch')
    for relative, digest in freeze['source_sha256'].items():
        if sha256_file(CODE_ROOT / relative) != digest:
            raise ValueError('Imported source changed between phases')
    verify_seal(stage / '04_SEAL/PROVIDER_SEAL.json', stage)
    if args.phase == 'solve':
        bundles = json.loads((stage / '02_PROVIDERS/PROVIDER_BUNDLES.json').read_text())
        run_all(freeze['run_registry_rows'], bundles, contract, reg, stage, commit, resolution)
        print('SOLVERS_SEALED', flush=True)
        return
    records = json.loads((stage / '03_RUNS/RUN_RECORDS.json').read_text())
    results = evaluate_all(records, contract, reg, stage, commit)
    comparison, decision = build_comparison(contract, reg, stage, results, commit)
    horizontal_rows = horizontal(contract, reg, stage, results, commit)
    checkpoint(contract, reg, stage, 'AFTER_EVALUATION', resolution)
    verify_seal(stage / '04_SEAL/SOLVER_OUTPUT_SEAL.json', stage)
    render(contract, stage, records, results, comparison, decision, horizontal_rows, commit, contract_commit)
    seal_roots(stage, ['07_EVALUATION', '08_AGGREGATE', '09_HORIZONTAL_V3'], '04_SEAL/EVALUATION_ARTIFACT_SEAL.json',
               {'code_commit': commit, 'data_mode': 'real_base_controlled_degradation', 'decision': decision['decision']})
    write_json(stage / 'FINAL_STATUS.json', {'status': 'COMPLETED', 'code_commit': commit,
               'solver_terminal_count': len(records), 'evaluation_terminal_count': len(results),
               'decision': decision['decision'], 'full_matrix_rerun_executed': False})
    print('P07_COMPLETE', decision['decision'], flush=True)


if __name__ == '__main__':
    main()
