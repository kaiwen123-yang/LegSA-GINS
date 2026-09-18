"""Synthetic-only T5bc uncertainty substitution and exact-identity gates."""
import csv
import hashlib
import io
import math
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext import heading_provider as hp
from legsa_gins.paper_rebuild.hext import t5a_provider as t5a
from legsa_gins.paper_rebuild.hext import t5bc_provider as tb


WEEK = 2408
BASE = hp.GPS_EPOCH_UNIX + WEEK * hp.WEEK_SECONDS - hp.LEAP_SECONDS
KEYS = (10000, 10200, 10400)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def table():
    lines = [b"# synthetic only\r\n", b"\r\n"]
    for key in KEYS:
        tokens = [f"{key / 1000:.9f}", "30", "120", "50", ".10", ".10", ".20",
                  "1", "2", "3", ".05", ".05", ".05", "179.000000", "2.933193", "1", "1", "1"]
        lines.append(("  " + " \t ".join(tokens) + "  \r\n").encode())
    return b"".join(lines)


def inputs():
    return dict(raw_yaw_rows=[dict(itow_ms=key, yaw_ned_deg=yaw, rel_n=n, rel_e=e, rel_d=d)
                              for key, yaw, (n, e, d) in zip(KEYS, (90., 180., 0.), ((1., 0., .1), (0., 1., .2), (-1., 0., .3)))],
                pacc1_m=dict(zip(KEYS, (.003, .006, .009))),
                pacc2_m=dict(zip(KEYS, (.004, .008, .012))),
                pvt_flags1=dict.fromkeys(KEYS, 128), pvt_flags2=dict.fromkeys(KEYS, 128),
                baseline_m=.5, k=2., sigma_deg=.0002)


def reference(base, data):
    result, _, _ = t5a.build_t5a_variants(
        base, expected_sha256=sha(base), gps_week=WEEK, base_time=BASE, sequence="BY2",
        variants=("R5",), raw_yaw_rows=data["raw_yaw_rows"],
        pvt_flags1=data["pvt_flags1"], pvt_flags2=data["pvt_flags2"])
    return result["R5"]


def arguments(base, data, r5=None):
    r5 = reference(base, data) if r5 is None else r5
    return dict(expected_sha256=sha(base), gps_week=WEEK, base_time=BASE,
                weights=tb.prepare_heading_weights(**data), r5_reference_bytes=r5,
                r5_reference_sha256=sha(r5), window=(10.2, 10.4),
                data_mode="synthetic", f04_yaw_std_min_deg=1.5)


@pytest.mark.parametrize('key', ['baseline_m', 'k', 'sigma_deg'])
@pytest.mark.parametrize('value', [True, False, np.bool_(True)])
def test_boolean_calibration_values_are_not_numbers(key, value):
    data = inputs()
    data[key] = value
    with pytest.raises(tb.T5BCProviderError, match='Explicit finite'):
        tb.prepare_heading_weights(**data)


@pytest.mark.parametrize('value', [True, np.bool_(False)])
def test_boolean_accuracy_cannot_enter_a_valid_provider_row(value):
    data = inputs()
    data['pacc1_m'][10000] = value
    with pytest.raises(tb.T5BCProviderError, match='valid row lacks pAcc'):
        tb.build_heading_variants(table(), **arguments(table(), data))


def test_formula_units_no_floor_and_full_window_byte_gates():
    base, data = table(), inputs()
    payloads, audit = tb.build_heading_variants(base, **arguments(base, data))
    assert set(payloads) == {"R5", "R5W", "R5SIGMA"}
    assert all(row['tokens'][14] == b'2.933193' for row in hp._rows(payloads['R5'])[0])
    after = hp._rows(payloads["R5W"])[0]
    assert [float(row["tokens"][14]) for row in after] == pytest.approx(
        [math.degrees(.02), math.degrees(.04), math.degrees(.06)])
    for payload in payloads.values():
        assert hp.validate_heading_byte_gate(base, payload)["all_whitespace_byte_equal"]
    assert all(float(row["tokens"][14]) == .0002 for row in hp._rows(payloads["R5SIGMA"])[0])
    sigma = audit["variants"]["R5SIGMA"]["std"]
    assert sigma["all_provider"]["all_rows"]["loader_below_0p001_deg_count"] == 3
    assert sigma["closed_window"]["yaw_valid_rows"]["count"] == 2
    assert sigma["all_provider"]["all_rows"]["loader_effective_minimum_deg"] == .001
    assert sigma["all_provider"]["all_rows"]["f04_below_explicit_std_min_count"] == 3
    assert audit["provider_cropped"] is False and audit["provider_std_clipping"] is False
    assert audit["synthetic_data_used"] is True and audit["semisynthetic_data_used"] is False


