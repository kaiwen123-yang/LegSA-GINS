"""Synthetic-only D1/D4/D5 provider and frozen-config guards; no runtime launch."""
import csv
import hashlib
import io
import json
import math
import struct

import numpy as np
import pytest

from legsa_gins.input_generation.status_yaw_builder import apply_yaw_install_and_ned, wrap_deg
from legsa_gins.paper_rebuild.hext import heading_provider as hp
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import ubx_checksum

WEEK = 2408
BASE = hp.GPS_EPOCH_UNIX+WEEK*hp.WEEK_SECONDS-hp.LEAP_SECONDS


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _table(width=18, valid=(1,0,1)):
    lines = [b"# synthetic fixture; never real evidence\r\n", b"\r\n"]
    for time, yaw, flag in zip((10.,10.2,10.4),(179.,0.,359.),valid):
        tokens = [f"{time:.9f}","30.000000000000","120.000000000000","50.000000000",
                  ".10",".10",".20","1.000000","2.000000","3.000000",".05",".05",".05",f"{yaw:.6f}","2.933193"]
        if width == 18:
            tokens += ["1","1",str(flag)]
        lines.append(("  "+" \t ".join(tokens)+"  \r\n").encode())
    return b"".join(lines)


def _kwargs(payload):
    # NED headings 180,270,0: wrapped differences from A1 are +1,+1.
    return dict(expected_sha256=_sha(payload),gps_week=WEEK,base_time=BASE,
                solution_itow_ms=[10000,10200,10400],b21_ned_m=[[0,.35,0],[-.35,0,0],[0,-.35,0]],
                pvt_flags1={10000:128,10200:128,10400:128},
                pvt_flags2={10000:128,10200:64,10400:64},window=(10.1,10.4))


def test_d1_full_file_epoch_set_is_not_clipped_and_exact_v2_inverse():
    payload = _table()
    epochs = hp.extract_epoch_set(payload,expected_sha256=_sha(payload),gps_week=WEEK,base_time=BASE,
                                  window=(10.1,10.4))
    assert epochs["itow_ms"]==[10000,10400]
    assert epochs["epoch_set_size"]==2 and epochs["closed_window_epoch_set_size"]==1
    # V2 serializes a floating Unix-time subtraction; inverse tolerates only its submicrosecond rounding.
    base_time = 1772784000.
    key = 461223802
    original = hp.GPS_EPOCH_UNIX+WEEK*hp.WEEK_SECONDS+key/1000-18-base_time
    assert hp.time_to_itow_ms(f"{original:.9f}",gps_week=WEEK,base_time=base_time)==key
    with pytest.raises(hp.HeadingProviderError,match="iTOW"):
        hp.time_to_itow_ms("10.00002",gps_week=WEEK,base_time=BASE)
    with pytest.raises(hp.HeadingProviderError,match="SHA-256"):
        hp.extract_epoch_set(payload,expected_sha256="0"*64,gps_week=WEEK,base_time=BASE)


def test_d4_formula_is_exact_a1_fixed_transform_for_all_quadrants():
    for north,east in ((1.,0.),(0.,1.),(-1.,0.),(0.,-1.),(.2,-.3)):
        candidate = wrap_deg(-math.degrees(math.atan2(east,north)))
        frozen = apply_yaw_install_and_ned([{"yaw_baseline_deg":candidate}],sign=1.,offset_deg=0.)[0]
        body,yaw = hp.baseline_heading([north,east,.1])
        assert body == frozen["yaw_body_deg"]
        assert yaw == frozen["yaw_ned_deg"]
    assert hp.both_receivers_fixed(128|15,128|15)
    assert not hp.both_receivers_fixed(128,64)
    assert not hp.both_receivers_fixed(192,128)


def test_s5u_and_s5m_preserve_every_other_token_and_whitespace():
    frozen = _table()
    variants,audit,rows = hp.build_heading_variants(frozen,**_kwargs(frozen))
    original = frozen.splitlines(keepends=True)
    uniform = variants["S5U"].splitlines(keepends=True)
    matched = variants["S5M"].splitlines(keepends=True)
    assert matched[2]==original[2] and matched[4]==original[4]
    assert matched[3]==uniform[3] and matched[3]!=original[3]
    assert [line.split()[17] for line in uniform[2:]]==[b"1",b"0",b"0"]
    assert all(line.split()[14]==b"2.933193" for line in uniform[2:])
    assert audit["byte_gates"]["S5U"]["all_whitespace_byte_equal"] is True
    assert audit["byte_gates"]["S5M"]["preserved_A1_full_lines"]==2
    assert audit["A1_epochs_not_both_fixed_count"]==1
    assert audit["consistency_on_E"]["mean_deg"]==pytest.approx(1.)
    assert audit["consistency_on_E"]["std_population_deg"]==0.
    assert [row["yaw_5hz_minus_a1_deg"] for row in rows]==[1.,None,1.]
    assert audit["trace_payload_reads"]==0


