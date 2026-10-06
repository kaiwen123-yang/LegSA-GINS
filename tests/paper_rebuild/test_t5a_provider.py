"""Synthetic fixtures only: raw-to-frozen transform calls and T5a byte gates."""
import ast
import csv
import hashlib
import inspect

import numpy as np
import pytest

from legsa_gins.input_generation import status_yaw_builder
from legsa_gins.paper_rebuild.hext import heading_provider as hp
from legsa_gins.paper_rebuild.hext import t5a_provider as tp

WEEK = 2408
BASE = hp.GPS_EPOCH_UNIX + WEEK * hp.WEEK_SECONDS - hp.LEAP_SECONDS


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _table(valid=("1", "0", "1"), width=18, times=(10.0, 10.2, 10.4)):
    lines = [b"# synthetic fixture; never real-data evidence\r\n", b"\r\n"]
    for time, flag in zip(times, valid):
        tokens = [f"{time:.9f}", "30.000000000000", "120.000000000000", "50.000000000",
                  ".10", ".10", ".20", "1.000000", "2.000000", "3.000000",
                  ".05", ".05", ".05", "179.000000", "2.933193", "1", "1", flag]
        lines.append(("  " + " \t ".join(tokens[:width]) + "  \r\n").encode())
    return b"".join(lines)


def _kwargs(frozen):
    keys = [hp.time_to_itow_ms(row["tokens"][0], gps_week=WEEK, base_time=BASE)
            for row in hp._rows(frozen)[0]]
    return dict(expected_sha256=_sha(frozen), gps_week=WEEK, base_time=BASE, sequence="BY2",
                raw_yaw_rows=[{"itow_ms": key, "yaw_ned_deg": yaw}
                              for key, yaw in zip(keys, (180., 270., 0.) * len(keys))],
                pvt_flags1=dict.fromkeys(keys, 128), pvt_flags2=dict.fromkeys(keys, 128))


def test_raw_adapter_calls_both_frozen_functions_and_exact_time_branch(tmp_path, monkeypatch):
    calls = []
    original_builder = status_yaw_builder.build_a1_dual_diff_yaw_rows
    original_install = status_yaw_builder.apply_yaw_install_and_ned

    def observed_builder(path1, path2, *, base_time):
        calls.append("builder")
        with path1.open(newline="") as file1, path2.open(newline="") as file2:
            first, second = list(csv.DictReader(file1)), list(csv.DictReader(file2))
        assert [(row["header.stamp.secs"], row["header.stamp.nsecs"]) for row in first] == [
            (row["header.stamp.secs"], row["header.stamp.nsecs"]) for row in second]
        assert [int(row["header.stamp.nsecs"]) for row in first] == [2_000_000, 202_000_000, 402_000_000]
        assert all(float(row["rel_acc_n"]) == 0 for row in first + second)
        return original_builder(path1, path2, base_time=base_time)

    def observed_install(rows, *, sign, offset_deg):
        calls.append("install")
        assert sign == 1.0 and offset_deg == 0.0
        return original_install(rows, sign=sign, offset_deg=offset_deg)

    monkeypatch.setattr(status_yaw_builder, "build_a1_dual_diff_yaw_rows", observed_builder)
    monkeypatch.setattr(status_yaw_builder, "apply_yaw_install_and_ned", observed_install)
    first = np.array([[1000.125, 2000.25, 3.5]] * 3)
    second = first + [[1., 0., 0.], [0., 1., 0.], [-1., 0., 0.]]
    rows, audit = tp.raw_yaw_from_ned(first, second, itow_ms=[10002, 10202, 10402],
                                     gps_week=WEEK, base_time=BASE, adapter_root=tmp_path / "adapter",
                                     data_mode="synthetic")
    assert calls == ["builder", "install"]
    assert [row["yaw_ned_deg"] for row in rows] == [90., 180., 270.]
    assert [row["itow_ms"] for row in rows] == [10002, 10202, 10402]
    assert [row["rel_n"] for row in rows] == [1., 0., -1.]
    assert audit["synthetic_data_used"] is True and audit["semisynthetic_data_used"] is False
    assert audit["receiver_interpolation_required_count"] == 0
    assert audit["trace_payload_reads"] == 0
    assert "UNUSED_BY_YAW" in audit["accuracy_fields_role"]
    for member in audit["adapter_members"]:
        assert _sha((tmp_path / "adapter" / member["name"]).read_bytes()) == member["sha256"]


