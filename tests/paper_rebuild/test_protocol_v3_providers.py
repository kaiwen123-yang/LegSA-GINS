"""Synthetic byte/mapping edge cases; never scientific result evidence."""
import pytest
from legsa_gins.paper_rebuild.protocol_v3.providers import byte_gate, lift_heading


def table(times, yaw=10., valid=1, std='2.933193'):
    return b'# synthetic fixture\r\n'+b''.join(('  '+str(t)+'  '+' '.join(['0']*12)+
        f' {yaw} {std} 1 1 {valid}\r\n').encode() for t in times)


def values(payload):
    return [row.split() for row in payload.splitlines() if row and not row.startswith(b'#')]


def test_nonyaw_whitespace_and_std_are_protected():
    source=table([56.,57.])
    assert byte_gate(source,table([56.,57.],yaw=20.))['passed']
    with pytest.raises(ValueError):byte_gate(source,table([56.,57.],std='1.5'))
    with pytest.raises(ValueError):byte_gate(source,source.replace(b'  ',b' '))


def test_exact_half_open_outage_preserves_all_other_fields():
    raw=table([55.8,56.,56.2,56.4,56.6,56.8,57.],yaw=20.)
    source=table([55.8,56.,56.2,56.4,56.6,56.8,57.],std='4.399789500')
    result,audit=lift_heading(source,raw,table([56.,57.]),type_id='D30',components=[
        {'affected_source':'dual_yaw','details':{'interval':[56.2,56.6]}}])
    assert [r[17] for r in values(result)]==[b'1',b'1',b'0',b'0',b'1',b'1',b'1']
    assert all(r[14]==b'4.399789500' for r in values(result))
    assert audit['all_other_bytes_identical']


def test_cell_lift_wrap_and_last_cell_boundary():
    times=[55.8,56.,56.2,56.8,57.,57.8,58.]
    fault=[dict(time=56.,yaw_deg=12.,valid=1),dict(time=57.,yaw_deg=7.,valid=1)]
    result,_=lift_heading(table(times),table(times,yaw=359.),table([56.,57.]),
        type_id='D32',fault_rows=fault)
    assert [float(r[13]) for r in values(result)]==[359.,1.,1.,1.,356.,356.,359.]


def test_d57_unmatched_is_invalid_without_timestamp_repair():
    source=table([56.123456789,57.23456789])
    result,audit=lift_heading(source,table([56.,57.]),table([56.,57.]),type_id='D57')
    assert audit['valid_heading_rows']==0
    assert all(r[17]==b'0' for r in values(result))
    assert [r[0] for r in values(result)]==[r[0] for r in values(source)]
    with pytest.raises(ValueError):lift_heading(table([56.,57.]),table([56.,57.]),table([56.,57.]),type_id='D57')


def test_frozen_std_variants_and_disabled_f01_std_remain_exact():
    for std in ('1.5','2.933193','8.799579000','0.733298250'):
        result,audit=lift_heading(table([56.,57.],std=std),table([56.,57.],yaw=20.),table([56.,57.]))
        assert all(r[14]==std.encode() for r in values(result))
        assert audit['changed_tokens_by_column'][14]==0


def test_legacy_dropout_lifts_one_second_cells_without_redraw():
    raw=table([55.8,56.,56.2,56.8,57.,57.2,58.])
    fault=[dict(time=56.,yaw_deg=10.,valid=0),dict(time=57.,yaw_deg=10.,valid=1)]
    result,_=lift_heading(raw,raw,table([56.,57.]),type_id='D11',fault_rows=fault)
    assert [r[17] for r in values(result)]==[b'1',b'0',b'0',b'0',b'1',b'1',b'1']


def test_d39_exact_frozen_windows_and_d09_time_bins():
    raw=table([56.,56.2,56.4,56.6,56.8,57.])
    result,_=lift_heading(raw,raw,table([56.,57.]),type_id='D39',components=[
        {'affected_source':'dual_yaw_quality','details':{'intervals':[{'start_s':56.,'end_s':56.4},[56.8,57.]]}}])
    assert [r[17] for r in values(result)]==[b'0',b'0',b'1',b'1',b'0',b'1']
    result,_=lift_heading(raw,raw,table([56.,57.]),type_id='D09',anchor_time_s=56.)
    assert [r[17] for r in values(result)]==[b'1',b'0',b'0',b'1',b'0',b'1']