def test_same_immutable_weights_apply_to_degraded_non_yaw_source():
    base, data = table(), inputs()
    args = arguments(base, data)
    weights = args["weights"]
    degraded = base.replace(b"\t .10 \t", b"\t 99.0 \t").replace(b"\t .20 \t", b"\t 88.0 \t")
    original, _ = tb.build_heading_variants(base, **args)
    changed, audit = tb.build_heading_variants(degraded, **{**args, "expected_sha256": sha(degraded)})
    for variant in original:
        before, after = hp._rows(original[variant])[0], hp._rows(changed[variant])[0]
        assert all([x["tokens"][i] for i in (13, 14, 17)] == [y["tokens"][i] for i in (13, 14, 17)] for x, y in zip(before, after))
        assert hp.validate_heading_byte_gate(degraded, changed[variant])["passed"]
    assert audit["weights_sha256"] == weights.sha256
    with pytest.raises(FrozenInstanceError):
        weights.k = 3.
    data["pacc1_m"][10000] = 50.
    assert weights.epochs[0].pacc1_m == .003


def test_float_missing_pvt_and_missing_accuracy_are_distinct():
    base, data = table(), inputs()
    data["pvt_flags2"][10200] = 64
    data["pvt_flags1"].pop(10400)
    data["pacc2_m"].pop(10400)
    payloads, audit = tb.build_heading_variants(base, **arguments(base, data))
    for payload in payloads.values():
        assert [row["tokens"][17] for row in hp._rows(payload)[0]] == [b"1", b"0", b"0"]
    assert audit["inactive_r5w_std_retained_missing_pacc_itow_ms"] == [10400]
    assert hp._rows(payloads["R5W"])[0][-1]["tokens"][14] == b"2.933193"
    weights = tb.prepare_heading_weights(**data)
    assert "NOT_BOTH_FIXED" in weights.epochs[1].issues
    assert set(weights.epochs[2].issues) == {"MISSING_PVT", "UNAVAILABLE_PACC2_M"}


def test_valid_missing_pacc_cannot_be_hidden_by_changing_validity():
    base, data = table(), inputs()
    data["pacc2_m"].pop(10000)
    with pytest.raises(tb.T5BCProviderError, match="valid row lacks pAcc") as error:
        tb.build_heading_variants(base, **arguments(base, data))
    assert error.value.audit["itow_ms"] == 10000
    assert "UNAVAILABLE_PACC2_M" in error.value.audit["issues"]


def test_independent_r5_mask_heading_and_identity_gates():
    base, data = table(), inputs()
    original = reference(base, data)
    data["pvt_flags2"][10200] = 64
    with pytest.raises(tb.T5BCProviderError, match="validity differs"):
        tb.build_heading_variants(base, **arguments(base, data, original))
    data = inputs()
    data["raw_yaw_rows"][0]["yaw_ned_deg"] = 90.01
    with pytest.raises(tb.T5BCProviderError, match="heading token mismatch"):
        tb.build_heading_variants(base, **arguments(base, data, original))
    args = arguments(base, inputs())
    with pytest.raises(hp.HeadingProviderError, match="SHA-256"):
        tb.build_heading_variants(base, **{**args, "expected_sha256": "0" * 64})
    modified = original.replace(b"10.200000000", b"10.201000000")
    with pytest.raises(tb.T5BCProviderError, match="iTOW identity"):
        tb.build_heading_variants(base, **{**args, "r5_reference_bytes": modified, "r5_reference_sha256": sha(modified)})


def test_explicit_std_gate_catches_non_yaw_and_whitespace_edits():
    base, data = table(), inputs()
    args = arguments(base, data)
    payloads, _ = tb.build_heading_variants(base, **args)
    for bad in (payloads["R5W"].replace(b".10", b".11", 1), payloads["R5W"].replace(b" \t ", b"   ", 1)):
        with pytest.raises(hp.HeadingProviderError, match="byte gate"):
            tb.validate_variant_byte_gate(base, bad, r5_reference_bytes=args["r5_reference_bytes"])


def test_sidecar_copies_exact_time_and_uses_empty_invalid_cells():
    base, data = table(), inputs()
    data["raw_yaw_rows"].pop(1)
    data["pacc1_m"].pop(10200)
    data["pvt_flags2"][10400] = 64
    payload, audit = tb.build_baseline3d_sidecar(
        base, expected_sha256=sha(base), gps_week=WEEK, base_time=BASE,
        weights=tb.prepare_heading_weights(**data), data_mode="synthetic")
    rows = list(csv.DictReader(io.StringIO(payload.decode())))
    assert list(rows[0]) == ["time", "b_n", "b_e", "b_d", "pAcc1", "pAcc2", "valid"]
    assert [row["time"] for row in rows] == [row["tokens"][0].decode() for row in hp._rows(base)[0]]
    assert rows[0]["b_n"] == "1" and float(rows[0]["pAcc1"]) == .003
    assert rows[1]["b_n"] == rows[1]["b_e"] == rows[1]["b_d"] == rows[1]["pAcc1"] == ""
    assert [row["valid"] for row in rows] == ["1", "0", "0"]
    assert "MISSING_RAW_HEADING" in audit["rows"][1]["reasons"]
    assert audit["rows"][2]["reasons"] == ["NOT_BOTH_FIXED"]
    assert audit["valid_count"] == 1 and audit["interpolation_used"] is False


