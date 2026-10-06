"""Synthetic-only tests of T5bc pure reporting; no native/evaluator/raw access."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.hext import t5bc_reporting as report


def row(sequence="BY2", profile="F02", version="v3", value="1.230000000000000"):
    result = dict.fromkeys(report.TABLE_FIELDS, report.UNAVAILABLE)
    result.update(sequence_id=sequence, method_id=profile, config=profile,
                  start_convention=report.FROZEN, evaluator_contract="evaluator_contract_" + version,
                  evaluation_status="COMPLETED", failure_classification="NONE",
                  h_rmse_m=value, roll_rmse_deg="2.00000", pitch_rmse_deg="3.00000",
                  main_row="True", manuscript_row="True", code_commit="f" * 40,
                  output_epoch_count="7", matched_epoch_count="7", coverage_ratio="1.00000")
    return result


def inputs(version="v3"):
    frozen = [(i, row(s, p, version)) for i, (s, p) in enumerate(
        ((s, p) for s in report.SEQUENCES for p in report.PROFILES), 2)]
    t5a = [{**row(s, p, version, "1.250000000000000"), "variant": "R5"}
           for s in report.SEQUENCES for p in ("F02", "F04")]
    literature = [row(s, p, version, "0.9000000000000")
                  for s in report.SEQUENCES for p in ("LC01", "LC01-S")]
    return frozen, t5a, literature


def payload(sequence="BY2", profile="F04", variant="R5W", version="v3", **updates):
    case = updates.get("case_id", updates.get("subset_case_id"))
    data_mode = updates.get("data_mode", "synthetic" if case is None else "real_raw" if case == "C00_clean_normal" else "semisynthetic")
    source = {**row(sequence, profile, version, "1.240000000000000"),
              "configuration_id": profile, "variant": variant, "data_mode": data_mode,
              "synthetic_data_used": data_mode == "synthetic", "semisynthetic_data_used": data_mode == "semisynthetic", **updates}
    return {"row": source, "audit": {"passed": True, "trace_open_count": 1}, "body_frame_bias": {}}


def pilot(evaluations=(), version="v3"):
    frozen, t5a, literature = inputs(version)
    return report.pilot_rows(frozen, t5a, evaluations, literature, version=version, data_mode="synthetic")


def select(rows, sequence="BY2", profile="F04", variant="R5W"):
    return next(r for r in rows if r["sequence_id"] == sequence and r["configuration_id"] == profile
                and r["variant"] == variant)


def test_authorized_matrix_exact_tokens_dual_deltas_and_no_invented_a04_r5():
    rows = pilot([payload()])
    assert len(rows) == 36
    assert len(report.sequence_slots()) == 15
    assert all(r["synthetic_data_used"] is True for r in rows if r["evaluation_status"] == "COMPLETED")
    assert all(r["synthetic_data_used"] == report.UNAVAILABLE for r in rows if r["evaluation_status"] == "NOT_RUN")
    frozen, _, literature = inputs()
    assert all(rows[0][key] == frozen[0][1][key] for key in report.TABLE_FIELDS)
    assert all(rows[-6][key] == literature[0][key] for key in report.TABLE_FIELDS)
    candidate = select(rows)
    assert candidate["delta_vs_frozen_h_rmse_m"] == "0.010000000000000"
    assert candidate["delta_vs_t5a_r5_h_rmse_m"] == "-0.010000000000000"
    assert candidate["delta_vs_frozen_body_forward_bias_m"] == report.UNAVAILABLE
    a04 = select(rows, profile="A04", variant="B3")
    assert a04["delta_vs_t5a_r5_h_rmse_m"] == report.UNAVAILABLE
    assert a04["evaluation_status"] == "NOT_RUN" and a04["h_rmse_m"] == report.UNAVAILABLE
    assert not [r for r in rows if r["configuration_id"] == "A04" and r["variant"] in ("R5W", "R5SIGMA", report.T5A_R5)]


def test_comparators_are_matched_by_sequence_and_configuration_not_row_position():
    frozen, t5a, literature = inputs()
    for _, item in frozen:
        if item["sequence_id"] == "BY2H" and item["method_id"] == "F04":
            item["h_rmse_m"] = "4.00000000"
    candidate = payload("BY2H", "F04", h_rmse_m="4.25000000")
    rows = report.pilot_rows(list(reversed(frozen)), list(reversed(t5a)), [candidate],
                            list(reversed(literature)), version="v3", data_mode="synthetic")
    assert select(rows, "BY2H", "F04")["delta_vs_frozen_h_rmse_m"] == "0.25000000"
    assert select(rows, "BY2", "F04")["delta_vs_frozen_h_rmse_m"] == report.UNAVAILABLE


@pytest.mark.parametrize("status", ["UNAVAILABLE_EVALUATION_FAILED", "NOT_RUN_ALGORITHM_FAILURE", "TECHNICAL_INVALID"])
def test_failed_new_rows_cannot_leak_stale_numbers_or_replace_frozen(status):
    source = payload(evaluation_status=status, h_rmse_m="0.0", body_forward_bias_m="0.0")
    source["body_frame_bias"] = {"forward_signed_mean_m": "0.0"}
    original = deepcopy(source)
    rows = pilot([source])
    candidate = select(rows)
    assert candidate["h_rmse_m"] == candidate["body_forward_bias_m"] == report.UNAVAILABLE
    assert candidate["delta_vs_frozen_h_rmse_m"] == report.UNAVAILABLE
    assert select(rows, variant=report.FROZEN)["h_rmse_m"] == "1.230000000000000"
    assert source == original


@pytest.mark.parametrize("field,value", [("h_rmse_m", "nan"), ("roll_rmse_deg", float("inf"))])
def test_nonfinite_new_metrics_make_entire_new_row_unavailable(field, value):
    candidate = select(pilot([payload(**{field: value})]))
    assert candidate["evaluation_status"] == "UNAVAILABLE_NONFINITE_METRICS"
    assert candidate["h_rmse_m"] == candidate["roll_rmse_deg"] == report.UNAVAILABLE


def test_available_capture_requires_audit_and_rejects_bad_or_duplicate_slots():
    bad = payload()
    bad["audit"]["passed"] = False
    with pytest.raises(ValueError, match="capture/disposition"):
        pilot([bad])
    bad = payload()
    bad["row"]["metrics_admitted"] = False
    with pytest.raises(ValueError, match="Rejected evaluator"):
        pilot([bad])
    with pytest.raises(ValueError, match="unauthorized"):
        pilot([payload(profile="A04")])
    with pytest.raises(ValueError, match="Duplicate"):
        pilot([payload(), payload()])
    with pytest.raises(ValueError, match="Semisynthetic"):
        pilot([payload(data_mode="semisynthetic")])


def test_missing_comparator_and_literature_are_not_silently_dropped():
    frozen, t5a, literature = inputs()
    with pytest.raises(ValueError, match="Missing same-sequence"):
        report.pilot_rows(frozen[:-1], t5a, [], literature, version="v3")
    with pytest.raises(ValueError, match="Six pinned"):
        report.pilot_rows(frozen, t5a, [], literature[:-1], version="v3")
    with pytest.raises(ValueError, match="Duplicate"):
        report.pilot_rows(frozen + [frozen[0]], t5a, [], literature, version="v3")


def test_v2_is_parallel_and_mismatched_evaluator_is_not_reused():
    rows = pilot([payload(version="v3")], version="v2")
    assert select(rows)["evaluation_status"] == "NOT_RUN"
    assert all(r["evaluator_contract"] == "evaluator_contract_v2" for r in rows)


def test_complete_matrix_uses_declared_table_schema_and_never_mutates_inputs():
    evaluations = [payload(s, p, v) for s, p, v in report.sequence_slots()]
    original = deepcopy(evaluations)
    result = pilot(evaluations)
    assert len(result) == 36
    assert all(set(r) == set(report.PILOT_FIELDS) for r in result)
    assert all(r["evaluation_status"] == "COMPLETED" for r in result)
    assert evaluations == original


WINDOW = [3186., 3563.]


def errors():
    values = np.arange(1., 8.)
    return pd.DataFrame({"time": [3186., 3369.94, 3411.95, 3440., 3495.94, 3508.94, 3563.],
                         "horizontal_err_m": values / 10, "position_3d_err_m": values / 9,
                         "err_u_m": -values / 20, "yaw_err_deg": values - 4,
                         "roll_err_deg": values / 5, "pitch_err_deg": -values / 7})


def segments(frame, **kwargs):
    return report.derive_by2o_segments(frame, profile="F04", variant="R5W", version="v3",
                                      window=WINDOW, source="SYNTHETIC", data_mode="synthetic", **kwargs)


def test_segment_arithmetic_closed_regions_and_nonfinite_cannot_be_deleted():
    result = segments(errors())
    indexed = {r["segment_id"]: r for r in result}
    assert [indexed[key]["count"] for key in report.REGIONS] == [7, 2, 2, 4, 3]
    assert indexed["outside"]["yaw_rmse_deg"] == pytest.approx(np.sqrt(6.))
    assert indexed["inside_union"]["roll_rmse_deg"] == pytest.approx(np.sqrt(np.mean(np.array([2, 3, 5, 6]) ** 2)) / 5)
    frame = errors()
    frame.loc[1, "pitch_err_deg"] = np.nan
    failed = segments(frame)
    assert len(failed) == 5
    assert all(r["h_rmse_m"] == report.UNAVAILABLE and r["count"] == report.UNAVAILABLE for r in failed)
    assert all(r["unavailable_reason"] == "NONFINITE_ERROR_SERIES" for r in failed)
    assert all(r["h_rmse_m"] == report.UNAVAILABLE for r in segments(errors(), evaluation_status="NOT_RUN"))
    text_frame = errors().astype(str)
    text_frame.loc[1, "pitch_err_deg"] = "nan"
    assert all(r["count"] == report.UNAVAILABLE for r in segments(text_frame))


def test_segment_comparators_copy_tokens_and_missing_rows_remain_explicit():
    frozen = segments(errors())
    for item in frozen:
        item["variant"] = report.FROZEN
        item["h_rmse_m"] = "1.230000000000000"
    original = deepcopy(frozen)
    result = report.by2o_segment_rows(frozen, [], segments(errors()), version="v3", data_mode="synthetic")
    assert len(result) == 50
    copy = next(r for r in result if r["configuration_id"] == "F04" and r["variant"] == report.FROZEN and r["segment_id"] == "full")
    assert copy["h_rmse_m"] == "1.230000000000000"
    absent = next(r for r in result if r["configuration_id"] == "A04" and r["variant"] == "B3")
    assert absent["h_rmse_m"] == report.UNAVAILABLE
    assert absent["delta_vs_t5a_r5_h_rmse_m"] == report.UNAVAILABLE
    assert frozen == original
    bad = segments(errors())
    bad[0]["configuration_id"] = "A04"
    with pytest.raises(ValueError, match="Unregistered"):
        report.by2o_segment_rows(frozen, [], bad, version="v3", data_mode="synthetic")


def test_data_roles_cannot_be_upgraded_or_omitted_for_admitted_payloads():
    frozen, t5a, literature = inputs()
    for source in (payload(), payload(data_mode="real_raw", synthetic_data_used=True),
                   payload(data_mode="real_raw", semisynthetic_data_used=True)):
        with pytest.raises(ValueError, match="Data role|Semisynthetic"):
            report.pilot_rows(frozen, t5a, [source], literature, version="v3")
    for field in ("data_mode", "synthetic_data_used", "semisynthetic_data_used"):
        source = payload()
        source["row"].pop(field)
        with pytest.raises(ValueError, match="must be explicit"):
            pilot([source])
    source = payload(evaluation_status="NOT_RUN")
    for field in ("data_mode", "synthetic_data_used", "semisynthetic_data_used"):
        source["row"].pop(field)
    result = select(pilot([source]))
    assert result["data_mode"] == result["synthetic_data_used"] == report.UNAVAILABLE
    with pytest.raises(ValueError, match="Data role"):
        subset([payload(profile="F04", case_id=CASES[1], data_mode="synthetic")])


def _runtime_payload(case=None):
    """Use the real wrapper's identity keys and its actual pure metrics helper."""
    from legsa_gins.paper_rebuild.hext.t5bc_runtime import IDENTITY_KEYS, window_metrics

    identity = {"run_id": "BY2__F04__R5W__SYNTHETIC_FIXTURE", "sequence_id": "BY2",
                "configuration_id": "F04", "variant": "R5W", "subset_case_id": case}
    assert tuple(identity) == IDENTITY_KEYS
    identity.update(dataset_id="BY2", method_id="F04", data_mode="semisynthetic" if case else "synthetic",
                    synthetic_data_used=case is None, semisynthetic_data_used=case is not None,
                    evaluator_contract="evaluator_contract_v3", metrics_admitted=True,
                    evaluation_invoked=True, trace_used_online=False)
    frame = pd.DataFrame({"time": [1., 2.], "err_n_m": [1., 1.], "err_e_m": [2., 2.],
                          "err_u_m": [0., 0.], "horizontal_err_m": [2., 2.],
                          "position_3d_err_m": [2., 2.], "roll_err_deg": [1., 1.],
                          "pitch_err_deg": [1., 1.], "yaw_err_deg": [1., 1.]})
    nav = np.zeros((2, 11)); nav[:, 1] = [1., 2.]
    source = window_metrics(frame, nav, identity, [1., 2.], 2)
    source.update(status="COMPLETED", failure_classification="NONE")
    return {"row": source, "audit": {"passed": True, "trace_open_count": 1},
            "body_frame_bias": {"forward_signed_mean_m": 0., "right_signed_mean_m": 0., "up_signed_mean_m": 0.}}


