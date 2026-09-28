"""One-case P09c provider worker; caller supplies isolated strace/pool/tempdir."""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
from ..canonical541 import provider_generator as canonical
from ..canonical541.seed_anchor import stable_component_rngs
from ..clean5_degradation.common import pinned, read_csv, resolved_pins, write_json
from ..clean5_degradation.providers import (
    build_base, generate_case, _csv, _valid, SOURCE_TO_ROLE, DegradationProviderError,
)
from ..manifest import sha256_file
from .contract import STAGE_NAME, selection


def wgs84_self_check():
    """Independent analytic WGS84 axes check, without observation/reference data."""
    a=6378137.0; f=1/298.257223563; b=a*(1-f)
    checks=[(canonical._ecef(0,0,0),(a,0,0)),
            (canonical._ecef(0,90,0),(0,a,0)),
            (canonical._ecef(90,0,0),(0,0,b)),
            (canonical._ecef(0,0,123),(a+123,0,0))]
    errors=[float(np.max(np.abs(np.asarray(actual)-expected))) for actual,expected in checks]
    if max(errors)>1e-7:
        raise DegradationProviderError('WGS84 analytic ECEF self-check failed')
    return {'passed':True,'a_m':a,'inverse_flattening':298.257223563,'maximum_axis_error_m':max(errors),
            'trace_opened':False,'test_data_used_as_runtime_input':False}


def _selected(case, table, ratio):
    rngs=stable_component_rngs(int(case['seed_value']),canonical.COMPONENT_RNG_NAMES)
    return set(int(v) for v in canonical._random_subset(
        rngs['selection'],np.asarray([i for i,r in enumerate(table.rows) if _valid(r)],dtype=int),ratio))


def validate_case_extension(base, case, result):
    """Realized measurements close additional P08 branch and event gates."""
    tid=case['degradation_type_id']; checks=[]
    def check(name,passed,details):
        checks.append({'check':name,'passed':bool(passed),'details':details})
        if not passed:
            raise DegradationProviderError('P09c effect failed '+name)
    check('p07_per_family_semantics',result['semantic_equivalence']['passed'],
          {'handler':tid,'checks':len(result['semantic_equivalence']['checks'])})
    gnss=np.loadtxt(result['providers']['gnsspath']['path'],ndmin=2)
    before=np.asarray(base.gnss_tokens,float)
    check('finite_18_columns_validity',gnss.shape[1]==18 and np.isfinite(gnss).all()
          and np.isin(gnss[:,15:18],[0,1]).all(),'position/RV/A1 independent 0/1 flags')
    check('strict_time_order',np.all(np.diff(gnss[:,0])>0),'no duplicate or reversed event times')
    if tid!='D57':
        check('five_hz_source_grid_preserved',np.array_equal(gnss[:,0],before[:,0]),'faults except D57 retain frozen nominal schedule')
        check('a1_only_original_rows',np.all(gnss[before[:,17]==0,17]==0),'never enable a held yaw')
    else:
        check('d57_event_conservation',all(int(gnss[:,col].sum())==sum(_valid(r) for r in base.bundle.tables[src].rows)
              for col,src in [(15,'gnss_position'),(16,'receiver_velocity'),(17,'dual_yaw')]),
              'each independent source valid event appears once in irregular union')
        check('d57_irregular_union',len(gnss)>len(before) and np.any(np.abs(np.diff(gnss[:,0])-.2)>1e-6),
              'independent time faults cannot snap back onto original 5Hz grid')
    if tid in ('D51','D52','D54'):
        source='go2_hv' if tid=='D54' else 'go2_rp'
        table=base.bundle.tables[source]
        _,after=_csv(Path(result['providers'][SOURCE_TO_ROLE[source]]['path']))
        check('auxiliary_rows_and_times',len(after)==len(table.rows) and all(float(l['time'])==float(r['time']) for l,r in zip(table.rows,after)),source)
        if tid in ('D51','D54'):
            seed=int(case['seed_index'][-2:]); ratio=.5 if tid=='D51' or seed>=4 else 0.
            selected=_selected(case,table,ratio) if ratio else set()
            dropped={i for i,(l,r) in enumerate(zip(table.rows,after)) if _valid(l) and not _valid(r)}
            check('exact_dropout_selection',dropped==selected,{'seed_index':seed,'ratio':ratio,'expected_count':len(selected),'actual_count':len(dropped)})
            check('no_invalid_source_enabled',all(not _valid(r) or _valid(l) for l,r in zip(table.rows,after)),'valid bits never manufacture an observation')
        if tid=='D54':
            scale=1.5 if seed<=3 or seed==8 else 1.0
            check('d54_seed_branch_scale',all(abs(float(r[k])-float(l[k])*scale)<=5.1e-10 for l,r in zip(table.rows,after) for k in ('vn','ve')),
                  {'seed_index':seed,'scale':scale,'dropout_ratio':ratio})
            check('d54_std_unchanged',all(l[k]==r[k] for l,r in zip(table.rows,after) for k in ('std_vn','std_ve','std_vd') if k in l),'all per-measurement noise fields frozen')
        elif tid=='D52':
            vectors=np.array([[float(r[k])-float(l[k]) for k in ('roll_rad','pitch_rad')] for l,r in zip(table.rows,after)])
            check('d52_constant_two_degree_vector',np.allclose(np.linalg.norm(vectors,axis=1),math.radians(2),rtol=0,atol=1.1e-12)
                  and np.max(np.abs(vectors-vectors[0]))<1.1e-12,'same 2deg vector on every row')
        else:
            check('d51_dropped_payload_retained',all(table.rows[i][k]==after[i][k] for i in selected for k in ('roll_rad','pitch_rad')),
                  'dropouts retain finite original angle payload')
            check('d51_std_unchanged',all(l[k]==r[k] for l,r in zip(table.rows,after) for k in ('std_roll_rad','std_pitch_rad') if k in l),'3deg noise applies only to remaining rows; std unchanged')
    if tid=='D56':
        audit=result['audit_payloads']['source_quality_metadata']
        _,rows=_csv(Path(audit['path']))
        rngs=stable_component_rngs(int(case['seed_value']),canonical.COMPONENT_RNG_NAMES)
        selected=canonical._random_subset(rngs['metadata'],np.arange(len(rows)),.3)
        seed=int(case['seed_index'][-2:])
        expected={int(i):('high_high' if (ordinal%2==0 if seed==8 else seed%2==0) else 'low_low') for ordinal,i in enumerate(selected)}
        actual={i:r['audit_go2_metadata'] for i,r in enumerate(rows) if r.get('audit_go2_metadata','')}
        check('d56_even_odd_alternating_branch',actual==expected,{'seed_index':seed,'selected_count':len(selected)})
    return {'status':'PASS_PROTOCOL_V2_EFFECT','passed':True,'checks':checks,'wgs84_self_check':wgs84_self_check(),
            'handler':tid,'gnss_row_count':len(gnss),'valid_counts':{'position':int(gnss[:,15].sum()),'receiver_velocity':int(gnss[:,16].sum()),'A1':int(gnss[:,17].sum())},
            'trace_opened':False,'automatic_regeneration':False}