def test_adapter_never_reimplements_frozen_atan2_or_ned_formula():
    tree = ast.parse(inspect.getsource(tp))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "atan2" for node in calls)
    targets = {ast.unparse(node.func) for node in calls}
    assert "status_yaw_builder.build_a1_dual_diff_yaw_rows" in targets
    assert "status_yaw_builder.apply_yaw_install_and_ned" in targets


def test_adapter_validates_before_output_and_does_not_overwrite(tmp_path):
    args = dict(itow_ms=[10000], gps_week=WEEK, base_time=BASE, adapter_root=tmp_path / "adapter",
                data_mode="synthetic")
    with pytest.raises(tp.T5AProviderError, match="finite matching"):
        tp.raw_yaw_from_ned([[float("nan"), 0, 0]], [[0, 0, 0]], **args)
    assert not args["adapter_root"].exists()
    tp.raw_yaw_from_ned([[0, 0, 0]], [[1, 0, 0]], **args)
    with pytest.raises(FileExistsError):
        tp.raw_yaw_from_ned([[0, 0, 0]], [[1, 0, 0]], **args)


def test_r1_mask_is_frozen_bytes_and_all_non_yaw_bytes_survive():
    frozen = _table(valid=("1.0", "0.000", "1"))
    variants, audit, rows = tp.build_t5a_variants(frozen, **_kwargs(frozen))
    before, _ = hp._rows(frozen)
    after, _ = hp._rows(variants["R1"])
    assert [row["tokens"][17] for row in after] == [row["tokens"][17] for row in before]
    assert after[1]["line"] == before[1]["line"]
    assert [row["tokens"][13] for row in after] == [b"180.000000", b"179.000000", b"0.000000"]
    for payload in variants.values():
        gate = hp.validate_heading_byte_gate(frozen, payload)
        assert gate["non_heading_tokens_byte_equal"] and gate["all_whitespace_byte_equal"]
    assert audit["variant_valid_counts"] == {"R1": 2, "R5": 3}
    assert audit["epoch_set"]["raw_grid_matched_count"] == 2
    assert rows[0]["delta_raw_minus_a1_deg"] == 1.


@pytest.mark.parametrize("sequence", ["BY2", "BY2H", "BY2O"])
def test_r1_fixed_subset_records_difference_and_continues(sequence):
    frozen = _table()
    kwargs = _kwargs(frozen)
    kwargs.update(sequence=sequence, variants=("R1", "R5"), window=(10.1, 10.4))
    kwargs["pvt_flags2"][10400] = 64
    variants, audit, rows = tp.build_t5a_variants(frozen, **kwargs)
    assert audit["status"] == "PASS_D3_BYTE_AND_VALID_GATES"
    assert audit["R1_missing_valid_itow_ms"] == {"R1": [10400]}
    assert audit["A1_epochs_not_both_fixed_itow_ms"] == [10400]
    assert audit["byte_gates"]["R1"]["R1_valid_subset_of_E"]
    assert audit["byte_gates"]["R1"]["R1_excluded_exactly_PVT_not_both_fixed"]
    assert audit["byte_gates"]["R1"]["frozen_valid_tokens_byte_equal"] is False
    assert audit["counts"]["all_provider"]["variant_valid_counts"] == {"R1": 1, "R5": 2}
    assert audit["counts"]["closed_window"]["variant_valid_counts"] == {"R1": 0, "R5": 1}
    assert [row["tokens"][17] for row in hp._rows(variants["R1"])[0]] == [b"1", b"0", b"0"]
    assert rows[2]["raw_fixed_float_label"] == "FIXED_FLOAT"
    assert rows[2]["yaw_a1_token"] == "179.000000"