def test_actual_runtime_subset_identity_maps_exactly_and_conflicting_aliases_stop():
    source = _runtime_payload(CASES[1])
    assert "case_id" not in source["row"] and "horizontal_rmse_m" in source["row"]
    rows, _ = subset([source])
    selected = next(r for r in rows if r["case_id"] == CASES[1] and r["variant"] == "R5W")
    assert selected["evaluation_status"] == "COMPLETED" and selected["h_rmse_m"] == 2.
    assert selected["semisynthetic_data_used"] is True
    source["row"]["case_id"] = CASES[2]
    with pytest.raises(ValueError, match="identities disagree"):
        subset([source])
    source["row"]["case_id"] = CASES[1]
    assert subset([source])[0]
    with pytest.raises(ValueError, match="subset evaluation"):
        pilot([source])


@pytest.mark.parametrize("location", ["horizontal_alias", "body_bias", "gnss_count"])
def test_runtime_normalized_aliases_and_body_bias_nonfinite_fail_atomically(location):
    source = _runtime_payload()
    if location == "horizontal_alias":
        source["row"]["horizontal_rmse_m"] = float("nan")
    elif location == "body_bias":
        source["body_frame_bias"]["forward_signed_mean_m"] = float("inf")
    else:
        source["row"]["gnss2_float_epochs"] = float("nan")
    candidate = select(pilot([source]), profile="F04")
    assert candidate["evaluation_status"] == "UNAVAILABLE_NONFINITE_METRICS"
    assert all(candidate[field] == report.UNAVAILABLE for field in report.NUMERIC_FIELDS)
    assert all(candidate["delta_vs_frozen_" + field] == report.UNAVAILABLE for field in report.NUMERIC_FIELDS)


