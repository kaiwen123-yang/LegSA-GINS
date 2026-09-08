"""Synthetic NAV/STD/error artifacts only; no raw reference or evaluator runs."""
import csv
import json
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean5_sequence import evaluation_tables as tables


def error_frame(times=(413.,414.,415.)):
    count=len(times)
    values=np.arange(1.,count+1)
    north=values*np.where(np.arange(count)%2,1.,-1.)
    east=values+1
    up=np.linspace(-4.,4.,count)
    return pd.DataFrame({"time":times,"err_n_m":north,"err_e_m":east,"err_u_m":up,
        "horizontal_err_m":np.hypot(north,east),"position_3d_err_m":np.sqrt(north**2+east**2+up**2),
        "roll_err_deg":values,"pitch_err_deg":-values,"yaw_err_deg":np.linspace(-10.,20.,count)})


def registry(method="F04",dataset="BY2H"):
    return {"run_id":f"{dataset}_{method}_{tables.METHODS[method]}","method_id":method,
            "effective_profile":tables.METHODS[method],"dataset_id":dataset,
            "case_id":f"CLEAN5_{dataset}_NATURAL","case_family":"natural_sequence",
            "degradation_type_id":"NATURAL","seed_index":"","run_order":1}


def synthetic_artifacts(tmp_path,*,nav_times=(412.9,413.,414.,415.,415.1)):
    output,eval_dir=tmp_path/"synthetic_solver",tmp_path/"synthetic_evaluator"
    output.mkdir();eval_dir.mkdir()
    (output/"KF_GINS_Navresult.nav").write_text("".join(f"0 {t} 0 0 0 0 0 0 0 0 0\n" for t in nav_times))
    (output/"KF_GINS_STD.txt").write_text("".join(f"{t} 1 1 1 1 1 1 1 1 1\n" for t in (413,414,415)))
    (output/"RUN_MANIFEST.json").write_text(json.dumps({"position_update_count":3,
        "source_aware_evaluation_count":3,"source_aware_weight_changed_count":1}))
    frame=error_frame()
    frame.to_csv(eval_dir/"error_series.csv",index=False)
    return output,eval_dir,frame


def test_calls_original_compute_result_and_overrides_only_three_fields(tmp_path):
    output,eval_dir,_=synthetic_artifacts(tmp_path)
    reg=registry()
    original=tables.canonical._compute_result(reg,{},output,eval_dir,4,.5,True)
    result=tables.compute_sequence_result(reg,{},output,eval_dir,window={"t_start":413,"t_end":415},
        reference_epoch_count=4,evaluation_runtime=.5,evaluation_invoked=True,
        wrapper_runtime_seconds=12.25,wrapper_exit_code=0)
    assert original["output_epoch_count"]==0
    assert result["output_epoch_count"]==3 and result["coverage_ratio"]==1.
    assert result["reference_epoch_count"]==4
    assert result["unmatched_epoch_count"]==original["unmatched_epoch_count"]==0
    for name,value in original.items():
        if name not in tables.RESULT_OVERRIDE_FIELDS:
            assert result[name]==value,name
    assert result["solver_runtime_seconds"] is None and result["solver_returncode"] is None
    assert result["wrapper_runtime_seconds"]==12.25 and result["wrapper_exit_code"]==0
    assert tables.canonical.WINDOW_START==66. and tables.canonical.WINDOW_END==340.


def test_original_unmatched_field_is_a_gate_not_a_fourth_override(tmp_path):
    output,eval_dir,_=synthetic_artifacts(tmp_path,nav_times=(413.,414.,415.,416.))
    with pytest.raises(ValueError,match="unauthorized fourth override"):
        tables.compute_sequence_result(registry(),{},output,eval_dir,window={"t_start":413,"t_end":416},
            reference_epoch_count=4,evaluation_runtime=1.,evaluation_invoked=True)


@pytest.mark.parametrize("reference_count",[-1,True,1.5])
def test_reference_count_is_fail_closed(tmp_path,reference_count):
    with pytest.raises(ValueError,match="nonnegative integer"):
        tables.compute_sequence_result(registry(),{},tmp_path,tmp_path,window={"t_start":413,"t_end":415},
            reference_epoch_count=reference_count,evaluation_runtime=1.,evaluation_invoked=True)


