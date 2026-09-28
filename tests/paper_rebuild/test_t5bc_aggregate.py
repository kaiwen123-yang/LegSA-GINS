"""Synthetic sealed artifacts only; no actual native/evaluator/raw reads."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.hext import t5bc_aggregate as agg
from legsa_gins.paper_rebuild.hext import t5bc_reporting as report
from legsa_gins.paper_rebuild.hext import t5bc_runtime as runtime
from legsa_gins.paper_rebuild.hext.aggregate import _write_csv, H03_PRIMARY_STARTS
from legsa_gins.paper_rebuild.hext.t5bc_calibration import scalar_pair_calibration, vector_pair_calibration
from test_t5bc_calibration import vector_fixture
from test_t5bc_reporting import row as frozen_row


def pin(path):
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def document(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return pin(path)


def table(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    _write_csv(path,rows)
    return pin(path)


def fixture(tmp_path, diagnostics=True):
    scratch=tmp_path/runtime.STAGE; clean=tmp_path/'clean'; code=tmp_path/'code'
    clean.mkdir();code.mkdir();scratch.mkdir()
    ctx=SimpleNamespace(scratch=scratch,freeze='f'*40,roots=dict(t5bc_scratch=scratch,
        clean_root=clean,code_root=code,raw_root=tmp_path/'raw'),
        contexts={s:SimpleNamespace(window=(0.,3.)) for s in report.SEQUENCES})
    case='C00_clean_normal'; roles=report._mode('synthetic')
    ctx.metadata={case:dict(case_meta=dict(case_id=case,injection=dict(enabled=False,window=[1.,2.])),
        source_registry_row=dict(degradation_family='CLEAN',fault_type='NONE',other_identity='retained elsewhere'))}
    ctx.index=dict(hext04l={},sequence_tables={},t5a_r=dict(tables={}),subset_tables={},
        runtime_sources={},subset_sources={case:dict(data_roles=roles)})
    for version in ('v3','v2'):
        frozen=[];core=[];literature=[]
        for seq in report.SEQUENCES:
            for profile in report.PROFILES:
                value=frozen_row(seq,profile,version);value['source_nav_sha256']='a'*64
                frozen.append(value)
                run='SEQUENCE_'+seq+'_'+profile
                core.append(dict(run_id=run,dataset_id=seq,method_id=profile,native_nav_sha256='a'*64))
                ctx.index['runtime_sources'][seq+'_'+profile]=dict(frozen_run_id=run,frozen_table_line=len(core)+1)
            for profile in ('LC01','LC01-S'):
                value=frozen_row(seq,profile,version);value['start_convention']=H03_PRIMARY_STARTS[seq]
                literature.append(value)
        ctx.index['hext04l']['HORIZONTAL_TABLE_'+version.upper()+'_THREE_SEQUENCES.csv']=table(clean/('horizontal_'+version+'.csv'),frozen+literature)
        ctx.index['sequence_tables'][version]=table(clean/('core_'+version+'.csv'),core)
        ctx.index['t5a_r']['tables']['SENSITIVITY_TABLE_'+version.upper()+'.csv']=table(clean/('t5a_'+version+'.csv'),
            [{**frozen_row(s,p,version),'variant':'R5'} for s in report.SEQUENCES for p in ('F02','F04')])
        ctx.index['subset_tables'][version]=table(clean/('subset_'+version+'.csv'),
            [{**frozen_row('BY2','F04',version),'case_id':case,'horizontal_iae_m':'123.000',**roles},
             {**frozen_row('BY2','F01',version),'case_id':'D01_seed_00',
              'data_mode':'real_base_controlled_degradation','synthetic_data_used':'False','semisynthetic_data_used':'False'}])
    ctx.index['hext04l']['hext04l_segments']=table(clean/'frozen_segments.csv',[])
    ctx.index['t5a_r']['tables']['BY2O_SEGMENTS_BY_VARIANT.csv']=table(clean/'t5a_segments.csv',[])
    specs={}
    slots=[(*slot,None) for slot in report.sequence_slots()]+[('BY2','F04',v,case) for v in report.SUBSET_VARIANTS]
    for seq,cfg,var,subset in slots:
        run='__'.join((seq,cfg,var,subset or 'SEQUENCE'))
        specs[run]=dict(run_id=run,sequence_id=seq,configuration_id=cfg,variant=var,subset_case_id=subset)
    contract=dict(registered_runs=specs,matrix=dict(subset=dict(case_ids=[case])))
    contract_sha=runtime.scientific_contract_sha256(contract)
    natives={};evaluators={}
    for seq,cfg,var,subset in slots:
        run='__'.join((seq,cfg,var,subset or 'SEQUENCE'))
        spec=dict(run_id=run,sequence_id=seq,configuration_id=cfg,variant=var,subset_case_id=subset)
        specs[run]=spec;root=scratch/runtime._native_relative(spec);root.mkdir(parents=True)
        # Keep small actual-covariance diagnostic fixtures, including a subset
        # row that must never leak into the six-run figure series.
        if diagnostics and cfg=='F04' and var=='R5W':
            table(root/'PORT_GNSS_UPDATE_TRACE.csv',[dict(gnss_time=1.,yaw_update=1,yaw_mode='NORMAL')])
            table(root/'SOURCE_AWARE_WEIGHT_TRACE.csv',[dict(time=1.,source_id='dual_antenna_yaw',
                used_innovation_covariance=1,dof=1,nis=2.)])
        native={**spec,**roles,'status':'ALGORITHM_FAILURE_ALL_YAW_REJECTED',
                'failure_classification':'ALGORITHM_FAILURE_ALL_YAW_REJECTED','code_commit':ctx.freeze,'contract_sha256':contract_sha}
        sealed=runtime._seal(root,native,filename='T5BC_NATIVE_SUMMARY.json')
        natives[run]=sealed['native_summary']
        for version in ('v3','v2'):
            eroot=scratch/'06_EVAL'/version/run;eroot.mkdir(parents=True)
            status='NOT_RUN_ALGORITHM_FAILURE'
            ev=dict(run_id=run+'__'+version,code_commit=ctx.freeze,contract_sha256=contract_sha,native_summary=natives[run],
                status=status,row={**spec,**roles,'evaluation_status':status,'failure_classification':native['failure_classification'],
                'evaluator_contract':'evaluator_contract_'+version},evaluation_invoked=False,
                subset_metrics={'horizontal_iae_m':999.})
            evaluators[run+'__'+version]=runtime._seal(eroot,ev,filename='T5BC_EVALUATION_SUMMARY.json')['evaluation_summary']
    contract=dict(registered_runs=specs,matrix=dict(subset=dict(case_ids=[case])))
    summary=dict(status='COMPLETE_REGISTERED_EXECUTION',code_freeze=ctx.freeze,
        contract_sha256=runtime.scientific_contract_sha256(contract),native_terminals=natives,
        evaluation_terminals=evaluators,**roles)
    summary_ref=document(scratch/'09_HANDOFF/EXECUTION/FINAL_EXECUTION_SUMMARY.json',summary)
    pins=[]
    for seq in report.SEQUENCES:
        data=vector_fixture()
        for name,fn in (('SCALAR',scalar_pair_calibration),('VECTOR',vector_pair_calibration)):
            value=fn(**data);value.update(sequence_id=seq,**roles)
            pins.append(document(scratch/f'01_CALIBRATION/{seq}/{name}/{name}_CALIBRATION.json',value))
    calibration=dict(pins=pins,selections={s:dict(k=.1,sigma_deg=.2,k_b=.3) for s in report.SEQUENCES})
    document(scratch/'01_CALIBRATION/CALIBRATION_SUMMARY.json',calibration)
    ctx._verified_calibration=lambda:calibration
    return ctx,contract,summary_ref


def csv_rows(path):
    return list(csv.DictReader(io.StringIO(path.read_text())))


def test_synthetic_sealed_full_pipeline_retains_counts_metrics_and_roles(tmp_path):
    ctx,contract,summary=fixture(tmp_path)
    before={str(p):pin(p)['sha256'] for p in ctx.scratch.rglob('*') if p.is_file()}
    result=agg.aggregate_t5bc(ctx,contract=contract,execution_summary_ref=summary)
    manifest=json.loads(Path(result['path']).read_text());out=ctx.scratch/'07_AGGREGATE'
    assert manifest['synthetic_data_used'] is True
    assert manifest['row_counts']['PILOT_TABLE_V3.csv']==36
    assert manifest['row_counts']['SUBSET61_TABLE_V3.csv']==5
    assert manifest['row_counts']['CALIBRATION_SUMMARY.csv']==6
    assert manifest['row_counts']['S3_CALIBRATION_BINS.csv']==36
    assert manifest['row_counts']['BY2O_SEGMENTS_BY_VARIANT.csv']==100
    subset=csv_rows(out/'SUBSET61_TABLE_V3.csv')
    assert subset[0]['horizontal_iae_m']=='123.000'
    assert all(r['horizontal_iae_m']=='UNAVAILABLE' for r in subset[1:])
    assert all(r['failure_classification']=='ALGORITHM_FAILURE_ALL_YAW_REJECTED' for r in subset[1:])
    assert subset[0]['heading_columns_replaced_by_design']=='False'
    assert all(r['heading_columns_replaced_by_design']=='True' for r in subset[1:])
    effects=csv_rows(out/'CASE_INPUT_EFFECTS.csv')
    assert len(effects)==1 and json.loads(effects[0]['case_meta_json'])==ctx.metadata['C00_clean_normal']['case_meta']
    assert json.loads(effects[0]['source_registry_family_type_json'])==dict(degradation_family='CLEAN',fault_type='NONE')
    assert effects[0]['original_heading_injection_preserved_claim']=='False'
    assert effects[0]['fault_presence_inferred']=='False'
    raw=json.loads((out/'FROZEN_SOURCE_ROWS.json').read_text())
    assert raw['original_csv_rows']['subset_v3'][1][1]['data_mode']=='real_base_controlled_degradation'
    series=csv_rows(out/'NIS_SERIES.csv')
    assert len(series)==3 and all(r['subset_case_id']=='' and r['variant']=='R5W' for r in series)
    calibration=csv_rows(out/'CALIBRATION_SUMMARY.csv')
    assert all({'sigma_deg','k','k_b','scalar_z_residual_variance_rad2','vector_sample_covariance_m2'} <= set(r) for r in calibration)
    assert all(pin(Path(path))['sha256']==digest for path,digest in before.items())
    assert all(pin(out/name)['sha256']==digest for name,digest in manifest['files_sha256'].items())
    assert not any(str(tmp_path) in (out/name).read_text() for name in manifest['files_sha256'] if name.endswith('.csv'))
    with pytest.raises(FileExistsError):agg.aggregate_t5bc(ctx,contract=contract,execution_summary_ref=summary)


def test_hash_failure_prevents_output_and_missing_terminal_is_not_dropped(tmp_path):
    ctx,contract,summary=fixture(tmp_path)
    Path(ctx.index['subset_tables']['v3']['path']).write_text('changed')
    with pytest.raises(RuntimeError,match='AGGREGATE_INPUT_HASH'):
        agg.aggregate_t5bc(ctx,contract=contract,execution_summary_ref=summary)
    assert not (ctx.scratch/'07_AGGREGATE').exists()


def test_empty_nis_series_has_explicit_schema_not_fabricated_rows(tmp_path):
    ctx,contract,summary=fixture(tmp_path,diagnostics=False)
    agg.aggregate_t5bc(ctx,contract=contract,execution_summary_ref=summary)
    path=ctx.scratch/'07_AGGREGATE/NIS_SERIES.csv'
    assert csv_rows(path)==[]
    assert {'sequence_id','configuration_id','variant','time','nis','dof'} <= set(path.read_text().splitlines()[0].split(','))


def test_source_index_roles_cannot_conceal_conflicting_frozen_tokens():
    with pytest.raises(ValueError,match='Data role'):
        agg._roles([(2,dict(data_mode='synthetic',synthetic_data_used='True',semisynthetic_data_used='False'))],
                   'real_raw',source_table='FROZEN')


def test_report_reader_denies_reference_trace_even_inside_clean_root(tmp_path):
    scratch=tmp_path/runtime.STAGE;clean=tmp_path/'clean';clean.mkdir()
    path=clean/'Trace_forbidden.csv';path.write_bytes(b'must not read')
    ctx=SimpleNamespace(scratch=scratch,roots=dict(clean_root=clean,code_root=tmp_path/'code',raw_root=tmp_path/'raw'))
    with pytest.raises(PermissionError,match='cannot read'):
        agg.PinnedInputs(ctx).read(dict(path=str(path),sha256='0'*64))


def test_frozen_row_requires_exact_nav_binding_not_near_metrics():
    rows=[(2,dict(sequence_id='BY2',method_id='F02',source_nav_sha256='a'*64))]
    core=[(2,dict(run_id='RUN',dataset_id='BY2',method_id='F02',native_nav_sha256='b'*64))]
    with pytest.raises(ValueError,match='NAV identity'):
        agg._frozen_native_binding(rows,core,{'BY2_F02':dict(frozen_run_id='RUN',frozen_table_line=2)})


def test_d57_case_effects_preserve_metadata_without_fault_inference():
    metadata=dict(case_meta=dict(description='Original timestamp fault',arbitrary_nested={'magnitude':.001}),
                  source_registry_row=dict(fault_family='TIME',degradation_type='IRREGULAR'))
    ctx=SimpleNamespace(metadata={'D57_seed_00':metadata},index=dict(subset_sources={
        'D57_seed_00':dict(data_roles=report._mode('synthetic'))}))
    rows=agg.case_input_effects(ctx,['D57_seed_00'])
    assert rows[0]['case_meta_json']==metadata['case_meta']
    assert rows[0]['d57_exact_time_join_without_repair'] is True
    assert 'no timestamp repair or interpolation' in rows[0]['time_policy']
    assert rows[0]['new_fault_injection_designed'] is False


def test_dual_error_exports_need_matching_decompressed_bytes(tmp_path):
    root=tmp_path/runtime.STAGE;root.mkdir()
    ctx=SimpleNamespace(scratch=root,roots=dict(clean_root=tmp_path/'clean',code_root=tmp_path/'code',raw_root=tmp_path/'raw'))
    plain=root/'errors.csv';plain.write_bytes(b'time,x\n1,2\n')
    compressed=root/'errors.csv.gz';compressed.write_bytes(gzip.compress(b'time,x\n1,3\n'))
    record=dict(file_hashes={p.name:pin(p)['sha256'] for p in (plain,compressed)})
    with pytest.raises(RuntimeError,match='bytes disagree'):
        agg.PinnedInputs(ctx).frame(root,record,'errors.csv')