CASES = ("C00_clean_normal", "D01_seed_00", "D02_seed_00")


def subset(evaluations=()):
    frozen = [{**row(profile="F04"), "case_id": case} for case in CASES]
    return report.subset_rows(frozen, evaluations, case_ids=CASES,
                              pending_rows=[{"case_id": "D06_seed_00", "status": "PENDING_V3_INJECTION"}])


def test_subset_is_exact_caller_cases_with_semisynthetic_boundary_and_pending_intact():
    candidate = payload(profile="F04", case_id="D01_seed_00")
    rows, pending = subset([candidate])
    assert len(rows) == 15
    assert pending == [{"case_id": "D06_seed_00", "status": "PENDING_V3_INJECTION"}]
    assert all(r["data_mode"] == "semisynthetic" and r["semisynthetic_data_used"] is True
               for r in rows if r["case_id"] != "C00_clean_normal" and r["evaluation_status"] == "COMPLETED")
    assert all(r["data_mode"] == "real_raw" and r["semisynthetic_data_used"] is False
               for r in rows if r["case_id"] == "C00_clean_normal" and r["evaluation_status"] == "COMPLETED")
    assert next(r for r in rows if r["case_id"] == "D01_seed_00" and r["variant"] == "R5W")["delta_vs_frozen_h_rmse_m"] == "0.010000000000000"
    assert sum(r["evaluation_status"] == "NOT_RUN" for r in rows) == 11
    with pytest.raises(ValueError, match="Every authorized"):
        report.subset_rows([], [], case_ids=CASES)
    with pytest.raises(ValueError, match="pending injection"):
        report.subset_rows([{**row(profile="F04"), "case_id": CASES[0]}], [], case_ids=CASES[:1],
                           pending_rows=[{"case_id": CASES[0]}])


