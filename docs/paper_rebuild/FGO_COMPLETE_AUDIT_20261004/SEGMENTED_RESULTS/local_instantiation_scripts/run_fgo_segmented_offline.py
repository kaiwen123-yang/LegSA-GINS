"""Local offline controller, executed only after all three new natives are sealed.

This external orchestration does not change registered scientific code or inputs.
It runs the frozen evaluator once per sequence and records actual reference opens.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--roots', required=True)
parser.add_argument('--protocol', required=True)
parser.add_argument('--python', required=True)
args = parser.parse_args()
roots = json.loads(pathlib.Path(args.roots).read_text())['aliases']
code = pathlib.Path(roots['<CODE_ROOT>'])
stage = pathlib.Path(roots['<FGO_DIAGNOSTIC_ROOT>'])
sys.path.insert(0, str(code/'src'))
from legsa_gins.paper_rebuild.fgo_comparison.raw_inputs import sha256, dump
from legsa_gins.paper_rebuild.fgo_comparison.segmented_diagnostic import verify_sources
from legsa_gins.paper_rebuild.fgo_comparison.evaluation import resolve
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records
import yaml

protocol = json.loads(pathlib.Path(args.protocol).read_text())
seal_path = stage/'ALL_NATIVE_SEALED.json'
seal_hash = sha256(seal_path)
seal = json.loads(seal_path.read_text())
assert seal['all_three_new_native_terminal'] and seal['new_native_count'] == 3
assert seal['new_evaluator_count_at_seal'] == 0
assert seal['new_native_reference_opens'] == seal['reused_original_native_reference_opens'] == 0
assert seal['protocol_sha256'] == sha256(args.protocol)
assert not (stage/'evaluation').exists()
assert not (stage/'ALL_OFFLINE_COMPLETE.json').exists()
controller_hash = sha256(__file__)
contract = yaml.safe_load((code/protocol['execution_contract_path']).read_text())
references = {sequence: str(resolve(spec['trace']['path'], roots))
              for sequence, spec in contract['sequences'].items()}
env = os.environ.copy()
env.update(PYTHONPATH=str(code/'src'), PYTHONDONTWRITEBYTECODE='1',
           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
           LEGSA_OBGINS_BRIDGE=roots['<FGO_BUILD>']+'/libobgins_bridge.so')
os.environ['LEGSA_OBGINS_BRIDGE'] = env['LEGSA_OBGINS_BRIDGE']

def native_gate():
    verify_sources(code, protocol)
    assert sha256(seal_path) == seal_hash
    assert sha256(args.protocol) == seal['protocol_sha256']
    assert sha256(__file__) == controller_hash
    for methods in seal['comparison_identities'].values():
        for binding in methods.values():
            path = resolve(binding['path'], roots)
            assert sha256(path/'RUN.json') == binding['run_json_sha256']
            assert sha256(path/'ACCESS.json') == binding['access_sha256']
            run = json.loads((path/'RUN.json').read_text())
            for name, digest in run['output_hashes'].items():
                assert sha256(path/name) == digest

native_gate()
launch = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'controller_sha256': controller_hash, 'protocol_sha256': sha256(args.protocol),
          'native_seal_sha256': seal_hash, 'source_count': len(protocol['execution_source_hashes']),
          'registered_sequences': protocol['new_native_sequences'],
          'reference_rule': 'one actual physical payload read per sequence, only after all natives sealed',
          'new_native_calls': 0, 'planned_offline_calls': 3}
assert not (stage/'OFFLINE_CONTROLLER_LAUNCH.json').exists()
dump(stage/'OFFLINE_CONTROLLER_LAUNCH.json', launch)
journal = []
for sequence in protocol['new_native_sequences']:
    native_gate()
    trace = stage/'logs'/(sequence+'_OFFLINE_OPENAT.strace')
    log = stage/'logs'/(sequence+'_OFFLINE.log')
    argv = ['strace', '-f', '-qq', '-yy', '-e', 'trace=openat', '-o', str(trace),
            args.python, '-m', 'legsa_gins.paper_rebuild.fgo_comparison.segmented_evaluation',
            '--roots', args.roots, '--protocol', args.protocol, '--sequence', sequence]
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clock = time.perf_counter()
    print('OFFLINE_START '+sequence, flush=True)
    with log.open('x') as stream:
        process = subprocess.run(argv, cwd=code, env=env, stdout=stream, stderr=subprocess.STDOUT)
    assert process.returncode == 0, sequence+' offline failed: retain partial, no automatic retry'
    native_gate()
    records = audited_open_records(trace, code)
    opens = [item for item in records if item.get('path') in references.values()
             or item.get('lexical_path') in references.values()]
    assert len(opens) == 1 and opens[0].get('path') == references[sequence]
    assert opens[0]['return_code'] >= 0 and 'O_RDONLY' in opens[0]['flags'], 'Reference read attempt failed'
    destination = stage/'evaluation'/sequence
    evaluation = json.loads((destination/'EVALUATION.json').read_text())
    assert evaluation['reference_read_count'] == 1 and len(evaluation['rows']) == 12
    assert evaluation['native_seal_sha256'] == seal_hash
    assert evaluation['protocol_sha256'] == sha256(args.protocol)
    access = {'actual_reference_open_attempts': len(opens), 'actual_reference_payload_opens': 1,
              'opened_reference_path': references[sequence], 'native_calls': 0,
              'all_new_native_sealed_before_open': True, 'strace_sha256': sha256(trace),
              'open_records_including_failed': len(records)}
    dump(destination/'ACCESS.json', access)
    output_hashes = {str(path.relative_to(destination)): sha256(path)
                     for path in sorted(destination.rglob('*')) if path.is_file()}
    journal.append({'sequence': sequence, 'start_utc': start,
                    'end_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'elapsed_s': time.perf_counter()-clock, 'returncode': process.returncode,
                    'actual_reference_payload_opens': 1, 'metric_row_count': 12,
                    'output_hashes': output_hashes, 'argv': argv,
                    'stdout_sha256': sha256(log), 'strace_sha256': sha256(trace),
                    'source_before_after_pass': True})
    dump(stage/'OFFLINE_JOURNAL.json', {'completed_sequences': journal,
                                      'new_offline_count': len(journal), 'new_native_calls': 0})
    print('OFFLINE_DONE '+sequence+' 12rows reference1', flush=True)
native_gate()
files = [path for path in stage.rglob('*') if path.is_file()]
directories = [path for path in stage.rglob('*') if path.is_dir()]
proxy = sum((path.stat().st_size+262143)//262144*262144 for path in files)+len(directories)*262144
assert proxy <= protocol['new_stage_budget_bytes'], 'Registered G allocation proxy exceeded'
complete = {'schema': 'fgo.segmented.all-offline.complete.v1',
            'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'all_three_offline_complete': True, 'new_offline_count': 3, 'new_native_calls': 0,
            'total_actual_offline_reference_payload_opens': 3, 'native_online_reference_opens': 0,
            'metric_row_count': sum(item['metric_row_count'] for item in journal),
            'protocol_sha256': sha256(args.protocol), 'native_seal_sha256': seal_hash,
            'offline_controller_sha256': controller_hash,
            'offline_launch_sha256': sha256(stage/'OFFLINE_CONTROLLER_LAUNCH.json'),
            'offline_journal_sha256': sha256(stage/'OFFLINE_JOURNAL.json'),
            'source_count': len(protocol['execution_source_hashes']), 'source_before_after_pass': True,
            'logical_stage_bytes': sum(path.stat().st_size for path in files),
            'allocated_stage_budget_proxy_bytes': proxy, 'is_actual_windows_allocation_API': False,
            'sequences': journal}
dump(stage/'ALL_OFFLINE_COMPLETE.json', complete)
print('ALL_THREE_OFFLINE_COMPLETE '+str(stage/'ALL_OFFLINE_COMPLETE.json'), flush=True)