def test_float_variants_only_by2o_and_each_receiver_must_be_float_or_fixed():
    frozen = _table()
    kwargs = _kwargs(frozen)
    kwargs.update(sequence="BY2O", variants=("R5", "R1F", "R5F"))
    kwargs["pvt_flags2"] = {10000: 128, 10200: 64, 10400: 64}
    variants, audit, _ = tp.build_t5a_variants(frozen, **kwargs)
    assert audit["variant_valid_counts"] == {"R5": 1, "R1F": 2, "R5F": 3}
    kwargs["pvt_flags1"][10400] = 192
    with pytest.raises(tp.T5AProviderError, match="R1F valid pattern") as result:
        tp.build_t5a_variants(frozen, **kwargs)
    assert result.value.audit["R1_missing_valid_counts"]["R1F"] == 1
    kwargs["variants"] = ("R5", "R5F")
    _, audit, _ = tp.build_t5a_variants(frozen, **kwargs)
    assert audit["variant_valid_counts"] == {"R5": 1, "R5F": 2}
    assert audit["counts"]["all_provider"]["reserved_carrier_state_count"] == 1
    assert all(row["tokens"][14] == b"2.933193" for row in hp._rows(variants["R5F"])[0])
    kwargs["sequence"] = "BY2H"
    with pytest.raises(tp.T5AProviderError, match="outside"):
        tp.build_t5a_variants(frozen, **kwargs)


def test_missing_raw_and_pvt_rows_are_listed_and_invalid_without_interpolation():
    frozen = _table()
    kwargs = _kwargs(frozen)
    kwargs["variants"] = ("R5",)
    kwargs["raw_yaw_rows"].pop()
    kwargs["pvt_flags1"].pop(10200)
    variants, audit, _ = tp.build_t5a_variants(frozen, **kwargs)
    assert audit["missing_raw_itow_ms"] == [10400]
    assert audit["missing_pvt_itow_ms"] == [10200]
    assert audit["epoch_set"]["raw_grid_unmatched_itow_ms"] == [10400]
    assert [row["tokens"][17] for row in hp._rows(variants["R5"])[0]] == [b"1", b"0", b"0"]
    kwargs["variants"] = ("R1",)
    with pytest.raises(tp.T5AProviderError, match="E-minus-valid differs") as result:
        tp.build_t5a_variants(frozen, **kwargs)
    assert result.value.audit["A1_epochs_not_both_fixed_count"] == 0
    assert result.value.audit["missing_raw_itow_ms"] == [10400]


def test_byte_gate_rejects_valid_mask_non_yaw_std_and_15_column_changes():
    frozen = _table()
    variants, _, _ = tp.build_t5a_variants(frozen, **_kwargs(frozen))
    with pytest.raises(tp.T5AProviderError, match="subset"):
        tp.validate_t5a_byte_gate(frozen, variants["R5"], variant="R1")
    with pytest.raises(hp.HeadingProviderError, match="non-heading token"):
        tp.validate_t5a_byte_gate(frozen, variants["R1"].replace(b".10", b".11", 1), variant="R1")
    with pytest.raises(tp.T5AProviderError, match="yaw_std"):
        tp.validate_t5a_byte_gate(frozen, variants["R1"].replace(b"2.933193", b"2.933194", 1), variant="R1")
    frozen15 = _table(width=15)
    with pytest.raises(tp.T5AProviderError, match="18-column"):
        tp.build_t5a_variants(frozen15, **_kwargs(frozen15))


def test_bad_frozen_hash_and_duplicate_raw_epochs_fail_closed():
    frozen = _table()
    kwargs = _kwargs(frozen)
    kwargs["expected_sha256"] = "0" * 64
    with pytest.raises(hp.HeadingProviderError, match="SHA-256"):
        tp.build_t5a_variants(frozen, **kwargs)
    kwargs = _kwargs(frozen)
    kwargs["raw_yaw_rows"].append(kwargs["raw_yaw_rows"][0])
    with pytest.raises(tp.T5AProviderError, match="Duplicate"):
        tp.build_t5a_variants(frozen, **kwargs)