def test_subset_distributions_use_true_pairs_and_explicit_failure_not_run_counts():
    evaluations = [payload(profile="F04", case_id=CASES[0], h_rmse_m="1.43"),
                   payload(profile="F04", case_id=CASES[1], h_rmse_m="1.13"),
                   payload(profile="F04", case_id=CASES[2], h_rmse_m="0.0",
                           evaluation_status="UNAVAILABLE_EVALUATION_FAILED")]
    rows, _ = subset(evaluations)
    distributions = report.subset_distributions(rows, case_ids=CASES, metrics=("h_rmse_m",))
    first = next(r for r in distributions if r["variant"] == "R5W")
    empty = next(r for r in distributions if r["variant"] == "R5SIGMA")
    assert first["valid_paired_count"] == 2 and first["failure_count"] == 1
    assert first["unpaired_count"] == 1 and first["not_run_count"] == 0
    assert first["paired_delta_mean"] == pytest.approx(.05)
    assert first["paired_delta_p95"] == pytest.approx(.185)
    assert first["paired_delta_worst_5pct_mean"] == pytest.approx(.2)
    assert first["worst_5pct_count"] == 1
    assert first["data_modes"] == ["real_raw", "semisynthetic"]
    assert first["semisynthetic_data_used"] is True and first["synthetic_data_used"] is False
    assert empty["valid_paired_count"] == 0 and empty["not_run_count"] == 3
    assert empty["failure_count"] == 0 and empty["paired_delta_mean"] == report.UNAVAILABLE
    # A numerically populated failed reference is not an available pair.
    next(r for r in rows if r["case_id"] == CASES[0] and r["variant"] == report.FROZEN)["evaluation_status"] = "FAILED"
    assert report.subset_distributions(rows, case_ids=CASES, metrics=("h_rmse_m",))[1]["valid_paired_count"] == 1


