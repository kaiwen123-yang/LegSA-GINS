"""Synthetic unit fixtures only: no real-data provider output or evidence."""
import pytest
from legsa_gins.paper_rebuild.clean5_parity.providers import (
    ParityProviderError, append_validity, build_variants, replace_time)
from legsa_gins.paper_rebuild.clean5_parity.input_audit import accuracy_audit


def fixture():
    # GPS week zero, leap policy fixed; epoch one second is deliberately outside
    # the runtime window and has no PVT. All measurement tokens stay untouched.
    base = 315964782
    lines = b'1.200000 0 0 0 .125000 .125000 .250000 0.001000 0.002000 0.003000 .050000 .050000 .050000 12.000000 1.500000\n2.200000 0 0 0 .125000 .125000 .250000 0.001000 0.002000 0.003000 .050000 .050000 .050000 13.000000 1.500000\n'
    statuses = []
    for t in (1, 2):
        statuses.append({'time_gps_wno':'0','time_gps_tow':str(t),
            'sys_stamp.secs':str(base+t),'sys_stamp.nsecs':'200000000',
            'header.stamp.secs':str(base+t),'header.stamp.nsecs':'0',
            'pos_acc_h':'.125','pos_acc_v':'.25','pos_lat':'0','pos_lon':'0','pos_height':'0'})
    hp = {2000:{'ecef_m':[6378137.,0,0], 'pAcc_m':.1}, 2200:{'ecef_m':[6378137.,0,0], 'pAcc_m':.1}}
    pvt = {k:{'velocity_mps':[.001,.002,.003],'hAcc_m':.125,'vAcc_m':.25,
               'receipt_stamp':base+k/1000+.1} for k in hp}
    return base,lines,statuses,hp,pvt


def test_append_preserves_original_bytes_and_validity():
    line=b' 1\t2 3 4 5 6 7 8 9 10 11 12 13 14 15\r\n'
    assert append_validity(line)==line[:-2]+b' 1 1 1\n'
    with pytest.raises(ParityProviderError):
        append_validity(line,(1,2,0))
    with pytest.raises(ParityProviderError):
        append_validity(b'nan '+b'1 '*14)


def test_missing_prewindow_epoch_is_invalid_not_filled_measurement():
    base,lines,status,hp,pvt=fixture()
    variants,audit=build_variants(lines,status,hp,pvt,base_time=base,window=[1.5,3],a1_source_times=[base+1,base+2])
    v1=[r.split() for r in variants['V1'].splitlines()]
    assert v1[0][-3:]==[b'1',b'0',b'1']
    for before,after in zip(lines.splitlines(),v1):
        assert before.split()[1:]==after[1:15]
    v2=[r.split() for r in variants['V2'].splitlines()]
    assert v2[0][4:7]==[b'0.125000',b'0.125000',b'0.250000']
    assert v2[0][-1]==b'1' and v2[1][-1]==b'0'
    assert audit['a1_hp_mapped_count']==1
    assert audit['same_source_within_5mm']
    for row in variants['V2e'].splitlines():
        r=row.split()
        assert r[-3:]==[b'1',b'0',b'0']
        assert len(set(r[4:7]))==1


def test_inwindow_missing_and_changed_velocity_fail_closed():
    base,lines,status,hp,pvt=fixture()
    with pytest.raises(ParityProviderError,match='Missing exact'):
        build_variants(lines,status,hp,pvt,base_time=base,window=[0,3],a1_source_times=[])
    pvt[2000]['velocity_mps'][0]=.002
    with pytest.raises(ParityProviderError,match='RV token mismatch'):
        build_variants(lines,status,hp,pvt,base_time=base,window=[1.5,3],a1_source_times=[])


def test_accuracy_reports_float32_not_false_float64_equality():
    import numpy as np
    row={'time_gps_tow':'2','pos_acc_h':str(float(np.float32(.014))), 'pos_acc_v':str(float(np.float32(.010)))}
    audit=accuracy_audit([row],{2000:{'hAcc_m':.014,'vAcc_m':.010}})
    assert audit['all_equal_at_status_float32_precision']
    assert audit['float64_exact_equal_count']==0
    row['pos_acc_h']='.03'
    assert not accuracy_audit([row],{2000:{'hAcc_m':.014,'vAcc_m':.010}})['all_equal_at_status_float32_precision']