def test_byte_gate_rejects_other_columns_whitespace_and_s5m_line_mutation():
    frozen = _table()
    variants,_,_ = hp.build_heading_variants(frozen,**_kwargs(frozen))
    with pytest.raises(hp.HeadingProviderError,match="non-heading token"):
        hp.validate_heading_byte_gate(frozen,variants["S5U"].replace(b"30.000000000000",b"31.000000000000",1))
    with pytest.raises(hp.HeadingProviderError,match="whitespace"):
        hp.validate_heading_byte_gate(frozen,variants["S5U"].replace(b" \t ",b"  ",1))
    with pytest.raises(hp.HeadingProviderError,match="full-line"):
        hp.validate_heading_byte_gate(frozen,variants["S5U"],preserved_line_indices=[2])


def test_empty_a1_is_unavailable_but_s5_providers_continue():
    frozen = _table(valid=(0,0,0))
    variants,audit,_ = hp.build_heading_variants(frozen,**_kwargs(frozen))
    assert variants["S5U"]==variants["S5M"]
    assert audit["epoch_set"]["status"]=="UNAVAILABLE"
    assert audit["consistency_on_E"]["reason"]=="EMPTY_A1_EPOCH_SET"


def test_missing_epochs_fail_and_fifteen_columns_never_mask_invalid_as_valid():
    frozen = _table()
    kwargs = _kwargs(frozen)
    kwargs["pvt_flags1"].pop(10200)
    with pytest.raises(hp.HeadingProviderError,match="exact-iTOW"):
        hp.build_heading_variants(frozen,**kwargs)
    frozen = _table(width=15)
    with pytest.raises(hp.HeadingProviderError,match="15-column"):
        hp.build_heading_variants(frozen,**_kwargs(frozen))
    kwargs = _kwargs(frozen)
    kwargs["pvt_flags2"] = dict.fromkeys(kwargs["solution_itow_ms"],128)
    variants,audit,_ = hp.build_heading_variants(frozen,**kwargs)
    assert variants["S5M"]==frozen
    assert audit["epoch_set"]["columns"]==15 and audit["epoch_set"]["epoch_set_size"]==3


def _pvt_csv(flags=(128,64)):
    stream = io.StringIO()
    writer = csv.DictWriter(stream,fieldnames=["name","data"])
    writer.writeheader()
    for index,flag in enumerate(flags):
        payload = bytearray(92)
        struct.pack_into("<I",payload,0,10000+index*200)
        payload[20]=3  # fixType is deliberately identical; carrSoln differs.
        payload[21]=flag
        frame = b"\xb5\x62\x01\x07"+struct.pack("<H",len(payload))+payload
        frame += bytes(ubx_checksum(frame[2:]))
        writer.writerow({"name":"UBX-NAV-PVT","data":json.dumps(list(frame))})
    return stream.getvalue().encode("utf-8-sig")


def test_raw_pvt_flags_are_decoded_from_byte21_not_fix_type():
    payload = _pvt_csv()
    assert hp.pvt_flags_from_csv_bytes(payload,expected_sha256=_sha(payload))=={10000:128,10200:64}
    with pytest.raises(hp.HeadingProviderError,match="SHA-256"):
        hp.pvt_flags_from_csv_bytes(payload,expected_sha256="0"*64)


def test_runtime_clone_only_gnsspath_and_frozen_file_gates(tmp_path):
    frozen = b"gnsspath: old.gnss\noutputpath: frozen-output\nimupath: unchanged.imu\nuse_hv: true\nsigma: 2.933193\n"
    candidate,audit = hp.clone_runtime_config(frozen,expected_sha256=_sha(frozen),gnsspath="new.gnss")
    assert audit["changed_fields"]==["gnsspath"]
    assert audit["non_gnsspath_sha256_before"]==audit["non_gnsspath_sha256_after"]
    with pytest.raises(hp.HeadingProviderError,match="non-gnsspath"):
        hp.validate_config_gnsspath_only(frozen,candidate.replace(b"unchanged.imu",b"changed.imu"))
    with pytest.raises(hp.HeadingProviderError,match="Duplicate"):
        hp.config_without_gnsspath_hash(b"gnsspath: a\ngnsspath: b\n")
    path = tmp_path/"frozen.imu"
    path.write_bytes(b"synthetic frozen IMU")
    specs = {"IMU":{"path":path,"sha256":_sha(path.read_bytes())}}
    assert hp.verify_frozen_inputs(specs)["IMU"]["size_bytes"]==20
    path.write_bytes(b"mutated")
    with pytest.raises(hp.HeadingProviderError,match="SHA-256"):
        hp.verify_frozen_inputs(specs)
    with pytest.raises(hp.HeadingProviderError,match="trace"):
        hp.verify_frozen_inputs({"trace":{"path":tmp_path/"never-open","sha256":"0"*64}})