def test_empty_subset_group_reports_unavailable_not_zero_performance():
    rows, pending = report.subset_rows([], [], case_ids=[])
    assert rows == pending == []
    distributions = report.subset_distributions([], case_ids=[], metrics=("h_rmse_m",))
    assert len(distributions) == 4
    assert all(r["case_count"] == 0 and r["paired_delta_mean"] == report.UNAVAILABLE for r in distributions)


def identity(variant="B3", sequence="BY2O"):
    return {"sequence_id": sequence, "configuration_id": "F04", "variant": variant,
            "run_id": "SYNTHETIC_RUN", "data_mode": "synthetic", "synthetic_data_used": True,
            "semisynthetic_data_used": False}


def b3_frame():
    return pd.DataFrame({"time": [3369.94, 3400., 3500., 3520., 3530.], "present": [1, 1, 1, 1, 0],
                         "valid": [1, 1, 1, 0, 0], "attempt": [1, 1, 1, 0, 0],
                         "accepted": [1, 1, 0, 0, 0], "rejected": [0, 0, 1, 0, 0],
                         "reason": ["ACCEPT", "ACCEPT", "NIS_3DOF_REJECT", "INVALID", "MISSING"],
                         "nis_actual_innovation": [1., 3., 14., np.nan, np.nan],
                         "along_axis_residual_m": [.1, -.2, .3, np.nan, np.nan],
                         "length_mismatch_m": [.2, -.3, .4, np.nan, np.nan]})


