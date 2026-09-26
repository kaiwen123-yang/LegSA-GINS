"""Synthetic lineage/remap checks; never generate real providers."""
import pytest
from legsa_gins.paper_rebuild.clean5_parity_p04 import rv_remap as rv


def fixture():
    base=315964782.
    statuses=[{'time_gps_wno':'0','time_gps_tow':str(t),'header.stamp.secs':str(int(base+t)),
               'header.stamp.nsecs':'0','sys_stamp.secs':str(int(base+t)),'sys_stamp.nsecs':'200000000'} for t in [1,2]]
    pvt={1800:{'receipt_stamp':base+2.19,'velocity_mps':[.001,.002,.003]},
         2000:{'receipt_stamp':base+2.24,'velocity_mps':[.009,.008,.007]}}
    original={'time':2.19,'stamp':base+2.19,'itow_ms':1800,'vn':.001,'ve':.002,'vd':.003}
    data=b''.join(f'{t+.2:.6f}  39 116 40 .1 .1 .2 0.001000 0.002000 0.003000 .05 .05 .05 10 1.5\n'.encode() for t in [1,2])
    return base,statuses,pvt,original,data


def test_authorized_change_retains_true_v0_comparison_and_receipt_lineage():
    base,status,pvt,old,data=fixture()
    output,a=rv.remap_v1(data,status,pvt,[{'match':old,'direct_match':False},{'match':old,'direct_match':True}],base_time=base,window=[1.5,3])
    assert a['RV_changed_row_count']==1 and a['non_time_measurement_tokens_byte_equal_to_true_V0'] is False
    assert a['position_and_std_tokens_byte_equal_to_true_V0'] and a['yaw_and_std_tokens_byte_equal_to_true_V0']
    assert output.splitlines()[0]==data.splitlines()[0]
    assert output.splitlines()[1].split()[7:10]==[b'0.009000',b'0.008000',b'0.007000']
    row=a['ledger'][1];assert row['old_PVT_itow_ms']==1800 and row['itow_ms']==2000
    assert row['old_match_mode']=='receipt_nearest'
    assert row['status_sys_minus_old_PVT_itow_s']==pytest.approx(.4,abs=1e-7)
    assert a['ledger'][0]['RV_valid']==0
    assert b'  39' in output


def test_bad_replay_and_missing_window_measurement_fail_closed():
    base,status,pvt,old,data=fixture();matches=[{'match':old,'direct_match':True}]*2
    with pytest.raises(ValueError,match='inside window'):rv.remap_v1(data,status,pvt,matches,base_time=base,window=[0,3])
    old['vn']=1
    with pytest.raises(ValueError,match='replay mismatch'):rv.remap_v1(data,status,pvt,matches,base_time=base,window=[1.5,3])


def test_original_nearest_and_fill_are_replayed_not_velocity_searched(monkeypatch):
    base,status,pvt,old,data=fixture()
    rows=[{**old}, {'time':2.24,'stamp':base+2.24,'vn':.009,'ve':.008,'vd':.007}]
    # Original computations use exact stamp-base, not rounded six-place text.
    for r in rows:r['time']=r['stamp']-base
    monkeypatch.setattr(rv,'_status_base_rows',lambda *a,**k:([{'time':rv.stamp(s,'sys_stamp.')-base} for s in status],0))
    monkeypatch.setattr(rv,'extract_pvt_velocity_rows',lambda *a,**k:rows)
    selected=rv.replay_original_matches(None,None,status,pvt,base)
    assert not selected[0]['direct_match'] and selected[1]['direct_match']
    assert [r['match']['itow_ms'] for r in selected]==[1800,1800]
    # Equal velocity at a different epoch cannot substitute for receipt identity.
    pvt[2000]['receipt_stamp']=base+3
    with pytest.raises(ValueError,match='receipt inventory'):rv.replay_original_matches(None,None,status,pvt,base)
