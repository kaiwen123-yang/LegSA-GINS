"""Synthetic source fixtures only; no real provider, solver or evaluator runs."""
from pathlib import Path
import pytest
import test_clean5_degradation_providers as p07
from test_clean5_degradation_providers import inputs  # fixture, explicitly synthetic
from legsa_gins.paper_rebuild.clean5_degradation.providers import generate_case, DegradationProviderError
from legsa_gins.paper_rebuild.clean6_canonical_v2.contract import load_contract, STAGE_NAME
from legsa_gins.paper_rebuild.clean6_canonical_v2.providers import validate_case_extension, wgs84_self_check


@pytest.mark.parametrize('tid',['D51','D52','D54','D56','D57'])
@pytest.mark.parametrize('seed',range(9))
def test_protocol_semantics_all_seed_branches(tmp_path,inputs,monkeypatch,tid,seed):
    row={'case_id':tid+f'_seed_{seed:02d}','degradation_type_id':tid,
         'seed_index':f'seed_{seed:02d}','seed_value':260306001+seed,'anchor_time_s':90.0}
    monkeypatch.setattr(p07,'case',lambda _:row)
    mapping=p07.mapping(tmp_path,tid,inputs[0])
    result=generate_case(inputs[0],row,mapping,tmp_path/'output',expected_family=STAGE_NAME)
    assert result['synthetic_data_used'] is True and result['data_mode']=='synthetic_test'
    assert result['provider_family']==STAGE_NAME
    audit=validate_case_extension(inputs[0],row,result)
    assert audit['passed'] and all(r['passed'] for r in audit['checks'])


def test_explicit_family_does_not_expand_unregistered_roots(tmp_path,inputs):
    with pytest.raises(DegradationProviderError,match='Unregistered explicit'):
        generate_case(inputs[0],p07.case('CLEAN'),p07.mapping(tmp_path,'CLEAN',inputs[0]),
                      tmp_path/'output',expected_family='UNAPPROVED_STAGE')
    assert not (tmp_path/'output').exists()


def test_default_family_remains_p07(tmp_path,inputs):
    result=generate_case(inputs[0],p07.case('CLEAN'),p07.mapping(tmp_path,'CLEAN',inputs[0]),tmp_path/'output')
    assert result['provider_family']=='CLEAN5_DEGSUBSET_C00_clean_normal'


def test_frozen_contract_covers_all_seeds_and_numeric_anchors():
    code=Path(__file__).resolve().parents[2]
    contract=load_contract(code/'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml')
    assert len(contract['anchors']['seed_anchor_rows'])==9
    assert len(contract['anchors']['C00_profiles'])==11
    assert all(len(r['files_sha256'])==7 for r in contract['anchors']['C00_profiles'])
    assert len(contract['sequence_consistency']['references'])==15
    assert contract['execution']['initial_gate_barrier'].startswith('Complete 33')
    assert 'physical MemTotal' in ' '.join(contract['execution']['pilot_required_measurements'])
    assert wgs84_self_check()['passed']
