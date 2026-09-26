#!/usr/bin/env python3
"""Copy completed, sealed A1/A2 facts into a portable report; no scientific calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import yaml


STAGE_NAME = 'CLEAN6_ADDENDUM_FAMILIES_A1_A2'
COMPANION_PREFIX = 'ADDENDUM_A1_A2_'
TRANSPORT = 'docs/paper_rebuild/clean6/ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md'
SUMMARY_FIELDS = (
    'comparison', 'metric_name', 'scope', 'family', 'case_family', 'duration_s',
    'paired_sample_count', 'total_case_count', 'mean_delta_candidate_minus_reference',
    'median_delta_candidate_minus_reference', 'mean_ci95_low', 'mean_ci95_high',
    'median_ci95_low', 'median_ci95_high', 'win_count', 'tie_count', 'loss_count',
    'win_rate', 'wilcoxon_p', 'wilcoxon_zero_policy', 'wilcoxon_approximation',
    'bootstrap_n', 'bootstrap_seed', 'bootstrap_policy', 'delta_definition',
)
FAILURE_FIELDS = (
    'failure_aware_comparable_count', 'failure_aware_win_count', 'failure_aware_loss_count',
    'failure_aware_tie_count', 'failure_aware_win_rate', 'failure_aware_win_rate_denominator',
    'all_registered_case_win_rate_sensitivity', 'all_registered_case_denominator',
    'both_algorithm_failure_count', 'candidate_algorithm_failure_count',
    'reference_algorithm_failure_count', 'technical_missing_count',
    'evaluation_suspect_count', 'finite_metric_unavailable_count', 'denominator_policy',
)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def regular(path, root):
    path, root = Path(path), Path(root)
    if (not path.is_relative_to(root) or not path.is_file()
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError('Missing, symlink, or out-of-scope report source: '+str(path))
    return path


def safe_relative(value):
    value = Path(value)
    if value.is_absolute() or '..' in value.parts:
        raise ValueError('Unsafe sealed relative member')
    return value


def csv_bytes(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ['status']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def cell(value):
    if value is None or value == '':
        return 'UNAVAILABLE'
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def md_table(headers, rows):
    output = ['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']
    output.extend('| '+' | '.join(cell(value) for value in row)+' |' for row in rows)
    return '\n'.join(output)+'\n'


class Evidence:
    def __init__(self, stage):
        self.stage = Path(stage)
        final_path = regular(self.stage/'FINAL_STATUS.json', self.stage)
        self.final_bytes = final_path.read_bytes()
        self.final = json.loads(self.final_bytes)
        seal_path = regular(self.stage/'FINAL_RECORD_SEAL.json', self.stage)
        self.seal_bytes = seal_path.read_bytes()
        self.seal = json.loads(self.seal_bytes)
        if self.seal.get('status') != 'SEALED':
            raise ValueError('Addendum final record seal is unavailable')
        self.pins = self.seal['files']
        self.rows = [{'source': '<ADDENDUM_ROOT>/FINAL_STATUS.json', 'sha256': digest(self.final_bytes),
                      'size_bytes': len(self.final_bytes), 'csv_data_rows': 'NOT_APPLICABLE', 'verification': 'TERMINAL_GATE'},
                     {'source': '<ADDENDUM_ROOT>/FINAL_RECORD_SEAL.json', 'sha256': digest(self.seal_bytes),
                      'size_bytes': len(self.seal_bytes), 'csv_data_rows': 'NOT_APPLICABLE', 'verification': 'FINAL_RECORD_SEAL'}]
        self.cache = {}

    def payload(self, relative):
        relative = safe_relative(relative).as_posix()
        if relative in self.cache:
            return self.cache[relative]
        if relative not in self.pins:
            raise ValueError('Required report source is not in the final record seal: '+relative)
        path = regular(self.stage/relative, self.stage)
        payload = path.read_bytes()
        pin = self.pins[relative]
        if len(payload) != pin['size_bytes'] or digest(payload) != pin['sha256']:
            raise ValueError('Sealed report source changed: '+relative)
        self.cache[relative] = payload
        self.rows.append({'source': '<ADDENDUM_ROOT>/'+relative, 'sha256': pin['sha256'],
                          'size_bytes': len(payload), 'csv_data_rows': 'NOT_APPLICABLE', 'verification': 'FROZEN_FINAL_RECORD_SEAL'})
        return payload

    def json(self, relative):
        return json.loads(self.payload(relative))

    def table(self, version, filename):
        relative = f'13_AGGREGATE_ADDENDUM/{version}/{filename}'
        payload = self.payload(relative)
        rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
        next(r for r in self.rows if r['source'] == '<ADDENDUM_ROOT>/'+relative)['csv_data_rows'] = len(rows)
        source_hash = self.pins[relative]['sha256']
        return [{**row, 'evaluator_version': version, 'source_table': '<ADDENDUM_ROOT>/'+relative,
                 'source_table_row': index+2, 'source_sha256': source_hash} for index, row in enumerate(rows)]


def validate_terminal(final):
    required = {'terminal_status': 'PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE',
        'native_terminal_count': 495, 'evaluation_terminal_count': 990, 'archive_pending': 0,
        'native_retry_count': 0, 'evaluator_retry_count': 0, 'core_solver_calls': 0, 'core_evaluator_calls': 0,
        'data_mode': 'semisynthetic', 'synthetic_data_used': False, 'semisynthetic_data_used': True,
        'trace_used_online': False}
    for key, expected in required.items():
        if type(final.get(key)) is not type(expected) or final[key] != expected:
            raise ValueError('Incomplete or inconsistent terminal field: '+key)
    native = final['native_status_counts']
    evaluated = final['evaluation_status_counts']
    if (set(native)-{'COMPLETED', 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'}
            or sum(native.values()) != 495
            or set(evaluated)-{'COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE'}
            or sum(evaluated.values()) != 990
            or evaluated.get('COMPLETED', 0) != 2*native.get('COMPLETED', 0)
            or evaluated.get('NOT_RUN_ALGORITHM_FAILURE', 0) != 2*native.get('ALGORITHM_FAILURE_ALL_YAW_REJECTED', 0)):
        raise ValueError('Native/evaluation terminal partitions do not close')


def combine_summaries(finite, failures, *, duration):
    dimensions = ('case_family', 'duration_s') if duration else ('family',)
    def key(row):
        return tuple(row.get(k) for k in ('comparison', 'metric_name', *dimensions))
    lookup = {key(row): row for row in failures if duration or row['scope'] == 'family'}
    output = []
    for row in finite:
        if not duration and row['scope'] != 'family':
            continue
        failure = lookup.pop(key(row))
        output.append({**{k: row[k] for k in SUMMARY_FIELDS if k in row},
            **{k: failure[k] for k in FAILURE_FIELDS if k in failure},
            **{k: row[k] for k in ('evaluator_version', 'source_table', 'source_table_row', 'source_sha256')},
            'failure_source_table': failure['source_table'], 'failure_source_table_row': failure['source_table_row'],
            'failure_source_sha256': failure['source_sha256']})
    if lookup:
        raise ValueError('Finite and failure-aware summary identity sets differ')
    return output


def prepare(stage):
    evidence = Evidence(stage)
    validate_terminal(evidence.final)
    original_freeze = evidence.json('00_PREREGISTRATION/EXECUTION_FREEZE.json')
    if evidence.final.get('active_execution_freeze'):
        active = Path(evidence.final['active_execution_freeze'])
        if not active.is_relative_to(Path(stage)):
            raise ValueError('Active continuation freeze escapes the addendum stage')
        freeze = evidence.json(active.relative_to(stage).as_posix())
        if (freeze.get('original_execution_code_commit') != original_freeze['code_commit']
                or freeze.get('original_native_reused_count') != 99
                or freeze.get('original_completed_evaluation_reused_count') != 1
                or freeze.get('historical_full_file_derived_seal_available') is not False):
            raise ValueError('Continuation provenance differs from the registered BOM recovery')
        evidence.payload((active.parent/'ADDENDUM_METRIC_WORDING_ERRATUM.md').relative_to(stage).as_posix())
        evidence.payload((active.parent/'CURRENT_POST_STOP_EVALUATION_SNAPSHOT.json').relative_to(stage).as_posix())
        if freeze.get('prior_bom_code_commit'):
            for key, expected in (('io_native_reused_count', 99), ('io_evaluation_reused_count', 198),
                                  ('io_verified_archive_reused_count', 54)):
                if freeze.get(key) != expected or evidence.final.get(key) != expected:
                    raise ValueError('Archive continuation reuse count differs: '+key)
            prior = evidence.json('CONTINUATIONS/BOM_RECOVERY_20260913/EXECUTION_FREEZE.json')
            if (prior != freeze['prior_bom_execution_freeze'] or prior['code_commit'] != freeze['prior_bom_code_commit']
                    or freeze.get('numerical_sources_unchanged_from_bom_commit') is not True):
                raise ValueError('Archive and BOM continuation provenance differs')
            evidence.payload((active.parent/'INTERRUPT_SCENE_SNAPSHOT.json').relative_to(stage).as_posix())
    else:
        freeze = original_freeze
    contract_payload = evidence.payload('00_PREREGISTRATION/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml')
    contract = yaml.safe_load(contract_payload)
    if (digest(contract_payload) != freeze['contract_hash']
            or evidence.final['contract_hash'] != freeze['contract_hash']
            or evidence.final['code_commit'] != freeze['code_commit']
            or freeze['remote_commit'] != freeze['code_commit']):
        raise ValueError('Contract, execution commit and pushed freeze identities differ')
    evidence.payload('00_PREREGISTRATION/ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md')
    mapping_payload = evidence.payload('00_PREREGISTRATION/NATIVE_IDENTITY_MAPPING.csv')
    mapping = list(csv.DictReader(io.StringIO(mapping_payload.decode())))
    if len(mapping) != 495 or len({r['run_id'] for r in mapping}) != 495:
        raise ValueError('Native/outer identity mapping is incomplete')
    for name in ('PRE', 'POST'):
        result = evidence.json('01_CHECKPOINTS/'+name+'/CHECKPOINT_RESULT.json')
        audit = evidence.json('01_CHECKPOINTS/'+name+'/CHECKPOINT_STRACE_AUDIT.json')
        if result.get('passed_count') != 22 or audit.get('passed') is not True:
            raise ValueError('The raw integrity checkpoint did not close: '+name)
    companion = {name: [] for name in ('PAIRWISE_FAMILY', 'PAIRWISE_DURATION', 'SEED_SIGNS', 'FAILURE_COUNTS',
        'METHOD_SUMMARY', 'METHOD_SUMMARY_DURATION', 'H1_CONTRASTS', 'H1_SUMMARY', 'H1_COMPONENTS',
        'H2_CASES', 'H2_SUMMARY', 'H3_SEED_SIGNS')}
    decisions = {}
    expected_cases = {r['case_id'] for r in contract['case_rows']}
    expected_methods = set(contract['runtime']['profiles'])
    expected_pairs = {r['comparison'] for r in contract['statistics']['pair_definitions']}
    metrics = set(contract['statistics']['primary_metrics']+contract['statistics']['secondary_metrics'])
    for version in ('v3', 'v2'):
        root = '13_AGGREGATE_ADDENDUM/'+version+'/'
        unique = evidence.table(version, 'UNIQUE_EVALUATION_RESULTS.csv')
        logical = evidence.table(version, 'LOGICAL_EVALUATION_RESULTS.csv')
        expected = {(c, m) for c in expected_cases for m in expected_methods}
        if (len(unique) != 495 or {(r['case_id'], r['method_id']) for r in unique} != expected
                or len(logical) != 585 or len({(r['case_id'], r['method_id']) for r in logical}) != 585):
            raise ValueError('Unique or logical addendum matrix identity is incomplete')
        if any(r['data_mode'] != 'semisynthetic' or r['semisynthetic_data_used'].lower() != 'true'
               or r['synthetic_data_used'].lower() != 'false' for r in unique+logical):
            raise ValueError('Addendum data-role disclosure differs from registration')
        status = evidence.json(root+'FINAL_EVALUATION_SUMMARY.json')
        decisions[version] = evidence.json(root+'HYPOTHESIS_DECISIONS.json')
        if decisions[version] != status['hypotheses']:
            raise ValueError('Hypothesis decision copies disagree')
        family = combine_summaries(evidence.table(version, 'PAIRWISE_SUMMARY.csv'),
                                   evidence.table(version, 'FAILURE_AWARE_PAIRWISE_SUMMARY.csv'), duration=False)
        duration = combine_summaries(evidence.table(version, 'PAIRWISE_BY_DURATION.csv'),
                                     evidence.table(version, 'FAILURE_AWARE_PAIRWISE_BY_DURATION.csv'), duration=True)
        if (len(family) != 112 or {(r['family'], r['comparison'], r['metric_name']) for r in family}
                != {(f, p, m) for f in ('A1', 'A2') for p in expected_pairs for m in metrics}):
            raise ValueError('All eight pairs and seven metrics are required for both families')
        groups = {(r['case_family'], str(r['duration_s'])) for r in contract['case_rows']}
        if (len(duration) != 280 or {(r['case_family'], r['duration_s'], r['comparison'], r['metric_name']) for r in duration}
                != {(f, d, p, m) for f, d in groups for p in expected_pairs for m in metrics}
                or any(r['total_case_count'] != '9' for r in duration)):
            raise ValueError('All five duration groups require nine registered paired cases')
        companion['PAIRWISE_FAMILY'].extend(family)
        companion['PAIRWISE_DURATION'].extend(duration)
        for name, filename in (
            ('SEED_SIGNS', 'SEED_SIGNS.csv'), ('FAILURE_COUNTS', 'FAILURE_COUNTS.csv'),
            ('METHOD_SUMMARY', 'UNIQUE_METHOD_SUMMARY.csv'), ('METHOD_SUMMARY_DURATION', 'METHOD_SUMMARY_BY_DURATION.csv'),
            ('H1_CONTRASTS', 'H1_CROSS_GROUP_PAIRWISE_CASE_LEVEL.csv'), ('H1_SUMMARY', 'H1_CROSS_GROUP_PAIRWISE_SUMMARY.csv'),
            ('H1_COMPONENTS', 'H1_COMPONENT_DECISIONS.csv'), ('H2_CASES', 'H2_MATCHED_FAMILY_CASE_LEVEL.csv'),
            ('H2_SUMMARY', 'H2_MATCHED_FAMILY_SUMMARY.csv'), ('H3_SEED_SIGNS', 'H3_SEED_SIGNS.csv')):
            rows = evidence.table(version, filename)
            if name == 'SEED_SIGNS' and len(rows) != 45*8*7:
                raise ValueError('Per-case pair signs must include unavailable/failed cases')
            companion[name].extend(rows)
        definitions = evidence.json(root+'FIELD_DEFINITIONS.json')
        if definitions.get('original_preregistered_field_definitions') != contract['field_definitions']:
            raise ValueError('Original metric wording must remain available beside the erratum')
        effective = {key: definitions[key] for key in contract['field_definitions']}
        if version == 'v3':
            contract['report_effective_field_definitions'] = effective
        elif effective != contract['report_effective_field_definitions']:
            raise ValueError('v3/v2 metric field definitions disagree')
    return evidence, freeze, contract, companion, decisions


def paired_markdown(rows, duration):
    headings = ['Evaluator', 'Family', 'Duration (s)', 'Pair', 'Metric', 'Median delta', 'Median 95% CI',
                'Mean delta', 'Mean 95% CI', 'Finite N', 'Finite win rate', 'Wilcoxon p', 'Failure-aware win rate', 'Failure-aware N']
    body = []
    for row in rows:
        body.append([row['evaluator_version'], row.get('case_family') if duration else row['family'],
            row.get('duration_s', 'ALL'), row['comparison'], row['metric_name'],
            row.get('median_delta_candidate_minus_reference'),
            '['+cell(row.get('median_ci95_low'))+', '+cell(row.get('median_ci95_high'))+']',
            row.get('mean_delta_candidate_minus_reference'),
            '['+cell(row.get('mean_ci95_low'))+', '+cell(row.get('mean_ci95_high'))+']',
            row['paired_sample_count'], row.get('win_rate'), row.get('wilcoxon_p'),
            row.get('failure_aware_win_rate'), row.get('failure_aware_comparable_count')])
    return md_table(headings, body)


def report_text(evidence, freeze, contract, companion, decisions):
    final = evidence.final
    output = ['# Addendum families A1/A2 results\n', contract['label']+'\n',
        'Terminal: `'+final['terminal_status']+'`. Native terminals: `495`; v3/v2 evaluator terminal identities: `990`; '
        'archive pending: `0`. Native calls repeated: `0`; evaluator calls repeated: `0`; core solver calls: `0`; core evaluator calls: `0`.\n',
        'The evidence comes only from `<ADDENDUM_ROOT> = <CLEAN_ROOT>/stages/'+STAGE_NAME+'`. '
        'The 541-core aggregate tables are unchanged. v3 is primary; v2 is parallel. '
        'Data mode: `semisynthetic`; `synthetic_data_used=false`; `semisynthetic_data_used=true`; `trace_used_online=false`.\n',
        '## Registration and execution identities\n',
        md_table(['Field', 'Frozen value'], [
            ['Preregistered date', contract['preregistered_date']], ['Contract commit', freeze['contract_commit']],
            ['Contract SHA-256', freeze['contract_hash']], ['Execution/code commit', freeze['code_commit']],
            ['Original native execution commit', freeze.get('original_execution_code_commit', freeze['code_commit'])],
            ['BOM bookkeeping commit', freeze.get('prior_bom_code_commit', freeze['code_commit'])],
            ['Pushed code commit at launch', freeze['remote_commit']],
            ['Executable SHA-256', contract['runtime']['executable']['sha256']],
            ['Evaluator SHA-256', contract['evaluation']['evaluator']['sha256']],
            ['Sensor-model SHA-256', contract['runtime']['model']['sha256']],
            ['Final status SHA-256', digest(evidence.final_bytes)], ['Final record seal SHA-256', digest(evidence.seal_bytes)],
            ['PRE raw checkpoint', 'PASS 22/22'], ['POST raw checkpoint', 'PASS 22/22']]),
        'Outer identities `ADD_RUN_00001`–`ADD_RUN_00495` and the D61/D62 case registry are authoritative. '
        'Native loader tokens `RUN_06001`–`RUN_06495` / `D01_seed_00`–`D01_seed_08` are compatibility metadata; '
        '`native_case_token_has_scientific_meaning=false`. '
        '[Native transport companion](clean6/ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md).\n',
        '## Terminal and failure counts\n',
        md_table(['Layer', 'Terminal status', 'Count'],
                 [['native', k, final['native_status_counts'].get(k, 0)] for k in ('COMPLETED', 'ALGORITHM_FAILURE_ALL_YAW_REJECTED')]
                 + [['v3 + v2 evaluator identities', k, final['evaluation_status_counts'].get(k, 0)]
                    for k in ('COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE')]),
        'BOM bookkeeping continuation: original native terminals reused `'+str(final.get('original_native_reused_count', 0))+
        '`; original completed evaluator terminal reused `'+str(final.get('original_completed_evaluation_reused_count', 0))+
        '`. The original stop is preserved; original evaluator files were verified unchanged before the registered archive/cleanup. '
        'The first evaluator output had no historical completed derived-metric seal; '
        'its current post-stop snapshot is labelled separately. Native and evaluator invocations were not repeated.\n',
        'Archive I/O bookkeeping continuation: native terminals reused `'+str(final.get('io_native_reused_count', 0))+
        '`; evaluator terminals reused `'+str(final.get('io_evaluation_reused_count', 0))+
        '`; published verified archives reused `'+str(final.get('io_verified_archive_reused_count', 0))+
        '`. This count is a separate reuse layer, not additional scientific execution. '
        'The prior interruption and resource history are preserved.\n',
        '[Execution bookkeeping notes](clean6/ADDENDUM_EXECUTION_NOTES.md) preserve the BOM stop, archive-accounting interruption, '
        'and pre-import launcher failure; the launcher failure involved zero scientific calls.\n',
        'Algorithm-failure evaluator identities retain `NOT_RUN_ALGORITHM_FAILURE`; those identities do not assert an evaluator process invocation. '
        'The following table copies native counts from the v3 aggregate; the full companion preserves both table versions.\n',
        md_table(['Family', 'Duration (s)', 'Configuration', 'Native status', 'Count'],
                 [[r['case_family'], r['duration_s'], r['method_id'], r['terminal_status'], r['run_count']]
                  for r in companion['FAILURE_COUNTS'] if r['evaluator_version'] == 'v3']),
        '## Preregistered hypothesis decisions\n',
        md_table(['Evaluator', 'H1', 'H2', 'H3', 'full_vs_no_Go2 case–metric harm rows', 'H3 unavailable rows'],
                 [[v, decisions[v]['H1'], decisions[v]['H2'], decisions[v]['H3'],
                   decisions[v]['H3_harm_count'], decisions[v]['H3_missing_count']] for v in ('v3', 'v2')]),
        'These are the stored operational decision codes. The component decisions, twenty HV/no-HV contrasts, '
        'matched A2-minus-A1 differences and every H3 seed sign are copied in the companion tables; no hypothesis is re-rated here.\n',
        '## All eight registered pairings, by family\n',
        'Delta is candidate minus reference. The tables copy full stored precision. Blank or unavailable source values display as `UNAVAILABLE`. '
        'Finite statistics retain only successful finite pairs; failure-aware rates retain their separately registered denominator. '
        'The source row, source SHA-256, failure counts, bootstrap settings and Wilcoxon policy are retained in the CSV companions.\n',
        paired_markdown(companion['PAIRWISE_FAMILY'], False),
        '## All eight registered pairings, by duration\n',
        'Each registered family/duration group contains nine cases. No duration group is pooled into the 541-core tables.\n',
        paired_markdown(companion['PAIRWISE_DURATION'], True),
        '## Metric definitions\n',
        md_table(['Metric', 'Effective inherited/registered definition'], list(contract['report_effective_field_definitions'].items())),
        '[Metric wording erratum](clean6/ADDENDUM_METRIC_WORDING_ERRATUM.md) preserves the original contract wording alongside '
        'the inclusive inherited fault-RMSE endpoint and half-open new derived-metric endpoints. The erratum changes no numerical operation.\n',
        'No NAV, error-series metric, bootstrap interval, Wilcoxon statistic, or hypothesis decision was recomputed by this report generator. '
        'The source aggregates retain the original native/evaluator outcomes and explicit unavailable fields.\n',
        '## Complete portable companions\n']
    labels = {'SEED_SIGNS': 'All eight pairings, seven metrics and every case/seed sign, including failures',
              'H1_CONTRASTS': 'All twenty HV/no-HV contrasts at finite case level',
              'H1_SUMMARY': 'All twenty HV/no-HV contrast summaries',
              'H1_COMPONENTS': 'H1 benefit and duration-trend component decisions',
              'H2_CASES': 'H2 matched A2-minus-A1 case differences', 'H2_SUMMARY': 'H2 family/duration summaries',
              'H3_SEED_SIGNS': 'H3 every duration/seed sign and unavailable classification'}
    output.append(md_table(['Companion', 'Rows', 'Content'], [[
        '['+name+'](clean6/'+COMPANION_PREFIX+name+'.csv)', len(rows), labels.get(name, name)]
        for name, rows in companion.items()]))
    output.extend(['## Source table hashes\n',
        md_table(['Source alias', 'SHA-256', 'Bytes', 'CSV data rows'],
                 [[r['source'], r['sha256'], r['size_bytes'], r['csv_data_rows']] for r in evidence.rows]),
        '[Machine-readable source inventory](clean6/'+COMPANION_PREFIX+'EVIDENCE.csv). '
        'CSV `source_table_row` values are one-based physical line numbers including the header. '
        'Aliases keep machine-local paths out of tracked report material.\n'])
    return '\n'.join(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--stage')
    parser.add_argument('--report')
    parser.add_argument('--companions-dir')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args(argv)
    paths = yaml.safe_load(Path(args.local_config).read_text())['paths']
    code = Path(paths['code_root'])
    stage = Path(args.stage) if args.stage else Path(paths['clean_root'])/'stages'/STAGE_NAME
    report = Path(args.report) if args.report else code/'docs/paper_rebuild/ADDENDUM_FAMILIES_A1_A2_RESULTS.md'
    companions = Path(args.companions_dir) if args.companions_dir else code/'docs/paper_rebuild/clean6'
    evidence, freeze, contract, tables, decisions = prepare(stage)
    summary = {'status': 'VALIDATED', 'native_terminals': 495, 'evaluation_terminals': 990,
               'hypotheses': decisions, 'companion_rows': {k: len(v) for k, v in tables.items()},
               'contract_hash': freeze['contract_hash'], 'code_commit': freeze['code_commit']}
    if args.validate_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    payloads = {companions/(COMPANION_PREFIX+name+'.csv'): csv_bytes(rows) for name, rows in tables.items()}
    payloads[companions/(COMPANION_PREFIX+'EVIDENCE.csv')] = csv_bytes(evidence.rows)
    payloads[report] = report_text(evidence, freeze, contract, tables, decisions).encode('utf-8')
    substitutions = [(str(stage), '<ADDENDUM_ROOT>')]
    substitutions += [(str(paths[key]), alias) for key, alias in (
        ('addendum_a1_a2_scratch', '<ADDENDUM_SCRATCH>'), ('clean_root', '<CLEAN_ROOT>'),
        ('raw_root', '<RAW_ROOT>'), ('code_root', '<CODE_ROOT>'),
        ('handoff_root', '<HANDOFF_ROOT>')) if key in paths]
    for path, payload in list(payloads.items()):
        text = payload.decode('utf-8')
        for local, alias in substitutions:
            text = text.replace(local, alias)
        if '/home/' in text or '/mnt/' in text:
            raise ValueError('Unresolved machine-local path in portable report output: '+str(path))
        payloads[path] = text.encode('utf-8')
        if path.exists() or path.is_symlink():
            raise FileExistsError('Refusing to overwrite an existing report artifact: '+str(path))
    for path, payload in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(payload)
    summary.update(status='REPORT_WRITTEN', report=str(report), report_sha256=digest(payloads[report]),
                   companion_file_count=len(payloads)-1, metric_recomputation_performed=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