def test_r1_difference_gate_cannot_hide_raw_loss_as_not_both_fixed():
    frozen = _table()
    kwargs = _kwargs(frozen)
    kwargs["pvt_flags2"][10400] = 64
    variants, _, _ = tp.build_t5a_variants(frozen, **kwargs)
    with pytest.raises(tp.T5AProviderError, match="E-minus-valid differs"):
        tp.validate_t5a_byte_gate(frozen, variants["R1"], variant="R1",
                                  r1_not_both_fixed_line_indices=[])
    kwargs["raw_yaw_rows"].pop(0)
    with pytest.raises(tp.T5AProviderError, match="E-minus-valid differs") as result:
        tp.build_t5a_variants(frozen, **kwargs)
    assert result.value.audit["A1_epochs_not_both_fixed_itow_ms"] == [10400]
    assert result.value.audit["missing_raw_itow_ms"] == [10000]
    assert result.value.audit["failed_gate"]["detail"]["actual_excluded_line_indices"] == [2, 4]
    assert result.value.audit["failed_gate"]["detail"]["expected_excluded_line_indices"] == [4]


@pytest.mark.parametrize("missing_kind", ["raw", "pvt", "carrier"])
def test_r1f_all_e_gate_does_not_fabricate_missing_observations(missing_kind):
    frozen = _table(valid=("1.0", "0.000", "1"))
    kwargs = _kwargs(frozen)
    kwargs.update(sequence="BY2O", variants=("R1F",))
    kwargs["pvt_flags2"][10400] = 64
    variants, audit, _ = tp.build_t5a_variants(frozen, **kwargs)
    assert audit["byte_gates"]["R1F"]["frozen_valid_tokens_byte_equal"]
    if missing_kind == "raw":
        kwargs["raw_yaw_rows"].pop()
    elif missing_kind == "pvt":
        kwargs["pvt_flags2"].pop(10400)
    else:
        kwargs["pvt_flags2"][10400] = 0
    with pytest.raises(tp.T5AProviderError, match="R1F valid pattern") as result:
        tp.build_t5a_variants(frozen, **kwargs)
    assert result.value.audit["R1_missing_valid_itow_ms"]["R1F"] == [10400]
    assert all(row["tokens"][14] == b"2.933193" for row in hp._rows(variants["R1F"])[0])


def test_by2o_segment_closed_endpoints_and_no_carrier_counts():
    times = (3369.939, 3369.94, 3411.95, 3411.951, 3495.94, 3508.94, 3508.941)
    frozen = _table(valid=("1",) * len(times), times=times)
    kwargs = _kwargs(frozen)
    kwargs.update(sequence="BY2O", variants=("R5F",), window=(3369.94, 3508.94))
    kwargs["pvt_flags2"][3369940] = 0
    _, audit, rows = tp.build_t5a_variants(frozen, **kwargs)
    assert [row["segment"] for row in rows] == ["outside", "primary", "primary", "outside", "secondary", "secondary", "outside"]
    assert audit["counts"]["all_provider"]["no_carrier_solution_count"] == 1
    assert audit["counts"]["all_provider"]["provider_row_count"] == 7
    assert audit["counts"]["closed_window"]["provider_row_count"] == 5
    assert audit["counts"]["closed_window"]["variant_valid_counts"]["R5F"] == 4


def test_synthetic_full_provider_445_vs_window_378_counts_are_not_table_crops():
    keys = list(range(3199000, 3643001, 200))
    frozen = _table(valid=["1" if key % 1000 == 0 else "0" for key in keys],
                    times=[key / 1000 for key in keys])
    kwargs = _kwargs(frozen)
    kwargs.update(sequence="BY2O", window=(3230., 3607.))
    float_seconds = set(range(3370, 3413)) | set(range(3495, 3510))
    kwargs["pvt_flags2"] = {key: 64 if key // 1000 in float_seconds else 128 for key in keys}
    variants, audit, _ = tp.build_t5a_variants(frozen, **kwargs)
    full = audit["counts"]["all_provider"]
    closed = audit["counts"]["closed_window"]
    assert full["a1_epoch_count"] == 445 and closed["a1_epoch_count"] == 378
    assert full["variant_valid_counts"]["R1"] == 387
    assert closed["variant_valid_counts"]["R1"] == 320
    assert full["variant_valid_counts"]["R1F"] == 445
    assert closed["variant_valid_counts"]["R1F"] == 378
    assert full["a1_not_both_fixed_count"] == closed["a1_not_both_fixed_count"] == 58
    assert all(len(hp._rows(payload)[0]) == len(keys) for payload in variants.values())