@pytest.mark.parametrize("field,value", [("baseline_m", 0.), ("k", -1.), ("sigma_deg", float("nan"))])
def test_explicit_calibration_values_are_validated(field, value):
    data = inputs()
    data[field] = value
    with pytest.raises(tb.T5BCProviderError, match="Explicit finite"):
        tb.prepare_heading_weights(**data)


def test_no_nearest_epoch_join_and_no_adapter_accuracy_substitution():
    data = inputs()
    data["pacc1_m"] = {10001: .003, 10201: .006, 10401: .009}
    weights = tb.prepare_heading_weights(**data)
    assert all(epoch.pacc1_m is None for epoch in weights.epochs if epoch.itow_ms in KEYS)
    assert tb.raw_yaw_from_ned is t5a.raw_yaw_from_ned
    data["raw_yaw_rows"].append(data["raw_yaw_rows"][0])
    with pytest.raises(tb.T5BCProviderError, match="Duplicate raw"):
        tb.prepare_heading_weights(**data)


def test_zero_std_is_reported_without_provider_floor():
    base, data = table(), inputs()
    data.update(k=0., sigma_deg=0.)
    payloads, audit = tb.build_heading_variants(base, **arguments(base, data))
    assert all(row["tokens"][14] == b"0" for key, payload in payloads.items() if key != 'R5' for row in hp._rows(payload)[0])
    assert audit["variants"]["R5W"]["std"]["all_provider"]["all_rows"]["loader_below_0p001_deg_count"] == 3


@pytest.mark.parametrize('changed,reason,itow', [(b'10.200250000','V2_ITOW_ROUNDTRIP_UNMATCHED_1US',None),
    (b'10.201000000','NO_EXACT_R5_REFERENCE_TIME',10201)])
def test_d57_unmatched_is_explicit_invalid_without_interpolation(changed,reason,itow):
    base,data=table(),inputs()
    r5=reference(base,data)
    altered=base.replace(b'10.200000000',changed)
    args=arguments(altered,data,r5)
    args.update(allow_unmatched_times=True,subset_case_id='D57_seed_00')
    payloads,audit=tb.build_heading_variants(altered,**args)
    mapped=tb.prepared_raw_rows(altered,**{k:v for k,v in args.items() if k not in ('window','data_mode','f04_yaw_std_min_deg')})
    assert mapped[1]['itow_ms']==itow and mapped[1]['raw_valid'] is False
    assert mapped[1]['reasons']==[reason]
    for payload in payloads.values():
        assert [r['tokens'][17] for r in hp._rows(payload)[0]]==[b'1',b'0',b'1']
        assert hp.validate_heading_byte_gate(altered,payload)['passed']
    sidecar,_=tb.build_baseline3d_sidecar(altered,expected_sha256=sha(altered),gps_week=WEEK,
        base_time=BASE,weights=args['weights'],data_mode='synthetic',prepared_rows=mapped,
        allow_unmatched_times=True,subset_case_id='D57_seed_00')
    row=list(csv.DictReader(io.StringIO(sidecar.decode())))[1]
    assert row['valid']=='0' and row['b_n']==row['pAcc1']==''
    assert row['time']==changed.decode() and len(audit['unmatched_epochs'])==1
    with pytest.raises(tb.T5BCProviderError,match='D57-only'):
        tb.build_heading_variants(altered,**{**args,'subset_case_id':'D56_seed_00'})


def test_all_old_yaw_faults_replaced_and_b3_scalar_channel_disabled():
    base,data=table(),inputs(); args=arguments(base,data)
    corrupted=base.replace(b'179.000000',b'999.000000').replace(b'2.933193',b'88.0')
    outputs,_=tb.build_heading_variants(corrupted,**{**args,'expected_sha256':sha(corrupted)})
    assert [r['tokens'][13] for r in hp._rows(outputs['R5'])[0]]==[b'90.000000',b'180.000000',b'0.000000']
    payload,audit=tb.build_baseline3d_gnss(corrupted,expected_sha256=sha(corrupted))
    assert audit['passed'] and audit['scalar_yaw_valid_count']==0
    assert all(r['tokens'][17]==b'0' for r in hp._rows(payload)[0])


def test_real_clean_provider_role_is_preserved_without_synthetic_flags():
    base,data=table(),inputs(); args=arguments(base,data)
    _,audit=tb.build_heading_variants(base,**{**args,'data_mode':'real_clean'})
    assert audit['data_mode']=='real_clean'
    assert audit['synthetic_data_used'] is audit['semisynthetic_data_used'] is False
    _,audit=tb.build_baseline3d_sidecar(base,expected_sha256=sha(base),gps_week=WEEK,base_time=BASE,
        weights=args['weights'],data_mode='real_clean')
    assert audit['data_mode']=='real_clean'