def gating(frame=None, log=None, variant="B3"):
    return report.gating_nis_rows(log, identity=identity(variant), window=WINDOW, source="SYNTHETIC",
                                  baseline3d=frame)


def test_b3_counts_nis_and_signed_axis_statistics_keep_invalid_missing_rows():
    rows = gating(b3_frame())
    full = rows[0]
    assert len(rows) == 5
    assert full["epochs"] == 5 and full["attempted"] == 3
    assert full["accepted"] == 2 and full["rejected"] == 1
    assert full["invalid"] == 2 and full["missing"] == 1 and full["not_attempted"] == 2
    assert full["accounting_consistent"] is True
    assert full["nis_count"] == 5 and full["nis_available_count"] == 3 and full["nis_missing_count"] == 2
    assert full["nis_mean"] == pytest.approx(6.)
    assert full["nis_p95"] == pytest.approx(12.9)
    assert full["along_axis_residual_m_mean"] == pytest.approx(.2 / 3)
    assert full["along_axis_residual_m_p95_absolute"] == pytest.approx(.29)
    assert full["reason_counts"]["MISSING"] == 1
    inside = next(r for r in rows if r["segment_id"] == "inside_union")
    outside = next(r for r in rows if r["segment_id"] == "outside")
    assert inside["attempted"] == 3 and outside["invalid"] == 2
    assert outside["nis_mean"] == report.UNAVAILABLE


def test_b3_bad_accounting_and_nonfinite_diagnostics_remain_visible():
    frame = b3_frame()
    frame.loc[0, "rejected"] = 1
    frame.loc[1, "nis_actual_innovation"] = float("inf")
    full = gating(frame)[0]
    assert full["status"] == "UNAVAILABLE_ACCOUNTING_MISMATCH"
    assert full["accepted"] == full["rejected"] == 2
    assert full["nis_mean"] == report.UNAVAILABLE and full["nis_nonfinite_count"] == 1
    assert full["nis_available_count"] == 2
    frame.loc[1, "valid"] = 2
    with pytest.raises(ValueError, match="binary"):
        gating(frame)


def test_scalar_attempts_do_not_invent_invalid_or_missing_counts():
    log = pd.DataFrame({"gnss_time": [3369.94, 3400., 3500., 3520.],
                        "yaw_update": [1, 1, 1, 0], "yaw_mode": ["NORMAL", "DOWNWEIGHT", "REJECT", "NONE"]})
    full = gating(log=log, variant="R5W")[0]
    assert full["attempted"] == 3 and full["accepted"] == 2 and full["rejected"] == 1
    assert full["invalid"] == full["missing"] == report.UNAVAILABLE
    assert full["nis_status"] == "NOT_APPLICABLE_SCALAR_TRACE"
    assert gating(log=log)[0]["status"] == "UNAVAILABLE_DIAGNOSTICS"
    log.loc[3, "yaw_mode"] = "NORMAL"
    assert gating(log=log, variant="R5W")[0]["status"] == "UNAVAILABLE_ACCOUNTING_MISMATCH"


