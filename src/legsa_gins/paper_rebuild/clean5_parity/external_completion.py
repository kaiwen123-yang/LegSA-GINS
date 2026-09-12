"""One bounded completion of the two previously uninvoked external v3 evaluations.

Retain the partial aggregate byte-for-byte before publishing a full replacement.
No solver, provider generation, or completed evaluator invocation is repeated.
"""
from __future__ import annotations
import argparse
import copy
from dataclasses import replace
import json
from pathlib import Path
import shutil

import yaml

from ..manifest import sha256_file
from ..clean5_sequence.registry import load_registry
from ..clean5_sequence.solver_runner import execution_state
from ..clean5_sequence.evaluation_tables import CANONICAL_CSV_NAMES
from .evaluation import (EVALUATOR_SHA256, _resolve, _external_evaluate, _metrics, _csv,
    body_frame_bias, transform_nav, write_transformed_nav, write_version_tables,
    canonical, canonical_headers, write_json)
from .decomposition import build_decomposition

PINNED_INPUTS = {
    'P02_CONTINUED_TERMINAL.json':'69d35a380d6cd27c764d9ac2536f664e4bdb17a3851ee535489464389cee9886',
    '08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json':'0a53d5d529c243c0cd81dafe2be4df2bb299f9a009ec9bf5d2a0f7d5f46c3778',
    '04_PARITY_SEAL/PARITY_OUTPUT_SEAL_CONTINUED.json':'4196d3e188dcd556924fd36bd99d401f06270a9ac4a9d4141a827671563b06ce',
    '04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json':'94f90e213378665fbff9ef32e02fb20302ccd004ed1be5b327f7a4e9fff644fb',
    '02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json':'85b3ed069c30df31a78b2d64a1946721eb845c06dc840d51867ef92462f70e5c',
    '00_PARITY_TARGET_AND_AUDITS/A_TARGET_EXTRACTION.json':'63ad6db8a65aafb3730cdcb4342dcd0b3ba1fad88784719ba920755dca169790',
}
TRACE_SHA='ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c'
EXTERNAL_IDS=('LC01','EXT05C')


def _json(path):
    return json.loads(Path(path).read_text())


def _file(path):
    path=Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
        raise ValueError('Missing/symlink input '+str(path))
    return path