def test_o_segments_have_closed_during_and_outside_union_with_secondary_retained():
    frame=error_frame((10.,11.,12.,13.,14.,15.,16.))
    case={"degradation_parameters_json":json.dumps({"start_s":12,"end_s":14,"secondary_runs":[[15,16]]})}
    rows=tables.segment_rows(frame,registry=registry(dataset="BY2O"),dataset_id="BY2O",
        window={"t_start":10,"t_end":16},case_meta=case)
    assert len(rows)==20
    index={(row["segment_id"],row["metric_name"]):row for row in rows}
    assert [index[(segment,"horizontal")]["count"] for segment in ("pre","during","post","outside","full")]==[2,3,2,4,7]
    assert index[("during","up")]["time_start"]==12 and index[("during","up")]["time_end"]==14
    for segment in ("post","outside","full"):
        assert index[(segment,"horizontal")]["secondary_run_epoch_count"]==2
    assert index[("during","horizontal")]["secondary_run_epoch_count"]==0
    outside=frame[frame.time.isin([10,11,15,16])]
    expected=tables.canonical._axis_stats(outside.time.to_numpy(),outside.err_u_m.to_numpy())
    actual=index[("outside","up")]
    assert actual["rmse"]==expected["rmse"]
    assert actual["p95_abs"]==expected["p95_absolute"]
    assert actual["max_abs"]==expected["max_absolute"]
    assert actual["signed_mean"]==expected["signed_mean"]
    assert index[("outside","horizontal")]["signed_mean"] is None
    assert index[("outside","yaw")]["unit"]=="deg"


def test_empty_segment_is_unavailable_and_secondary_union_is_not_double_counted():
    frame=error_frame((12.,13.,14.,15.))
    case={"degradation_parameters_json":json.dumps({"start_s":12,"end_s":14,"secondary_runs":[[14,15],[14,15]]})}
    rows=tables.segment_rows(frame,registry=registry(dataset="BY2O"),dataset_id="BY2O",
        window={"t_start":10,"t_end":16},case_meta=case)
    pre=next(row for row in rows if row["segment_id"]=="pre" and row["metric_name"]=="up")
    assert pre["count"]==0 and all(pre[key] is None for key in ("rmse","p95_abs","max_abs","signed_mean"))
    full=next(row for row in rows if row["segment_id"]=="full" and row["metric_name"]=="up")
    assert full["secondary_run_epoch_count"]==2


def test_h_full_only_uses_norm_and_signed_axis_helpers_without_other_segments():
    frame=error_frame()
    rows=tables.segment_rows(frame,registry=registry(),dataset_id="BY2H",window={"t_start":413,"t_end":415},case_meta={})
    assert len(rows)==4 and {row["segment_id"] for row in rows}=={"full"}
    assert all(row["secondary_run_epoch_count"]==0 for row in rows)
    horizontal=next(row for row in rows if row["metric_name"]=="horizontal")
    expected=tables.canonical._norm_stats(frame.time.to_numpy(),frame.horizontal_err_m.to_numpy())
    assert horizontal["p95_abs"]==expected["p95"] and horizontal["rmse"]==expected["rmse"]
    with pytest.raises(ValueError,match="no frozen degradation"):
        tables.segment_rows(frame,registry=registry(),dataset_id="BY2H",window={"t_start":413,"t_end":415},
                            case_meta={"degradation_parameters_json":'{"start_s":413,"end_s":414}'})


def fixture_tables(dataset="BY2H"):
    unique,logical,segments=[],[],[]
    for order,(method,profile) in enumerate(tables.METHODS.items(),1):
        reg=registry(method,dataset)
        row={"run_id":reg["run_id"],"method_id":method,"effective_configuration_id":profile,
             "dataset_id":dataset,"case_id":reg["case_id"],"case_family":"natural_sequence",
             "degradation_id":"NATURAL","seed_id":"","evaluation_status":"COMPLETED","finite_output":True,
             "solver_runtime_seconds":None,"evaluation_runtime_seconds":.5,"wrapper_runtime_seconds":float(order),
             "wrapper_exit_code":0,"horizontal_rmse_m":float(6-order),"up_rmse_m":float(6-order),
             "source_aware_evaluation_count":3,"source_aware_touch_rate":1/3}
        unique.append(row)
        logical.append({**reg,"execution_alias":False,"alias_of":"","logical_id":reg["run_id"]+"_logical"})
        segments.extend(tables.segment_rows(error_frame(),registry=reg,dataset_id=dataset,
            window={"t_start":413,"t_end":415},case_meta={}))
    for alias,method in (("A01","F04"),("A02","F03")):
        reg=registry(method,dataset)
        logical.append({**reg,"method_id":alias,"execution_alias":True,"alias_of":method,"logical_id":alias})
    return unique,logical,segments


