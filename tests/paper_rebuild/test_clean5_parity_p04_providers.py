"""Synthetic P04 input-gate tests; no real-data provider generation."""
import pytest
from legsa_gins.paper_rebuild.clean5_parity_p04.providers import gnss_preflight, _counts


def source_fixture():
    base=315964782.
    status=[]
    lines=[]
    for t in [1,2]:
        status.append({'time_gps_tow':str(t),'header.stamp.secs':str(int(base+t)),
            'header.stamp.nsecs':'0','sys_stamp.secs':str(int(base+t)),'sys_stamp.nsecs':'200000000',
            'pos_acc_h':'.125','pos_acc_v':'.25'})
        lines.append(f'{t+.2:.6f} 0 0 0 .125 .125 .25 0.001000 0.002000 0.003000 .05 .05 .05 1 1.5')
    pv={2000:{'velocity_mps':[.001,.002,.003],'hAcc_m':.125,'vAcc_m':.25}}
    return base,status,('\n'.join(lines)+'\n').encode(),pv


def test_missing_leading_epoch_stays_explicit_outside_window():
    base,status,data,pv=source_fixture()
    a=gnss_preflight(data,status,{2000:{}},pv,base,[1.5,3])
    assert a['status']=='PASS'
    assert a['V1_RV_equal_count']==1
    assert a['V1_missing_same_itow_RV'][0]['inside_window'] is False


def test_same_epoch_value_conflict_is_not_silently_replaced():
    base,status,data,pv=source_fixture();pv[2000]['velocity_mps'][0]=.009
    a=gnss_preflight(data,status,{2000:{}},pv,base,[1.5,3])
    assert a['status']=='BLOCKED'
    mismatch=a['V1_RV_mismatches'][0]
    assert mismatch['inside_window'] is True
    assert mismatch['frozen_RV_tokens'][0]=='0.001000'
    assert mismatch['same_itow_RV_tokens'][0]=='0.009000'
    assert a['V1_non_time_measurement_bytes_can_remain_equal'] is False


def test_missing_inside_window_and_row_lineage_are_strict():
    base,status,data,pv=source_fixture()
    assert gnss_preflight(data,status,{2000:{}},pv,base,[0,3])['status']=='BLOCKED'
    status[0]['sys_stamp.nsecs']='300000000'
    with pytest.raises(ValueError,match='lineage'):gnss_preflight(data,status,{2000:{}},pv,base,[0,3])


def test_validity_counts_keep_closed_start_boundary():
    row=lambda t,y: ' '.join([str(t)]+['0']*14+['1','1',str(y)])
    data=(row(1,1)+'\n'+row(1.2,0)+'\n'+row(2,1)+'\n').encode()
    a=_counts(data,[1,1.2]);assert a['full']['rows']==3
    assert a['closed_window']=={'rows':2,'position_valid':2,'velocity_valid':2,'yaw_valid':1}


def test_frozen_gate_quantile_and_standard_even_median_are_distinguished():
    from legsa_gins.paper_rebuild.clean5_parity_p04.providers import frozen_baseline
    gate={'per_epoch':[{'baseline_length_m':x} for x in [.3,.4]],'median_baseline_length_m':.3}
    median,audit=frozen_baseline(gate)
    assert median==.35
    assert audit['frozen_gate_summary_order_statistic_m']==.3
    gate['median_baseline_length_m']=.35
    with pytest.raises(ValueError,match='_percentile'):frozen_baseline(gate)


def test_blocked_preflight_cannot_create_provider_directory(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.clean5_parity_p04 import providers
    registry=SimpleNamespace(clean_root=tmp_path,raw_root=tmp_path/'raw',code_root=tmp_path/'code')
    stage=tmp_path/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/12_PARITY_GENERALIZATION'
    contract={'p04':{'stage_root':str(stage),'execution_ready':True,'sequences':{'BY2O':{'execution_ready':True}}}}
    monkeypatch.setattr(providers,'_prepare',lambda *args:({'status':'BLOCKED_V1_RV_CONFLICT'},None,''))
    with pytest.raises(ValueError,match='preflight blocked'):
        providers.generate_providers(registry=registry,stage_root=stage,contract=contract,code_commit='test',dataset='BY2O')
    assert not (stage/'BY2O/02_PARITY_PROVIDERS').exists()


@pytest.mark.parametrize('global_ready,local_ready',[(False,True),(True,False)])
def test_pending_registration_blocks_direct_provider_entry(tmp_path,monkeypatch,global_ready,local_ready):
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.clean5_parity_p04 import providers
    registry=SimpleNamespace(clean_root=tmp_path,raw_root=tmp_path/'raw',code_root=tmp_path/'code')
    stage=tmp_path/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/12_PARITY_GENERALIZATION'
    contract={'p04':{'stage_root':str(stage),'execution_ready':global_ready,
                    'sequences':{'BY2O':{'execution_ready':local_ready}}}}
    monkeypatch.setattr(providers,'_prepare',lambda *a:pytest.fail('Pending gate must precede raw reads'))
    with pytest.raises(ValueError,match='execution gate is not ready'):
        providers.generate_providers(registry=registry,stage_root=stage,contract=contract,code_commit='test',dataset='BY2O')
    assert not stage.exists()


def test_authorized_rv_remap_relaxes_only_value_conflict():
    base,status,data,pv=source_fixture();pv[2000]['velocity_mps'][0]=.009
    audit=gnss_preflight(data,status,{2000:{}},pv,base,[1.5,3],allow_rv_remap=True)
    assert audit['status']=='PASS' and audit['V1_RV_mismatch_count']==1
    assert audit['V1_non_time_measurement_bytes_can_remain_equal'] is False
    assert gnss_preflight(data,status,{2000:{}},pv,base,[0,3],allow_rv_remap=True)['status']=='BLOCKED'