def _tree_hashes(root):
    root=Path(root)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):raise ValueError('Symlink aggregate root')
    result={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise ValueError('Symlink aggregate entry')
        if path.is_file():result[path.relative_to(root).as_posix()]=sha256_file(path)
    return result


def _exclusive_copy(source,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with _file(source).open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)


def preserve_aggregate(source, destination):
    """Snapshot every aggregate file, and verify exact pre/post copy hashes."""
    source,destination=Path(source),Path(destination)
    original=_tree_hashes(source)
    if not original:raise ValueError('No aggregate files to preserve')
    destination.mkdir(parents=True,exist_ok=False)
    for relative in original:_exclusive_copy(source/relative,destination/relative)
    if _tree_hashes(destination)!=original or _tree_hashes(source)!=original:
        raise RuntimeError('Aggregate changed while preserving partial results')
    return original


def publish_aggregate(*, current, prepared, preserved, expected_hashes, audit_root):
    """Publish only after complete current/preserved identity checks; retain checkpoint."""
    current,prepared,preserved,audit_root=map(Path,(current,prepared,preserved,audit_root))
    if _tree_hashes(current)!=expected_hashes or _tree_hashes(preserved)!=expected_hashes:
        raise RuntimeError('Original aggregate or preserved copy changed; publication refused')
    prepared_hashes=_tree_hashes(prepared)
    if set(prepared_hashes)!=set(expected_hashes):raise ValueError('Completed aggregate file set differs')
    changed=[name for name in expected_hashes if expected_hashes[name]!=prepared_hashes[name]]
    write_json(audit_root/'PRE_PUBLICATION_GATE.json',{'status':'PASS','original':expected_hashes,
        'prepared':prepared_hashes,'changed_files':changed,'preserved_copy':str(preserved)})
    for index,relative in enumerate(changed):
        # Recheck each destination immediately before replacement. Atomic rename
        # changes only an explicitly listed aggregate file, not runtime evidence.
        if sha256_file(current/relative)!=expected_hashes[relative]:raise RuntimeError('Aggregate destination changed')
        destination=current/relative
        temporary=destination.with_name(destination.name+'.external_completion_tmp')
        _exclusive_copy(prepared/relative,temporary)
        if sha256_file(temporary)!=prepared_hashes[relative]:raise RuntimeError('Prepared copy mismatch')
        temporary.replace(destination)
        write_json(audit_root/f'PUBLISH_CHECKPOINT_{index:02d}.json',
                   {'relative_path':relative,'sha256':sha256_file(destination),'original_preserved':True})
    if _tree_hashes(current)!=prepared_hashes or _tree_hashes(preserved)!=expected_hashes:
        raise RuntimeError('Published aggregate hash gate failed')
    return {'status':'PASS','changed_files':changed,'files_sha256':prepared_hashes,'original_files_sha256':expected_hashes}


def _validate_inputs(stage, *, include_summary=True):
    for relative,digest in PINNED_INPUTS.items():
        if not include_summary and relative.startswith('08_AGGREGATE/'):continue
        if sha256_file(_file(stage/relative))!=digest:raise ValueError('Pinned input changed: '+relative)
    terminal=_json(stage/'P02_CONTINUED_TERMINAL.json')
    if (terminal['status']!='PARTIAL' or terminal['run_count']!=8 or terminal['completed_runs']!=7
            or len(terminal['runs'])!=8 or any(r['terminal_status']!='COMPLETED' for r in terminal['runs'][:7])
            or terminal['runs'][-1]['variant_id']!='V2e'
            or terminal['runs'][-1]['terminal_status']!='FAILED_NATIVE_COUNTER_CONTRACT'):
        raise ValueError('Continued terminal is outside bounded external-completion scope')
    seal=_json(stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL_CONTINUED.json')
    if seal['records']!=terminal['runs']:raise ValueError('Continued run seal/terminal identity differs')
    for relative,digest in seal['files_sha256'].items():
        rel=Path(relative)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unconfined sealed input')
        if sha256_file(_file(stage/rel))!=digest:raise ValueError('Sealed runtime input changed: '+relative)
    bundle=_json(stage/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json')
    for item in bundle['variants'].values():
        for entry in item['providers'].values():
            if sha256_file(_file(entry['path']))!=entry['sha256']:raise ValueError('Frozen parity provider changed')
    return terminal,bundle


def _completion_scope(summary):
    """Accept exactly the two header-parser failures plus the registered V2e failure."""
    for version in ('v2','v3'):
        rows=summary['rows'][version]
        if len(rows)!=13 or len({r['run_id'] for r in rows})!=13:raise ValueError('Unexpected evaluation row identities')
        unavailable={r['run_id']:r for r in rows if r['evaluation_status']!='COMPLETED'}
        expected={'CLEAN5_PARITY_V2e_F01'} | (set(EXTERNAL_IDS) if version=='v3' else set())
        if set(unavailable)!=expected:raise ValueError('Evaluation failures exceed bounded completion scope')
        if not unavailable['CLEAN5_PARITY_V2e_F01']['unavailable_reason'].startswith('Solver unavailable: FAILED_NATIVE_COUNTER_CONTRACT'):
            raise ValueError('Unexpected V2e failure')
        if version=='v3' and any(unavailable[k]['unavailable_reason']!='NAV row parser disagreement' for k in EXTERNAL_IDS):
            raise ValueError('External evaluator may already have been invoked')


def complete_external(*, registry, stage_root, contract, code_commit):
    stage=Path(stage_root);settings=contract['evaluation']
    if any((stage/p).exists() for p in ('09_EXTERNAL_COMPLETION_AUDIT','07_OFFLINE_EVALUATION/v3/EXTERNAL_COMPLETION','P02_FINAL_TERMINAL.json')):
        raise FileExistsError('Bounded external completion already attempted; retry refused')
    state=execution_state(registry.code_root,code_commit)
    if (settings['v2_sha256']!=EVALUATOR_SHA256 or settings['trace_sha256']!=TRACE_SHA
            or settings['base_time']!=1772784000 or list(settings['window_seconds'])!=[66.,340.]):
        raise ValueError('Frozen evaluator identity/window/base_time mismatch')
    evaluator=_resolve(settings['evaluator_path'],registry)
    if sha256_file(_file(evaluator))!=EVALUATOR_SHA256:raise ValueError('Evaluator executable hash changed')
    trace=_resolve(settings.get('trace_path',registry.sequences['BY2'].trace_path),registry)
    if trace!=registry.sequences['BY2'].trace_path:raise ValueError('Trace path differs from BY2 registry')
    terminal,bundle=_validate_inputs(stage)
    summary=_json(stage/'08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json')
    if summary!=terminal['evaluation']:raise ValueError('Partial terminal and aggregate summary differ')
    _completion_scope(summary)
    if summary['baseline_median_m']!=bundle['baseline_median_m']:raise ValueError('Frozen baseline geometry differs')
    p01=_json(stage/'00_PARITY_TARGET_AND_AUDITS/A_TARGET_EXTRACTION.json')
    if p01['evaluator']['sha256']!=EVALUATOR_SHA256 or p01['evaluator']['trace_sha256']!=TRACE_SHA:
        raise ValueError('External frozen evaluator identity differs')
    audit=stage/'09_EXTERNAL_COMPLETION_AUDIT';completion=stage/'07_OFFLINE_EVALUATION/v3/EXTERNAL_COMPLETION'
    if audit.exists() or completion.exists() or (stage/'P02_FINAL_TERMINAL.json').exists():
        raise FileExistsError('Bounded external completion already attempted; retry refused')
    for method in EXTERNAL_IDS:
        if (stage/'07_OFFLINE_EVALUATION/v3/PER_RUN'/method).exists():
            raise ValueError('Original external evaluator directory already exists')
        prior=stage/'07_OFFLINE_EVALUATION/v3/NAV_INPUTS'/method
        if prior.exists() and (prior.is_symlink() or any(prior.iterdir())):
            raise ValueError('Original failed external transform directory is not empty')
    audit.mkdir();completion.mkdir()
    write_json(audit/'COMPLETION_STARTED.json',{'code_commit':code_commit,'code_state':state,'pinned_inputs':PINNED_INPUTS,
        'allowed_external_ids':list(EXTERNAL_IDS),'maximum_evaluator_invocations':2,'solver_invocations':0,
        'baseline_median_m':summary['baseline_median_m'],'trace_sha256':TRACE_SHA,'evaluator_sha256':EVALUATOR_SHA256})
    current=stage/'08_AGGREGATE';preserved=audit/'PRE_COMPLETION_AGGREGATE'
    original_hashes=preserve_aggregate(current,preserved)
    write_json(audit/'PRE_COMPLETION_AGGREGATE_HASHES.json',original_hashes)
    result=copy.deepcopy(summary);calls=0
    try:
        for method in EXTERNAL_IDS:
            source=p01['methods'][method]
            navpath=Path(source['source_table']).parent/source['method_id']/'EXACT_EVALUATOR_INPUT.nav'
            navhash=sha256_file(_file(navpath))
            if navhash!=source['continuity']['evaluator_nav_sha256']:raise ValueError('External NAV hash mismatch')
            nav=canonical._read_numeric_table(navpath).to_numpy(float)
            transformed=transform_nav(nav,summary['baseline_median_m'])
            root=completion/method;inputs=root/'NAV_INPUTS';inputs.mkdir(parents=True,exist_ok=False)
            transformed_path=inputs/'EVALUATOR_INPUT.nav'
            write_transformed_nav(navpath,transformed_path,transformed)
            write_json(inputs/'TRANSFORM_MANIFEST.json',{'evaluator_contract':'evaluator_contract_v3',
                'input_nav':str(navpath),'input_sha256':navhash,'output_sha256':sha256_file(transformed_path),
                'baseline_median_m':summary['baseline_median_m'],
                'lever_frd_m':[.03,.03-.5*summary['baseline_median_m'],-.30],
                'attitude_columns_zero_based':[8,9,10],'fit_used':False,'further_correction_used':False,
                'code_commit':code_commit,'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False,
                'uncertainty_status':'UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED'})
            evaluation_dir=root/'EXACT_EVALUATOR_OUTPUT'
            calls+=1
            evaluated=_external_evaluate(evaluator=evaluator,trace=trace,nav=transformed_path,
                outdir=evaluation_dir,registry=registry,settings=settings)
            capture=evaluated['capture']
            expected={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}
            if capture.get('selected_columns')!=expected or capture.get('consistency',{}).get('passed') is not True:
                raise ValueError('External evaluator reference-column/consistency gate failed')
            errors=canonical._read_error_series(evaluation_dir)
            index=next(i for i,r in enumerate(result['rows']['v3']) if r['run_id']==method)
            identity=dict(result['rows']['v3'][index]);identity.pop('unavailable_reason',None)
            identity.update(evaluation_invoked=True,code_commit=code_commit,completion_code_commit=code_commit)
            row=_metrics(errors,nav,identity,capture['reference_epoch_count'])
            row.update(error_series_source=str(evaluation_dir),source_nav_sha256=navhash,
                evaluator_nav_sha256=sha256_file(transformed_path),evaluation_runtime_seconds=evaluated['runtime_seconds'],
                uncertainty_status='UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED')
            result['rows']['v3'][index]=row
            bias_index=next(i for i,r in enumerate(result['body_frame_bias']['v3']) if r['run_id']==method)
            bias=dict(result['body_frame_bias']['v3'][bias_index]);bias.pop('unavailable_reason',None)
            bias.update(body_frame_bias(errors,nav),status='AVAILABLE',error_series_source=str(evaluation_dir),code_commit=code_commit)
            result['body_frame_bias']['v3'][bias_index]=bias
            gate_index=next(i for i,r in enumerate(result['run_gates']) if r['run_id']==method and r['version']=='v3')
            result['run_gates'][gate_index]={'version':'v3','run_id':method,'status':'COMPLETED','reason':None,
                'evaluator_output':str(evaluation_dir),'completion_code_commit':code_commit}
            if sha256_file(navpath)!=navhash:raise RuntimeError('External source NAV changed')
            write_json(root/'COMPLETION_GATE.json',{'status':'PASS','run_id':method,'source_nav_unchanged':True,
                'evaluator_invocations':1,'code_commit':code_commit,'capture':capture,'audit':evaluated['audit']})
            print('External v3 completion '+method+': COMPLETED',flush=True)
        completed=sum(r['evaluation_status']=='COMPLETED' for v in result['rows'].values() for r in v)
        unavailable=[(version,r['run_id']) for version,rows in result['rows'].items() for r in rows if r['evaluation_status']!='COMPLETED']
        if (completed!=24 or unavailable!=[('v2','CLEAN5_PARITY_V2e_F01'),('v3','CLEAN5_PARITY_V2e_F01')] or calls!=2
                or sum(r['status']=='AVAILABLE' for rows in result['body_frame_bias'].values() for r in rows)!=24
                or sum(r['status']=='COMPLETED' for r in result['run_gates'])!=24):
            raise RuntimeError('Final 24 available plus 2 registered V2e unavailable gate failed')
        if result['rows']['v2']!=summary['rows']['v2'] or result['body_frame_bias']['v2']!=summary['body_frame_bias']['v2']:
            raise RuntimeError('v2 result mutation')
        for old,new in zip(summary['rows']['v3'],result['rows']['v3']):
            if old['run_id']!=new['run_id'] or (old['run_id'] not in EXTERNAL_IDS and old!=new):
                raise RuntimeError('Internal v3 row/order mutation')
        prepared=audit/'COMPLETED_AGGREGATE';prepared.mkdir();(prepared/'v3').mkdir()
        regenerated={'v3/'+name for name in (*CANONICAL_CSV_NAMES,'BODY_FRAME_BIAS.csv','WINDOW_SEGMENT_SUMMARY.csv',
                     'FIELD_DEFINITIONS.json','FINAL_EVALUATION_SUMMARY.json')}
        regenerated.update(('FINAL_EVALUATION_SUMMARY.json','PARITY_DECOMPOSITION.csv'))
        for relative in original_hashes:
            if relative not in regenerated:_exclusive_copy(preserved/relative,prepared/relative)
        headers=canonical_headers(_resolve(settings['canonical_attempt'],registry))
        write_version_tables(target=prepared/'v3',result_target=current/'v3',rows=result['rows']['v3'],
                             bias=result['body_frame_bias']['v3'],headers=headers)
        result['decomposition']=build_decomposition(result['rows']['v2'],result['rows']['v3'])
        _csv(prepared/'PARITY_DECOMPOSITION.csv',result['decomposition'])
        result.update(status='COMPLETED_WITH_V2E_NATIVE_FAILURE',completion_code_commit=code_commit,
            prior_evaluation_code_commit=summary['code_commit'],code_commit=code_commit,
            external_completion_evaluator_invocations=calls,available_evaluation_rows=completed,
            unavailable_evaluation_rows=2,original_partial_summary_sha256=PINNED_INPUTS['08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json'])
        write_json(prepared/'FINAL_EVALUATION_SUMMARY.json',result)
        write_json(prepared/'v3/FINAL_EVALUATION_SUMMARY.json',{k:v for k,v in result.items() if k not in ('rows','body_frame_bias','decomposition')})
        _validate_inputs(stage)
        if execution_state(registry.code_root,code_commit)!=state:raise RuntimeError('Completion code snapshot changed')
        published=publish_aggregate(current=current,prepared=prepared,preserved=preserved,
                                     expected_hashes=original_hashes,audit_root=audit)
        _validate_inputs(stage,include_summary=False)
        final={**terminal,'status':'COMPLETED_WITH_V2E_NATIVE_FAILURE','evaluation':result,
            'completion_code_commit':code_commit,'code_commit':code_commit,'prior_solver_code_commit':terminal['code_commit'],'evaluation_gate':{'pass':True,'available':24,'unavailable_V2e':2},
            'external_completion':{'evaluator_invocations':2,'solver_invocations':0,'provider_generations':0,
                'repeated_internal_evaluations':0,'original_partial_results_preserved':str(preserved),'publication':published}}
        write_json(stage/'P02_FINAL_TERMINAL.json',final)
        write_json(audit/'COMPLETION_TERMINAL.json',{'status':final['status'],'final_terminal_sha256':sha256_file(stage/'P02_FINAL_TERMINAL.json'),
            'evaluator_invocations':calls,'solver_invocations':0,'available':24,'unavailable_V2e':2})
        return final
    except Exception as exc:
        write_json(audit/'COMPLETION_FAILURE.json',{'status':'FAILED','error':str(exc),'evaluator_invocations':calls,
            'solver_invocations':0,'retry_authorized':False,'original_aggregate_preserved':str(preserved)})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--code-freeze-commit',required=True)
    parser.add_argument('--paths-config',type=Path,required=True)
    args=parser.parse_args(argv)
    registry=load_registry(args.code_root/'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',args.paths_config)
    registry=replace(registry,code_root=args.code_root.resolve())
    contract=yaml.safe_load((registry.code_root/'configs/paper_rebuild/clean5/CLEAN5_PARITY_CONTRACT.yaml').read_text())
    if contract.get('contract_version')!=2:raise ValueError('Only preregistered contract v2 authorized')
    final=complete_external(registry=registry,stage_root=_resolve(contract['stage_root'],registry),
                            contract=contract,code_commit=args.code_freeze_commit)
    print(json.dumps({'status':final['status'],'available_evaluation_rows':24,'V2e_unavailable_rows':2}),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
