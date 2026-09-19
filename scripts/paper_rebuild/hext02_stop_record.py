#!/usr/bin/env python3
"""Read-only scientific evidence closeout after the mandatory evaluator stop.

No solver, evaluator, parameter adjustment, full aggregate, or figure rendering.
Only existing outputs, failed evidence, counters, and missing-NAV facts are sealed.
"""
import csv
import json
import os
from pathlib import Path
import shutil

os.environ['GIT_OPTIONAL_LOCKS'] = '0'
from legsa_gins.paper_rebuild.hext import execution as io
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths, alias_path
from legsa_gins.paper_rebuild.hext.figures import verify_frozen_v21
from legsa_gins.paper_rebuild.hext.legsa_gap_diagnostic import run_legsa_gap_diagnostic


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def main():
    seq, scratch, archive = io.stage_roots()
    freeze = io.assert_freeze()
    root = scratch / '99_HARD_STOP'
    root.mkdir(exist_ok=False)
    failed_run = 'BY2H__EXT05C-S__FILE_START'
    failed_relative = Path('07_OFFLINE_EVALUATION/v3') / failed_run
    failed_output = scratch / failed_relative / 'EXACT_EVALUATOR_OUTPUT'
    capture = json.loads((failed_output / 'EVALUATOR_CAPTURE.json').read_text())
    audit = json.loads((failed_output / 'EVALUATOR_STRACE_AUDIT.json').read_text())
    if capture['consistency']['passed'] is not False or audit['passed'] is not False:
        raise RuntimeError('Expected recorded evaluator failure; never reinterpret as success')
    journal = [json.loads(line) for line in (scratch / 'EXECUTION_JOURNAL.jsonl').read_text().splitlines()]
    counts = {name: sum(r['event'] == name for r in journal) for name in (
        'NATIVE_LAUNCH', 'NATIVE_COMPLETED_ARCHIVED', 'EVALUATOR_LAUNCH', 'EVALUATOR_COMPLETED_ARCHIVED')}
    if list(counts.values()) != [14, 14, 17, 16]:
        raise RuntimeError('Hard-stop invocation counters changed')
    # Preserve the sole failed evaluator and its v3 input exactly, never rerun it.
    io.archive_batch(scratch / failed_relative, archive / failed_relative, scratch / 'ARCHIVE_LEDGER.jsonl', 'FAILED_EVALUATOR_17')
    v3_relative = Path('06_V3_NAV_INPUTS') / failed_run
    io.archive_batch(scratch / v3_relative, archive / v3_relative, scratch / 'ARCHIVE_LEDGER.jsonl', 'FAILED_EVALUATOR_17_V3_INPUT')
    records = json.loads((scratch / 'NATIVE_EXECUTION_RECORDS.json').read_text())
    ledger, gaps, geometry, native_audits = [], [], [], []
    for record in records:
        native = json.loads(Path(record['native_summary_path']).read_text())
        geom = native['geometric_audit']
        geometry.append(dict(sequence_id=record['sequence_id'], method_id=record['configuration_id'], start_convention=record['start_mode'],
            status=geom['terminal_status'], median_yaw_difference_deg=geom.get('median_absolute_iekf_vs_geometric_yaw_difference_deg', 'UNAVAILABLE'),
            p95_yaw_difference_deg=geom.get('p95_absolute_iekf_vs_geometric_yaw_difference_deg', 'UNAVAILABLE'),
            median_3d_direction_deg=geom.get('median_measured_vs_estimated_3d_direction_angle_deg', 'UNAVAILABLE'),
            p95_3d_direction_deg=geom.get('p95_measured_vs_estimated_3d_direction_angle_deg', 'UNAVAILABLE'),
            error=geom.get('error',''), source=alias_path(Path(record['native_summary_path']),seq)))
        for gap in json.loads(Path(record['gap_log_path']).read_text())['gaps']:
            gaps.append(dict(sequence_id=record['sequence_id'], method_id=record['configuration_id'], start_convention=record['start_mode'], **gap))
        native_audits.append(json.loads((archive / '04_ACCESS_AUDITS' / (record['run_id'] + '.json')).read_text()))
        for version in ('v3','v2'):
            evaluation = archive / '07_OFFLINE_EVALUATION' / version / record['run_id']
            result_path = evaluation / 'EVALUATION_RESULT.json'
            row = dict(sequence_id=record['sequence_id'], method_id=record['configuration_id'], start_convention=record['start_mode'],
                       version=version, status='NOT_RUN_HARD_STOP', trace_open_count=0, source=alias_path(evaluation,seq), source_sha256='UNAVAILABLE')
            if result_path.is_file():
                result = json.loads(result_path.read_text())
                if not result['audit']['passed']:
                    raise RuntimeError('Completed result has a failed gate')
                row.update(status='COMPLETED', trace_open_count=1, source=alias_path(result_path,seq), source_sha256=io.sha256_file(result_path))
            elif record['run_id'] == failed_run and version == 'v3':
                row.update(status='FAILED_EVALUATOR_CONSISTENCY', trace_open_count=1,
                           source_sha256=io.sha256_file(evaluation / 'EXACT_EVALUATOR_OUTPUT/EVALUATOR_STRACE_AUDIT.json'))
            ledger.append(row)
    if not all(r['passed'] and r['trace_bag_fpl_open_count'] == 0 for r in native_audits):
        raise RuntimeError('Completed native access audit failed')
    write_csv(root / 'EVALUATION_LEDGER.csv', ledger)
    write_csv(root / 'GAP_EVENTS.csv', gaps)
    write_csv(root / 'GEOMETRIC_AUDIT.csv', geometry)
    # This requested fail-soft item only checks frozen table/NAV availability.
    diagnostic = run_legsa_gap_diagnostic(stage_root=scratch, code_commit=freeze['code_freeze'])
    io.archive_batch(scratch / '09_LEGSA_GAP_DIAGNOSTIC', archive / '09_LEGSA_GAP_DIAGNOSTIC', scratch / 'ARCHIVE_LEDGER.jsonl', 'READ_ONLY_MISSING_NAV_CLOSEOUT')
    for name in ('BY2','BY2H','BY2O'):
        io.raw_checkpoint(load_sequence_paths(name), root / (name + '_RAW_POST_STOP.json'))
    before = json.loads((scratch / '03_PREREG/PREFLIGHT/FROZEN_FIGURES_PRE.json').read_text())
    after = verify_frozen_v21(before, seq.clean_root / 'stages/CLEAN6_PUBLICATION_FIGURES/figures/v21')
    io.write_json(root / 'FROZEN_FIGURES_POST_STOP.json', after)
    io.assert_freeze()
    pure_io = (audit['exit_code'] == 0 and audit['trace_open_count'] == 1 and audit['write_scope']['pass']
               and capture['trace_sha256'] == load_sequence_paths('BY2H').trace_sha256 and capture['trace_handle_hash_count'] == 1)
    report = dict(status='HARD_STOP_EVALUATOR_CONSISTENCY', full_task_completed=False, code_freeze=freeze['code_freeze'],
        failed_run_id=failed_run, failed_version='v3',
        budget=dict(comparison_native_attempted=14, comparison_native_completed=14, prereg_identity_native=2,
                    evaluator_attempted=17,evaluator_passed=16,evaluator_failed=1,evaluator_not_run=11),
        failure=dict(consistency=capture['consistency'], capture_sha256=io.sha256_file(failed_output/'EVALUATOR_CAPTURE.json'),
                     audit_sha256=io.sha256_file(failed_output/'EVALUATOR_STRACE_AUDIT.json'),pure_io_passed=pure_io,
                     exit_code=audit['exit_code'],trace_open_count=audit['trace_open_count'],metrics_admitted=False),
        not_produced=['08_AGGREGATE complete tables','10_FIGURES/FIG02S'],
        figures_unchanged=True,scientific_code_unchanged=True,scientific_source_hashes=freeze['source_hashes'],
        trace_opens_by_sequence={'BY2':4,'BY2H':13,'BY2O':0}, native_trace_bag_fpl_opens=0,
        raw_trace_postcheck='21 payload SHA + one declared trace identity/size per sequence; BY2O evaluator handle verification NOT_RUN',
        readonly_diagnostic=diagnostic, geometric_precondition_failure='UNAVAILABLE statistics; preserve frozen baseline-horizontal-length guard, no epoch deletion',
        completed_by2_selector=dict(LC01_S_yaw_rmse_deg=1.5392385536245534,LC01_frozen_yaw_rmse_deg=2.9948274600591076,
                                   selected_configuration='S',three_sequence_result_delivery='NOT_COMPLETED'),
        no_retry=True,no_parameter_change=True,no_gate_relaxation=True,
        data_mode='real_partial_hard_stop_evidence',synthetic_data_used=False,semisynthetic_data_used=False,
        hashes={p.name:io.sha256_file(p) for p in root.iterdir() if p.is_file()})
    io.write_json(root / 'STOP_REPORT.json', report)
    for name in ('HARD_STOP_EVALUATE.json','HARD_STOP_NATIVE.json','BOOKKEEPING_CACHE_ADJUDICATION.json','EXECUTION_JOURNAL.jsonl','NATIVE_EXECUTION_RECORDS.json'):
        shutil.copyfile(scratch/name,root/name)
    io.archive_batch(root, archive / '99_HARD_STOP', scratch / 'ARCHIVE_LEDGER.jsonl', 'HARD_STOP_CLOSEOUT')
    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))


if __name__ == '__main__':
    main()
