"""Transport addendum identities around the unchanged P-09c native/evaluator calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ..clean5_degradation.common import write_json, resolve
from ..clean6_canonical_v2.runtime import run_one
from ..clean6_canonical_v2.evaluation import one_evaluation
from ..manifest import sha256_file
from .aggregate import outage_metrics


def native_template(source):
    """Keep loader-only native identity tokens; outer IDs identify actual inputs.

    The frozen native loader accepts RUN_##### and C00 or D01..D60 case tokens,
    and couples C00 to real_clean. D61/D62 and ADD_RUN identifiers cannot be
    passed through that closed schema without changing the locked binary.
    RUN_06001..RUN_06495 and D01_seed_00..08 are reserved compatibility tokens.
    New provider hashes, actual opened input paths, outer registry, run folder,
    case metadata and addendum data mode identify each newly executed run.
    These tokens do not identify scientific core D01 cases or reused results.
    """
    path = Path(source['runtime_config_path'])
    if sha256_file(path) != source['runtime_config_file_hash']:
        raise ValueError('Frozen native method template changed')
    original = path.read_text()
    before = yaml.safe_load(original)
    import re
    if (not re.fullmatch(r'RUN_\d{5}', before['run_id']) or before['run_label'] != before['run_id']
            or before['case_id'] != 'C00_clean_normal' or before['data_mode'] != 'real_clean'):
        raise ValueError('Expected original accepted C00 loader compatibility tokens')
    match = re.fullmatch(r'ADD_RUN_(\d{5})', source['run_id'])
    seed_index = source.get('seed_index', source['case_id'].split('_')[-2]+'_'+source['case_id'].split('_')[-1])
    if (not match or not 1 <= int(match[1]) <= 495 or not re.fullmatch(r'seed_0[0-8]', seed_index)
            or not re.fullmatch(r'D6[12]_(?:10|20|30)s_'+re.escape(seed_index), source['case_id'])):
        raise ValueError('Outer addendum identity has no reserved native token mapping')
    native_run = 'RUN_'+str(6000+int(match[1])).zfill(5)
    replacements = {'run_id': native_run, 'run_label': native_run,
                    'case_id': 'D01_'+seed_index, 'data_mode': 'real_base_controlled_degradation'}
    counts = {key: 0 for key in replacements}
    lines = []
    for line in original.splitlines(keepends=True):
        key = line.split(':', 1)[0]
        if key in replacements:
            counts[key] += 1
            line = key+': '+json.dumps(replacements[key])+('\n' if line.endswith('\n') else '')
        lines.append(line)
    if any(n != 1 for n in counts.values()):
        raise ValueError('Native transport identity keys missing or duplicated')
    transported = ''.join(lines)
    after = yaml.safe_load(transported)
    if set(after) != set(before) or any(before[k] != after[k] for k in before if k not in replacements):
        raise ValueError('Native identity transport changed nontransport parameters')
    native = {key: after[key] for key in ('run_id', 'run_label', 'case_id', 'data_mode', 'stage_id')}
    return transported, {'original_template_sha256': source['runtime_config_file_hash'],
        'transported_template_sha256': hashlib.sha256(transported.encode()).hexdigest(),
        'transport_changed_fields': replacements, 'native_case_token_has_scientific_meaning': False,
        'native_identity': native, 'outer_identity': {'run_id': source['run_id'], 'case_id': source['case_id'],
            'data_mode': 'semisynthetic', 'method_id': source.get('method_id')}, 'scientific_changes': [],
        'loader_source_contract': 'port_config_loader.cpp isCanonical541MatrixRunId/isCanonical541CaseId/canonical541_data_mode_matches',
        'native_schema_note': 'Reserved loader tokens only; outer registry and actual provider/open-audit hashes identify addendum run',
        'C00_execution_or_evidence_claim': False, 'core_D01_execution_or_evidence_claim': False, 'core_run_reused': False}


def solve(source, bundle, case, contract, reg, root, code_commit):
    text, transport = native_template(source)
    meta = {**case, 'degradation_parameters_json': json.dumps({'start_s': case['outage_start_s'],
        'end_s': case['outage_end_s'], 'duration_s': case['duration_s']})}
    record = run_one(source, bundle, contract, reg, root, code_commit, original_text=text, case_meta=meta)
    record['native_adapter_protocol_id'] = record['protocol_id']
    record.update(protocol_id=contract['protocol_id'], native_template_transport=transport,
                  duration_s=case['duration_s'], **contract['data_roles'])
    return record


def finish_evaluation(row, record, contract, code_commit):
    """Complete new addendum sidecars from an existing terminal; no evaluator call."""
    row = dict(row)
    row.update(duration_s=record['duration_s'], **contract['data_roles'])
    row['derived_metrics_code_commit'] = code_commit
    folder = Path(row['evaluation_output_root'])
    for name in ('ADDENDUM_DERIVED_METRICS.json', 'ADDENDUM_EVALUATION_RESULT.json', 'EVALUATION_OUTPUT_SEAL.json'):
        if (folder/name).exists() or (folder/name).is_symlink():
            raise FileExistsError('Addendum sidecar already exists; no overwrite: '+name)
    if row['evaluation_status'] == 'COMPLETED':
        case = record['case_meta']
        metrics = outage_metrics(row['error_series_source'], case['outage_start_s'], case['outage_end_s'])
        row.update(metrics)
        write_json(folder/'ADDENDUM_DERIVED_METRICS.json', metrics)
    else:
        row.update(outage_end_horizontal_error_m=None, max_horizontal_error_in_window_m=None,
                   outage_metric_status='UNAVAILABLE_'+row['evaluation_status'])
    # Preserve frozen evaluator and adapter files; this exclusive sidecar carries
    # the registered addendum classification and full-rate-derived metrics.
    write_json(folder/'ADDENDUM_EVALUATION_RESULT.json', row)
    write_json(folder/'EVALUATION_OUTPUT_SEAL.json', {'status': 'SEALED_AFTER_DERIVED_METRICS',
        **{key: row[key] for key in ('original_completed_evaluation_reused',
            'historical_full_file_derived_seal_available', 'current_post_stop_snapshot') if key in row},
        'files': {p.relative_to(folder).as_posix(): {'sha256': sha256_file(p), 'size_bytes': p.stat().st_size}
                  for p in sorted(folder.rglob('*')) if p.is_file()}})
    return row


def evaluate(record, version, contract, reg, root, code_commit):
    folder = Path(root)/'12_OFFLINE_EVALUATION'/version/record['run_id']
    if folder.exists() or folder.is_symlink():
        raise FileExistsError('Evaluation output exists; evaluator must never be invoked again')
    marker = resolve(contract['stage_root'], reg)/'01_EVALUATION_CALLS'/version/(record['run_id']+'.json')
    write_json(marker, {'run_id': record['run_id'], 'evaluator_version': version,
        'code_commit': code_commit, 'native_execution_code_commit': record['code_commit'],
        'role': 'EXCLUSIVE_FIRST_EVALUATION_ADAPTER_ATTEMPT', 'repeat_authorized': False,
        'evaluator_invocation_planned': record['terminal_status'] == 'COMPLETED',
        'evaluation_output_root': str(folder)})
    row = one_evaluation(record, version, contract, reg, root, code_commit)
    return finish_evaluation(row, record, contract, code_commit)