def generate_one(contract, reg, stage, case_id, code_commit, contract_hash=None):
    """One attempt; no process pool, strace wrapper, retry, solver or evaluator.

    The parent verifies the committed contract/source freeze and runs this under
    an independent strace session. Immutable frozen sources are read by this
    process; the only writes are under stage/02_PROVIDERS/case_id.
    """
    stage=Path(stage)
    if stage.name!=STAGE_NAME or reg.clean_root not in stage.parents:
        raise ValueError('Provider stage outside exact P09c root')
    if contract_hash is None:
        contract_path=reg.code_root/'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml'
        contract_hash=sha256_file(contract_path)
    cases,_=selection(contract,reg)
    matches=[c for c in cases if c['case_id']==case_id]
    if len(matches)!=1: raise ValueError('Unregistered case')
    for spec in contract['sources']['frozen_injection_library']:
        pinned(spec,reg)
    raw_hashes={r['relative_path']:r['sha256'] for r in read_csv(pinned(contract['sources']['raw_lock'],reg)) if r['dataset']=='BY2'}
    if len(raw_hashes)!=22: raise ValueError('Raw source hash lineage incomplete')
    base=build_base(resolved_pins(contract['providers']['roles'],reg),
                    auxiliary_roles=resolved_pins(contract['providers']['auxiliary_roles'],reg),
                    base_time_s=contract['evaluation']['base_time'],raw_input_hashes=raw_hashes)
    mapping=next(m for m in contract['providers']['mapping'] if m['case_id']==case_id)
    mapping=resolved_pins(mapping,reg)
    mapping['equivalence_rule']=contract['providers']['semantic_evidence']['equivalence_rule']
    result=generate_case(base,matches[0],mapping,stage/'02_PROVIDERS',
                         code_commit=code_commit,config_hash=contract_hash,expected_family=STAGE_NAME)
    result.update(protocol_id=contract['protocol_id'],protocol_v2_effect=validate_case_extension(base,matches[0],result))
    case_root=Path(result['case_root'])
    write_json(case_root/'PROTOCOL_V2_EFFECT_VALIDATION.json',result['protocol_v2_effect'])
    write_json(case_root/'PROVIDER_BUNDLE.json',result)
    return result