def test_attitude_keeps_all_variants_literature_and_failed_visibility():
    rows = pilot([payload(roll_rmse_deg="2.10000", pitch_rmse_deg="2.90000")])
    attitude = report.attitude_rows(rows)
    assert len(attitude) == len(rows) == 36
    r5w = select(attitude)
    assert r5w["roll_rmse_deg"] == "2.10000"
    assert r5w["delta_vs_frozen_pitch_rmse_deg"] == "-0.10000"
    assert any(r["variant"] == "LC01-S" for r in attitude)
    assert select(attitude, profile="A04", variant="B3")["roll_rmse_deg"] == report.UNAVAILABLE
    assert "unobservable" in select(attitude, profile="A04", variant="B3")["baseline3d_observability"]


def test_full_canonical_metrics_and_real_clean_frozen_role_survive_and_pair():
    original={**row(profile="F04"),"case_id":CASES[0],"data_mode":"real_clean",
              "synthetic_data_used":"False","semisynthetic_data_used":"False",
              "north_signed_mean_m":"2.000","horizontal_iae_m":"40.000","cep50_m":"1.000"}
    new=payload(profile="F04",variant="R5",case_id=CASES[0],data_mode="real_clean")
    new["subset_metrics"]={"north_signed_mean_m":"3.250","horizontal_iae_m":"44.200","cep50_m":"1.500"}
    rows,_=report.subset_rows([original],[new],case_ids=CASES[:1])
    selected=next(r for r in rows if r["variant"]=="R5")
    assert selected["data_mode"]=="real_clean"
    assert selected["delta_vs_frozen_north_signed_mean_m"]=="1.250"
    assert selected["delta_vs_frozen_horizontal_iae_m"]=="4.200"
    assert selected["delta_vs_frozen_cep50_m"]=="0.500"
    new["row"]["evaluation_status"]="NOT_RUN_ALGORITHM_FAILURE"
    rows,_=report.subset_rows([original],[new],case_ids=CASES[:1])
    selected=next(r for r in rows if r["variant"]=="R5")
    assert selected["north_signed_mean_m"]==selected["horizontal_iae_m"]==report.UNAVAILABLE


def test_nis_reports_only_actual_covariance_a1_rows_and_accounts_negative_values():
    frame=pd.DataFrame({"source_id":["dual_antenna_yaw"]*5+["position"],
                        "used_innovation_covariance":[1,1,0,1,1,1],"dof":[1,1,1,3,1,1],
                        "time":[1,2,3,4,5,6],"nis":[1,-1,0,2,3,9]})
    summary,series=report.nis_consistency(frame,identity=identity("R5W","BY2"),window=[1,6],attempts={"full":6})
    full=next(r for r in summary if r["segment_id"]=="full")
    assert full["count"]==2 and full["negative_count"]==1
    assert full["nis_mean"]==2 and full["nis_selection_coverage"]==pytest.approx(1/3)
    assert len(series)==3 and series[1]["nis"]==report.UNAVAILABLE


def test_absolute_summary_worst_five_percent_is_p95_not_tail_mean():
    rows,_=subset([payload(profile="F04",variant="R5",case_id=case,h_rmse_m=str(value))
                   for case,value in zip(CASES,[1.,2.,10.])])
    result=report.subset_absolute_summary(rows,case_ids=CASES)
    selected=next(r for r in result if r["variant"]=="R5" and r["metric"]=="h_rmse_m")
    assert selected["mean"]==pytest.approx(13/3) and selected["median"]==2
    assert selected["worst_5pct_threshold_p95"]==pytest.approx(9.2)
