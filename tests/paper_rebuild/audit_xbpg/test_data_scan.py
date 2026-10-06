"""Parser boundary tests; these synthetic records never enter real-data tables."""
import struct
import binascii
import pytest

from legsa_gins.paper_rebuild.audit_xbpg.data_scan import (
    GO2_DIMS, GO2_SCALARS, clean_terminal_line, decode_ubx, decimal_ns,
    parse_bytes_cell, parse_go2_block, scan_go2, timeline, ubx_frames, decode_novb,
)


def go2_block():
    out=['stamp:', '  sec: 1767615915', '  nanosec: 804621364', 'imu_state:']
    for key,n in GO2_DIMS.items():
        if key.startswith('imu_state.'):
            out.append('  '+key.split('.')[1]+':')
            out.extend('  - -1.25e-3' for _ in range(n))
    out.append('  temperature: 79')
    for key,n in GO2_DIMS.items():
        if not key.startswith('imu_state.'):
            out.append(key+':')
            out.extend('- -2.5' for _ in range(n))
    for key in GO2_SCALARS:
        if '.' not in key: out.append(key+': 0')
    return out


def frame(c,m,p):
    body=bytes((c,m))+struct.pack('<H',len(p))+p
    a=b=0
    for x in body: a=(a+x)&255;b=(b+a)&255
    return b'\xb5\x62'+body+bytes((a,b))


def test_integer_time_no_float_roundtrip():
    assert decimal_ns('1767615915.804621364')==1767615915804621364


def test_go2_negative_scientific_and_exact_stamp():
    d=parse_go2_block(go2_block())
    assert d['time_ns']==1767615915804621364
    assert d['imu_state.gyroscope']==[-.00125]*3
    assert d['foot_speed_body']==[-2.5]*12


@pytest.mark.parametrize('mutation', ['dimension','duplicate','nanoseconds','nonfinite'])
def test_go2_rejects(mutation):
    b=go2_block()
    if mutation=='dimension': b.remove('  - -1.25e-3')
    if mutation=='duplicate': b+=['mode: 1']
    if mutation=='nanoseconds': b[2]='  nanosec: 1000000000'
    if mutation=='nonfinite': b[-1]='yaw_speed: .nan'
    with pytest.raises(ValueError): parse_go2_block(b)


def test_terminal_control_rendering():
    assert clean_terminal_line('\x1b[31mabc\bD\x1b[0m\r\n')=='abD'
    assert clean_terminal_line('\x1b]0;title\x07stamp:\r\n')=='stamp:'


def test_go2_loss_accounting(tmp_path):
    p=tmp_path/'input.txt'
    b='\n'.join(go2_block())
    p.write_text('Script started\n'+b+'\n---\nstamp:\n  sec: 123\n')
    r=scan_go2(p,tmp_path/'out.npz')
    assert r['rows']==1 and r['total_message_candidates']==2
    assert len(r['rejects'])==1 and r['rejects'][0]['delimiter_terminated'] is False


def test_literal_eval_is_not_eval():
    with pytest.raises((ValueError,SyntaxError)):
        parse_bytes_cell("__import__('os').system('false')")
    with pytest.raises(ValueError): parse_bytes_cell("'not bytes'")
    assert parse_bytes_cell("b'\\xb5b'")==b'\xb5b'


def test_ubx_length_checksum_and_junk():
    f=frame(1,19,bytes(28))
    assert list(ubx_frames(f))[0][:2]==(1,19)
    for damaged in (f[:-1],f[:-1]+bytes((f[-1]^1,)),b'x'+f):
        with pytest.raises(ValueError): list(ubx_frames(damaged))


def test_hpposecef_signed_hp_units_and_flag_byte():
    p=bytearray(28);struct.pack_into('<Iiii',p,4,123400,100,-200,300)
    struct.pack_into('<bbb',p,20,-99,50,-1);p[23]=1
    struct.pack_into('<I',p,24,12345)
    d=decode_ubx(1,19,p)
    assert d['x_m']==pytest.approx(.9901)
    assert d['y_m']==pytest.approx(-1.995)
    assert d['pacc_m']==pytest.approx(1.2345)
    assert d['invalid_ecef'] is True


def test_pvt_carrier_flags_not_fix_type():
    p=bytearray(92);p[20]=3;p[21]=129
    d=decode_ubx(1,7,p)
    assert d['fix_type']==3 and d['carrSoln']==2 and d['gnss_fix_ok']


def test_rawx_declared_measurement_count():
    p=bytearray(16);p[11]=1
    with pytest.raises(ValueError,match='numMeas'):decode_ubx(2,21,p)


def test_timeline_preserves_duplicate_out_of_order():
    d=timeline([0,2_000_000,2_000_000,1_000_000,202_000_000])
    assert d['duplicate_n']==1 and d['out_of_order_n']==1
    assert d['gaps_gt_100ms']==1


def test_novb_crc_and_layout():
    body=bytearray(154);body[:4]=b'\xaa\x44\x12\x1c'
    struct.pack_into('<H',body,4,1465);struct.pack_into('<H',body,8,126)
    struct.pack_into('<H',body,14,2400);struct.pack_into('<I',body,16,131133000)
    struct.pack_into('<d',body,36,39.9)
    data=bytes(body)+struct.pack('<I',binascii.crc32(body,0xffffffff)^0xffffffff)
    name,d=decode_novb(data)
    assert name=='NOV_B-INSPVAX' and d['lat_deg']==39.9
    with pytest.raises(ValueError,match='crc32'):decode_novb(data[:-1]+bytes((data[-1]^1,)))


def test_go2_wrong_indentation_is_not_silently_repaired():
    b=go2_block();b[b.index('  - -1.25e-3')]='- -1.25e-3'
    with pytest.raises(ValueError,match='invalid_list_item'):parse_go2_block(b)