def test_five_unique_seven_logical_aliases_six_pairs_and_wrapper_runtime():
    unique,logical,segments=fixture_tables()
    result=tables.build_tables(unique,logical,segments,metadata={"dataset_id":"BY2H","data_mode":"synthetic_test"})
    output=result["csv_tables"]
    assert len(output["UNIQUE_EVALUATION_RESULTS.csv"])==5
    assert len(output["LOGICAL_EVALUATION_RESULTS.csv"])==7
    index={row["method_id"]:row for row in output["LOGICAL_EVALUATION_RESULTS.csv"]}
    assert index["A01"]["run_id"]==index["F04"]["run_id"]
    assert index["A02"]["run_id"]==index["F03"]["run_id"]
    assert index["A01"]["role"]=="logical_alias"
    pairs=output["PAIRWISE_CASE_LEVEL.csv"]
    assert list(dict.fromkeys(row["comparison"] for row in pairs))==[item[0] for item in tables.PAIRWISE_DEFINITIONS]
    assert all(row["delta_candidate_minus_reference"]<0 for row in pairs)
    for row in output["PAIRWISE_SUMMARY.csv"]:
        assert row["paired_sample_count"]==1 and row["confidence_interval_status"]=="NOT_AVAILABLE_SINGLE_CASE"
        assert row["wilcoxon_status"]=="NOT_AVAILABLE_SINGLE_CASE" and row["wilcoxon_pvalue"] is None
    runtime=output["RUNTIME_SUMMARY.csv"]
    assert any(row["metric_name"]=="wrapper_runtime_seconds" for row in runtime)
    assert not any(row["metric_name"]=="solver_runtime_seconds" for row in runtime)
    assert result["FINAL_EVALUATION_SUMMARY.json"]["unique_run_count"]==5
    assert result["FINAL_EVALUATION_SUMMARY.json"]["logical_result_count"]==7


def test_pairwise_zero_reference_has_unavailable_relative_change():
    unique,logical,_=fixture_tables()
    unique[0]["horizontal_rmse_m"]=0.
    cases,_=tables.pairwise_rows(tables.canonical._logical_rows(logical,unique))
    row=next(row for row in cases if row["comparison"]=="basic_vs_single" and row["metric_name"]=="horizontal_rmse_m")
    assert row["relative_change_percent"] is None


@pytest.mark.parametrize("corruption",["missing_unique","alias_wrong_run","duplicate_segment","wrong_segment_unit","wrong_segment_identity"])
def test_identity_and_complete_segment_matrix_are_fail_closed(corruption):
    unique,logical,segments=fixture_tables()
    if corruption=="missing_unique":unique.pop()
    elif corruption=="alias_wrong_run":logical[-1]["run_id"]=unique[0]["run_id"]
    elif corruption=="duplicate_segment":segments.append(dict(segments[0]))
    elif corruption=="wrong_segment_unit":segments[0]["unit"]="deg"
    elif corruption=="wrong_segment_identity":segments[0]["method_id"]="F04"
    with pytest.raises(ValueError):
        tables.build_tables(unique,logical,segments,metadata={"dataset_id":"BY2H"})


def test_failed_evaluation_cannot_produce_pass_final_summary():
    unique,logical,segments=fixture_tables()
    unique[0].update(evaluation_status="TECHNICAL_FAILURE",finite_output=False)
    result=tables.build_tables(unique,logical,segments,metadata={"dataset_id":"BY2H"})
    assert result["FINAL_EVALUATION_SUMMARY.json"]["terminal_status"].startswith("PARTIAL")
    assert result["FINAL_EVALUATION_SUMMARY.json"]["evaluation_failures"]==1


def test_writer_preserves_caller_canonical_header_prefix_and_appends_fields(tmp_path):
    unique,logical,segments=fixture_tables()
    material=tables.build_tables(unique,logical,segments,metadata={"dataset_id":"BY2H","data_mode":"synthetic_test"})
    # Synthetic schema demonstrates preserving fields absent from new rows,
    # retaining their order, and appending without consulting old table data.
    headers={name:["canonical_first","metric_name","method_id"] for name in tables.CANONICAL_CSV_NAMES}
    root=tmp_path/"synthetic_08"
    output=tables.write_tables(root,material,canonical_headers=headers)
    assert len(output["files"])==12
    for name,prefix in headers.items():
        with (root/name).open(newline="") as handle:
            actual=next(csv.reader(handle))
        assert actual[:len(prefix)]==prefix
    with (root/"WINDOW_SEGMENT_SUMMARY.csv").open(newline="") as handle:
        assert next(csv.reader(handle))==list(tables.SEGMENT_FIELDS)
    assert "secondary_run_epoch_count" in tables.SEGMENT_FIELDS
    with pytest.raises(FileExistsError):
        tables.write_tables(root,material,canonical_headers=headers)


def test_invalid_schema_refused_before_creating_output(tmp_path):
    unique,logical,segments=fixture_tables()
    material=tables.build_tables(unique,logical,segments,metadata={"dataset_id":"BY2H"})
    headers={name:["x","x"] for name in tables.CANONICAL_CSV_NAMES}
    root=tmp_path/"must_not_exist"
    with pytest.raises(ValueError,match="distinct"):
        tables.write_tables(root,material,canonical_headers=headers)
    assert not root.exists()
