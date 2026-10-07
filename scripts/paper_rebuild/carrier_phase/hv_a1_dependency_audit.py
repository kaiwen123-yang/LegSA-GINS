#!/usr/bin/env python3
"""Bounded passive CALIBRATED_GNSS endpoint-time audit; never changes velocity."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from legsa_gins.paper_rebuild.carrier_phase.hv_a1_dependencies import dependencies, SCOPE
D = ROOT / 'docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007'
PLAN = D / 'HV_A1_DEPENDENCY_PLAN.json'
SCRIPT = 'scripts/paper_rebuild/carrier_phase/hv_a1_dependency_audit.py'
TEST = 'tests/paper_rebuild/test_hv_a1_dependencies.py'
BUDGET = dict(pytest_processes=1, synthetic_cases=6, synthetic_helper_calls=16,
              scientific_files=9, scientific_file_read_passes=1,
              real_helper_calls=3, source_decisions=4602, selected=4598,
              native_calls=0, evaluator_calls=0, raw_reads=0, body_npz_reads=0,
              velocity_recomputations=0, automatic_retries=0)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bits(t):
    return struct.pack('>d', float(t)).hex()


def emit(path, value):
    with path.open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write('\n')


class Inputs:
    def __init__(self, aliases):
        self.aliases = aliases
        self.receipts = []
        self.attempts = []
        self.seen = set()

    def path(self, value):
        for key, replacement in self.aliases.items():
            value = value.replace(key, replacement)
        require('<' not in value, 'unexpanded path')
        return Path(value).resolve()

    def read(self, pin, role):
        path = self.path(pin['path'])
        require(path not in self.seen, 'registered input opened more than once')
        self.seen.add(path)
        attempt=dict(role=role,path=pin['path'],expected_size=pin['size_bytes'],bytes_read=0)
        self.attempts.append(attempt)
        require(path.stat().st_size==pin['size_bytes'], 'input size before bounded read: '+role)
        with path.open('rb') as stream:
            data=stream.read(pin['size_bytes']+1)
        attempt['bytes_read']=len(data)
        require(len(data) == pin['size_bytes'] and sha(data) == pin['sha256'], 'input identity: '+role)
        self.receipts.append(dict(role=role, path=pin['path'], size_bytes=len(data),
                                 sha256=pin['sha256'], physical_read_passes=1))
        return data

    def json(self, pin, role):
        return json.loads(self.read(pin, role))


def physical_csv(data, role):
    # Same physical-line order and quote-toggle/trim as the native loader.
    # Empty LF lines are skipped there; whitespace-only or unclosed quoted
    # records are rejected here instead of guessing a different row identity.
    lines = data.decode('utf-8').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    require(lines and lines[0].strip(), role+': missing physical header')
    def split(line):
        cells=[];cell=[];quoted=False
        for ch in line:
            if ch == '"':
                quoted = not quoted
            elif ch == ',' and not quoted:
                cells.append(''.join(cell).strip());cell=[]
            else:
                cell.append(ch)
        require(not quoted, role+': unclosed physical quote/multiline field')
        cells.append(''.join(cell).strip())
        return cells
    fields=split(lines[0])
    require(len(fields)==len(set(fields)) and all(fields), role+': ambiguous header')
    for line in lines[1:]:
        if line == '':
            continue
        require(line.strip(), role+': ambiguous whitespace-only native row')
        cells=split(line)
        require(len(cells)==len(fields), role+': CSV width')
        yield dict(zip(fields,cells))


def finite(value):
    value = float(value)
    require(math.isfinite(value), 'nonfinite source time')
    return value


def process_sequence(spec, reader):
    sid = spec['sequence_id']
    events = list(physical_csv(reader.read(spec['decisions'], 'science:'+sid+':decisions'), 'decisions'))
    require(len(events) == spec['opportunities'], 'full opportunity count')
    selected = []
    indices = set()
    previous = -math.inf
    generations = set()
    for opportunity, row in enumerate(events):
        state, trigger = finite(row['state_time']), finite(row['trigger_time'])
        require(bits(state) == bits(trigger), 'registered exact-event clocks')
        require(row['frame'] == 'ned' and row['actual_available_time_s'] == '', 'NED/unknown arrival')
        require(row['source_present'] == row['consumed'] and row['source_present'] in ('0','1'), 'source presence')
        generations.add(int(row['generation']))
        if row['source_present'] == '0':
            require(row['accepted'] == '0' and all(row[k] == '' for k in
                    ('source_time','vector_index','source_time_bits_hex')), 'unavailable source remains empty')
            continue
        require(row['accepted'] == '1', 'registered windows have selected == accepted')
        index, source = int(row['vector_index']), finite(row['source_time'])
        require(index >= 0 and index not in indices and previous < source <= state,
                'accepted source unique, ordered and row-causal')
        require(bits(source) == row['source_time_bits_hex'], 'decision source bits')
        selected.append((opportunity,index,source,state))
        indices.add(index); previous = source
    require(len(generations) == 1 and len(selected) == spec['accepted'], 'generation/accepted denominator')
    hv_matches = {}
    hv_count = 0
    for index, row in enumerate(physical_csv(reader.read(spec['hv'], 'science:'+sid+':hv'), 'HV')):
        hv_count += 1
        if index in indices:
            require(row['update_flag'].lower() in ('true','1') and row['source_status'] == 'active', 'selected HV active')
            require(row['frame_candidate'] == 'FLU_to_FRD_Go2_RP_injected_A1_NED' and
                    row['prior_policy'] == 'SENSOR_MODEL_V21_horizontal_weak_prior', 'actual HV generation identity')
            hv_matches[index] = finite(row['time'])
    require(hv_count == spec['provider_rows'] and set(hv_matches) == indices, 'complete unfiltered vector mapping')
    for _,index,source,_ in selected:
        require(bits(hv_matches[index]) == bits(source), 'HV/decision time bits')
    data = reader.read(spec['gnss'], 'science:'+sid+':historical_gnss')
    gnss = np.loadtxt(io.StringIO(data.decode('utf-8')), dtype=np.float64, ndmin=2)
    require(gnss.ndim == 2 and gnss.shape[1] == 18 and np.isfinite(gnss[:,0]).all(), 'historical GNSS18 shape/time')
    require(np.all(np.diff(gnss[:,0]) > 0) and np.isin(gnss[:,17], [0.,1.]).all(), 'GNSS18 order/yaw flags')
    endpoint_rows = np.flatnonzero(gnss[:,17] == 1.)
    require(np.isfinite(gnss[endpoint_rows,13]).all(), 'finite yaw at actual generating endpoints')
    endpoint_times = gnss[endpoint_rows,0]
    joined = dependencies([x[2] for x in selected], endpoint_times,
                          round_to_ms=True, maximum_gap_s=1.2)
    require(len(joined) == len(selected), 'all selected dependencies retained')
    by_opportunity = {}
    for identity, dep in zip(selected, joined):
        opportunity,index,source,state = identity
        require(dep['support'] and dep['latest_endpoint_source_time'] is not None, 'accepted HV has valid generating support')
        latest = dep['latest_endpoint_source_time']
        after_query, after_state = latest > source, latest > state
        require(not after_state or after_query, 'state-future subset of query-future')
        by_opportunity[opportunity] = dict(
            status='JOINED_GENERATOR_ENDPOINTS', provider_vector_index=index,
            source_time=source, dependency_scope=SCOPE, support=dep['support'], kind=dep['kind'],
            endpoint_valid_indices=dep['endpoint_indices'],
            endpoint_gnss_data_indices=[int(endpoint_rows[i]) for i in dep['endpoint_indices']],
            endpoint_source_times=dep['endpoint_source_times'],
            endpoint_coordinates=dep['endpoint_coordinates'], endpoint_weights=dep['weights'],
            unwrap_prefix_last_index=dep['unwrap_prefix_last_index'],
            latest_endpoint_source_time=latest,
            dependency_after_hv_query=after_query, dependency_after_state=after_state,
            rounded_coordinate_after_state=max(dep['endpoint_coordinates'])>state,
            dependency_minus_hv_query_s=latest-source, dependency_minus_state_s=latest-state)
    rows=[]
    for i,event in enumerate(events):
        record=dict(sequence_id=sid, opportunity_index=i, state_time=finite(event['state_time']),
                    accepted=int(event['accepted']), original_reason=event['reason'], actual_arrival_time_s=None)
        record.update(by_opportunity.get(i, dict(status='NO_SELECTED_HV_SOURCE')))
        rows.append(record)
    leads = [r['dependency_minus_state_s'] for r in rows if r['status']=='JOINED_GENERATOR_ENDPOINTS']
    positive = [v for v in leads if v > 0]
    summary=dict(sequence_id=sid, opportunities=len(rows), selected=len(selected),
                 no_selected=len(rows)-len(selected), provider_rows=hv_count,
                 gnss_rows=len(gnss), valid_a1_endpoints=len(endpoint_rows),
                 dependency_after_hv_query=sum(r.get('dependency_after_hv_query',False) for r in rows),
                 dependency_after_state=len(positive),
                 rounded_coordinate_after_state=sum(r.get('rounded_coordinate_after_state',False) for r in rows),
                 positive_lead_bins_s={'(0,1e-6]':sum(0<v<=1e-6 for v in leads),
                                       '(1e-6,1e-3]':sum(1e-6<v<=1e-3 for v in leads),
                                       '(1e-3,1e-2]':sum(1e-3<v<=1e-2 for v in leads),
                                       '(1e-2,inf)':sum(v>1e-2 for v in leads)},
                 max_dependency_minus_state_s=max(leads,default=None),
                 min_positive_dependency_minus_state_s=min(positive,default=None),
                 kinds=dict(Counter(r.get('kind','NO_SELECTED_HV_SOURCE') for r in rows)))
    return rows,summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--registration-commit',required=True);args=parser.parse_args()
    reg=json.loads(PLAN.read_text())
    require(reg['status']=='REGISTERED_READY_SINGLE_EXECUTION' and reg['budgets']==BUDGET,'frozen plan/budget')
    require(PLAN.read_bytes()==subprocess.check_output(['git','show',args.registration_commit+':'+str(PLAN.relative_to(ROOT))],cwd=ROOT),'registered plan bytes')
    require(SCRIPT in reg['source_pins'] and TEST in reg['source_pins'],'runner/test registered')
    for relative,pin in reg['source_pins'].items():
        require(sha((ROOT/relative).read_bytes())==pin,'current source: '+relative)
        require(sha(subprocess.check_output(['git','show',args.registration_commit+':'+relative],cwd=ROOT))==pin,'registered source')
    for relative in reg['generator_source_paths']:
        require(sha(subprocess.check_output(['git','show',reg['generation_commit']+':'+relative],cwd=ROOT))==reg['source_pins'][relative],'historical generator source identity')
    reader=Inputs(reg['aliases']);stage=reader.path(reg['stage'])
    require(stage.parent==ROOT.parent.parent/'LegSA-GINS-SCRATCH/TRUSTED_HEADING_CONTINUATION_20261007' and not stage.exists(),'new bounded scratch attempt')
    stage.mkdir();emit(stage/'REGISTERED_PLAN.json',reg)
    local_done=False
    try:
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                 PYTHONPATH=str(ROOT/'src'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        env.pop('PYTEST_ADDOPTS',None);env.pop('PYTEST_PLUGINS',None)
        command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',TEST,'--junitxml='+str(stage/'LOCAL_TESTS.xml')]
        with (stage/'LOCAL_TESTS.stdout').open('xb') as out,(stage/'LOCAL_TESTS.stderr').open('xb') as err:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=60)
        require(result.returncode==0,'first local test process failed; no real payload read')
        suites=ET.parse(stage/'LOCAL_TESTS.xml').getroot().findall('.//testsuite')
        require(sum(int(s.get('tests','0')) for s in suites)==6 and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped')),'exact six passing cases')
        local_done=True;print('LOCAL_6_PASS',flush=True)
        meta={k:reader.json(v,'metadata:'+k) for k,v in reg['metadata_pins'].items()}
        oldplan=meta['native_plan'];oldaliases=Inputs(oldplan['aliases'])
        outputs=meta['native_seal']['outputs']
        require(meta['native_seal']['status']=='ALL_SIX_SEALED_THREE_LEGACY_IDENTITIES_PASS','native result state')
        require([s['sequence_id'] for s in reg['sequences']]==['BY2','BY2H','BY2O'],'original sequence order')
        scientific=[s[k] for s in reg['sequences'] for k in ('decisions','hv','gnss')]
        require(len({reader.path(x['path']) for x in scientific})==9,'nine unique scientific inputs')
        require(sum(x['size_bytes'] for x in scientific)==reg['scientific_bytes'],'fixed scientific byte total')
        for spec in reg['sequences']:
            sid=spec['sequence_id'];bundle=meta[sid+'_bundle'];manifest=meta[sid+'_manifest']
            require(bundle['code_commit']==reg['generation_commit'] and bundle['dataset_id']==sid,'generation identity')
            for key,role in [('providers','hv'),('base_provider_pins','gnss')]:
                entry=bundle[key]['go2_horizontal_velocity_prior_path' if role=='hv' else 'gnsspath']
                require(reader.path(entry['path'])==reader.path(spec[role]['path']) and entry['sha256']==spec[role]['sha256'],'generator input/output binding')
            logged=bundle['input_files'][spec['gnss']['path']]
            require(logged['sha256']==spec['gnss']['sha256'] and logged['bytes']==spec['gnss']['size_bytes'],'actual generator GNSS read identity')
            require(any(oldaliases.path(x['path'])==reader.path(spec['hv']['path']) and x['sha256']==spec['hv']['sha256'] and x['size_bytes']==spec['hv']['size_bytes'] for x in oldplan['provider_inputs']),'native actual provider closure')
            output=next(x for x in outputs if x['sequence_id']==sid and x['arm']=='CAUSAL')
            for name,pin in [('NED_VELOCITY_SOURCE_EVENTS.csv',spec['decisions']),('RUN_MANIFEST.json',reg['metadata_pins'][sid+'_manifest'])]:
                require(reader.path(output['path'])/name==reader.path(pin['path']) and output['seal']['files'][name]==dict(sha256=pin['sha256'],size_bytes=pin['size_bytes']),'same causal output identity')
            require(manifest['go2_velocity_prior_time_policy']=='causal_unique_latest' and manifest['go2_velocity_prior_diagnostic_prior_count']==spec['provider_rows'] and manifest['go2_velocity_prior_update_count']==spec['accepted'],'native count/policy')
        rows=[];summaries=[]
        for spec in reg['sequences']:
            one,summary=process_sequence(spec,reader);rows.extend(one);summaries.append(summary)
            print(spec['sequence_id'],'JOIN_COMPLETE',flush=True)
        require(len(rows)==4602 and sum(s['selected'] for s in summaries)==4598,'full denominator')
        require(sum(x['role'].startswith('science:') for x in reader.receipts)==9,'nine once-read scientific files')
        fields=list(dict.fromkeys(k for row in rows for k in row))
        with (stage/'ROWS.csv').open('x',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            writer.writerows({k:json.dumps(v) if isinstance(v,list) else v for k,v in row.items()} for row in rows)
        summary=dict(status='COMPLETE_PASSIVE_HV_GENERATOR_ENDPOINT_TIME_AUDIT',registration_commit=args.registration_commit,
                     scope=SCOPE,sequences=summaries,opportunities=len(rows),selected=4598,no_selected=4,
                     python_version=sys.version,numpy_version=np.__version__,
                     dependency_after_hv_query=sum(s['dependency_after_hv_query'] for s in summaries),
                     dependency_after_state=sum(s['dependency_after_state'] for s in summaries),
                     actual_arrival_qualified=False,raw_receiver_time_qualified=False,velocity_recomputed=False,
                     native_calls=0,evaluator_calls=0,local_synthetic_cases=6,local_first_pass=True,
                     not_a_navigation_accuracy_result=True)
        emit(stage/'SUMMARY.json',summary);emit(stage/'INPUT_READS.json',reader.receipts)
        emit(stage/'COMPLETE.json',dict(summary,output_files={n:dict(sha256=sha((stage/n).read_bytes()),size_bytes=(stage/n).stat().st_size) for n in ('ROWS.csv','SUMMARY.json','INPUT_READS.json','LOCAL_TESTS.xml','LOCAL_TESTS.stdout','LOCAL_TESTS.stderr')}))
        print(json.dumps(summary),flush=True)
    except BaseException as exc:
        emit(stage/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),local_tests_passed=local_done,input_reads=reader.receipts,input_attempts=reader.attempts,automatic_retries=0))
        raise


if __name__=='__main__':
    main()
