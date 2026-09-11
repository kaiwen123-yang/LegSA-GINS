"""Contract closure and separate preregistration/code freeze checks."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import yaml
from ..clean5_degradation.common import pinned, read_csv
from ..manifest import sha256_file

STAGE_NAME = 'CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2'
PROFILES = ('F01','F02','F03','F04','A03','A04','A05','A06','A07','A08','A09')


def load_contract(path):
    contract = yaml.safe_load(Path(path).read_text())
    if contract.get('schema_version') != 'paper_rebuild.clean6.canonical541_protocol_v2.v1':
        raise ValueError('Unknown P09c schema')
    if contract['stage_root'] != '<CLEAN_ROOT>/stages/'+STAGE_NAME:
        raise ValueError('Wrong protocol stage')
    if contract['selection']['NOT_TRANSFERABLE'] or contract['selection']['selected_case_count'] != 541:
        raise ValueError('All 541 cases required')
    if tuple(contract['runtime']['profiles']) != PROFILES or set(contract['runtime']['chains']) != {'CAL'}:
        raise ValueError('P09c requires CAL and eleven profiles')
    if contract['runtime']['solver_limit'] != 5973 or contract['sequence_consistency']['run_count'] != 33:
        raise ValueError('Distinct run accounting mismatch')
    if contract['execution']['initial_workers'] != 64 or contract['execution']['maximum_workers'] != 128:
        raise ValueError('Frozen concurrency mismatch')
    if contract['storage']['direct_G_fallback'] or contract['storage']['peak_limit_bytes'] != 250000000000:
        raise ValueError('Frozen ext4 retention policy mismatch')
    mappings = contract['providers']['mapping']
    if len(mappings) != 541 or [r['case_id'] for r in mappings] != contract['selection']['selected_case_ids']:
        raise ValueError('Frozen mapping does not close')
    for tid in ('D22','D39'):
        selected=[r for r in mappings if r['degradation_type_id']==tid]
        if len(selected)!=9 or any(len(r['intervals'])!=(1 if tid=='D22' else 3) for r in selected):
            raise ValueError('All nine frozen count-window mappings required')
    return contract


def selection(contract, reg):
    cases=read_csv(pinned(contract['sources']['case_registry'],reg))
    runs=read_csv(pinned(contract['sources']['unique_run_registry'],reg))
    if len(cases)!=541 or [r['case_id'] for r in cases]!=contract['selection']['selected_case_ids']:
        raise ValueError('Frozen case order changed')
    expected={(r['case_id'],m) for r in cases for m in PROFILES}
    if len(runs)!=5951 or {(r['case_id'],r['method_id']) for r in runs} != expected:
        raise ValueError('Frozen run identity closure failed')
    return cases, sorted(runs,key=lambda r:int(r['run_order']))


def verify_preregistration(contract_path, code_root, *, expected_commit=None):
    """Permit execution only from committed contract and a later code commit."""
    code_root=Path(code_root); path=Path(contract_path)
    relative=path.relative_to(code_root).as_posix()
    def git(*args): return subprocess.check_output(['git',*args],cwd=code_root)
    commit=git('rev-parse','HEAD').decode().strip()
    if git('diff', '--name-only', 'HEAD').strip():
        raise ValueError('All tracked implementation and protocol changes must be committed before launch')
    if expected_commit is not None and commit!=expected_commit:
        raise ValueError('Code commit changed')
    if git('show','HEAD:'+relative)!=path.read_bytes():
        raise ValueError('Contract is uncommitted or modified')
    contract_commit=git('log','-1','--format=%H','--',relative).decode().strip()
    if contract_commit==commit:
        raise ValueError('Separate code commit after preregistration required')
    subprocess.run(['git','merge-base','--is-ancestor',contract_commit,commit],cwd=code_root,check=True)
    implementations=sorted((code_root/'src/legsa_gins/paper_rebuild/clean6_canonical_v2').glob('*.py'))
    implementations.extend(sorted((code_root/'scripts/paper_rebuild').glob('clean6_*canonical541_v2.py')))
    for source in implementations:
        rel=source.relative_to(code_root).as_posix()
        if git('show','HEAD:'+rel)!=source.read_bytes():
            raise ValueError('Uncommitted P09c implementation '+rel)
    return {'code_commit':commit,'contract_commit':contract_commit,'contract_hash':sha256_file(path)}
