"""Synthetic aggregation fixtures only; no native/evaluator/reference access."""
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.hext import aggregate
from legsa_gins.paper_rebuild.hext import external_evaluation


def _row(seq, method, *, yaw=2., start="FILE_START", geometry="PASS"):
    source = {name: 1. for name in aggregate.METRIC_FIELDS}
    source.update(yaw_rmse_deg=yaw, evaluation_status="COMPLETED", output_epoch_count=2,
                  matched_epoch_count=2, coverage_ratio=1., code_commit="synthetic_scientific_commit")
    return aggregate.normalize_row(source, sequence_id=seq, method_id=method,
        config="S" if method.endswith("-S") else "LIT", start=start, geometric_status=geometry,
        notes=json.dumps({"result_reused": True}))


def test_selection_is_by2_only_with_frozen_anchor_and_no_tie_fallback():
    rows = [_row("BY2", "LC01", yaw=2.9948274600591076), _row("BY2", "LC01-S", yaw=2.9),
            _row("BY2H", "LC01", yaw=.1), _row("BY2H", "LC01-S", yaw=100),
            _row("BY2H", "LC01-S", yaw=.001, start="CONTRACT_START"), _row("BY2H", "F04")]
    selected = aggregate.select_main_config(rows)
    marked = aggregate.mark_main_rows(rows, selected, {"BY2": "FILE_START", "BY2H": "FILE_START"})
    assert selected["selected_method_id"] == "LC01-S"
    assert [(r["sequence_id"], r["method_id"], r["start_convention"]) for r in marked if r["main_row"]] == [
        ("BY2", "LC01-S", "FILE_START"), ("BY2H", "LC01-S", "FILE_START"), ("BY2H", "F04", "FILE_START")]
    rows[1]["yaw_rmse_deg"] = 2.9948274600591076
    with pytest.raises(ValueError, match="Equal yaw"):
        aggregate.select_main_config(rows)
    rows[1]["yaw_rmse_deg"] = "UNAVAILABLE"
    with pytest.raises(ValueError, match="substitution"):
        aggregate.select_main_config(rows)


def test_geometric_failure_keeps_metrics_and_unavailable_never_zero():
    row = _row("BY2H", "LC01", geometry="FAIL")
    assert row["evaluation_status"] == "AVAILABLE_GEOMETRIC_AUDIT_FAIL"
    assert row["yaw_rmse_deg"] == 2.
    assert row["body_forward_bias_m"] == "UNAVAILABLE"
    assert row["evaluator_nav_sha256"] == "UNAVAILABLE"


def test_static_fallback_reuses_h_contract_slots_without_budget_overrun():
    records = []
    for seq, methods in (("BY2", ("LC01-S", "EXT05C-S")), ("BY2H", aggregate.EXTERNAL_METHODS),
                         ("BY2O", aggregate.EXTERNAL_METHODS)):
        for method in methods:
            records.append(dict(run_id=seq+method, sequence_id=seq, configuration_id=method,
                                start_mode="CONTRACT_START", primary_start_mode="CONTRACT_START"))
    assert len(records) == 10
    aggregate.validate_run_identities(records)
    with pytest.raises(ValueError, match="identities"):
        aggregate.validate_run_identities(records[:-1])


def test_hash_gate_precedes_frozen_payload_parsing(tmp_path):
    source = tmp_path / "frozen.csv"
    source.write_bytes(b"malformed but immutable bytes")
    with pytest.raises(ValueError, match="hash mismatch"):
        aggregate.pinned_payload(source, "0"*64)
    assert aggregate.pinned_payload(source, hashlib.sha256(source.read_bytes()).hexdigest()) == source.read_bytes()


def _errors(times):
    return pd.DataFrame({"time": times, **{column: np.ones(len(times)) for column in (
        "horizontal_err_m", "position_3d_err_m", "err_n_m", "err_e_m", "err_u_m",
        "roll_err_deg", "pitch_err_deg", "yaw_err_deg")}})


def test_occlusion_segments_use_frozen_closed_intervals_and_keep_zero_support():
    errors = _errors([3369.939, 3369.94, 3411.95, 3411.951])
    rows = aggregate.segment_rows(errors, sequence_id="BY2O", method_id="LC01-S",
        start_convention="FILE_START", version="v3", window=(3186, 3563), source="synthetic")
    assert [r["count"] for r in rows] == [4, 2, 0]
    assert rows[-1]["h_rmse_m"] == "UNAVAILABLE"
    assert rows[-1]["status"] == "UNAVAILABLE_NO_MATCHED_EPOCHS"


def test_stage06_transform_layout_without_any_evaluator_process(tmp_path, monkeypatch):
    seq = SimpleNamespace(sequence_id="BY2O", trace=tmp_path/"raw"/"never_open.csv", trace_sha256="a"*64,
        base_time=1772780400., window=(3186.,3563.), baseline_median_m=.35013463864843675,
        output_root=tmp_path/"clean", hext_scratch=tmp_path/"scratch")
    nav=tmp_path/"original.nav";nav.write_text("0 3186 30 120 10 0 0 0 0 0 0\n1 3563 30 120 10 0 0 0 0 0 0\n")
    def fake_child(**kwargs):
        target=kwargs["outdir"];target.mkdir(parents=True)
        _errors([3186.,3563.]).to_csv(target/"error_series.csv",index=False)
        return {"audit":{"passed":True,"trace_open_count":1},"capture":{"reference_epoch_count":2},
                "runtime_seconds":0.,"outdir":str(target)}
    monkeypatch.setattr(external_evaluation,"_evaluate_process",fake_child)
    monkeypatch.setattr(external_evaluation,"run_process_group",lambda *a,**k:pytest.fail("real evaluator forbidden"))
    result=external_evaluation.evaluate(sequence=seq,evaluator=tmp_path/"never_run.py",nav=nav,
        expected_nav_sha256=hashlib.sha256(nav.read_bytes()).hexdigest(),outdir=seq.hext_scratch/"07_OFFLINE_EVALUATION/v3/job",
        nav_input_root=seq.hext_scratch/"06_V3_NAV_INPUTS/job",version="v3",identity={"code_commit":"synthetic"})
    assert (seq.hext_scratch/"06_V3_NAV_INPUTS/job/EVALUATOR_INPUT.nav").is_file()
    assert not (seq.hext_scratch/"07_OFFLINE_EVALUATION/v3/job/NAV_INPUTS").exists()
    assert result["row"]["output_epoch_count"] == 2
    assert not seq.trace.exists()


def test_complete_registered_aggregate_with_synthetic_sealed_results(tmp_path,monkeypatch):
    seqs={d:SimpleNamespace(sequence_id=d,clean_root=tmp_path/"clean",raw_root=tmp_path/"raw",
          hext_scratch=tmp_path/"scratch",code_root=tmp_path/"code",window=w)
          for d,w in (("BY2",(66.,340.)),("BY2H",(413.,683.)),("BY2O",(3186.,3563.)))}
    frozen={v:[_row(d,m,start="FROZEN_V21") for d in seqs for m in aggregate.LEGSA_METHODS]+[
        _row("BY2","LC01",yaw=2.9948274600591076),_row("BY2","EXT05C",yaw=12.048641737808111)] for v in ("v3","v2")}
    monkeypatch.setattr(aggregate,"load_frozen_rows",lambda *args,**kwargs:(frozen,{"synthetic_fixture":True}))
    ids=[("BY2",m,"FILE_START") for m in ("LC01-S","EXT05C-S")]
    ids += [("BY2H",m,start) for m in aggregate.EXTERNAL_METHODS for start in ("FILE_START","CONTRACT_START")]
    ids += [("BY2O",m,"FILE_START") for m in aggregate.EXTERNAL_METHODS]
    records=[]
    for i,(d,m,start) in enumerate(ids):
        base=tmp_path/"scratch"/str(i);base.mkdir(parents=True)
        native=base/"native.json";native.write_text(json.dumps({"geometric_audit":{"thresholds_pass":True}}))
        gaps=base/"gaps.json";gaps.write_text("[]")
        record=dict(run_id=str(i),sequence_id=d,configuration_id=m,start_mode=start,
                    native_summary_path=str(native),gap_log_path=str(gaps),evaluations={})
        for v in ("v3","v2"):
            folder=base/v;folder.mkdir();errors=_errors(list(seqs[d].window));errors.to_csv(folder/"error_series.csv",index=False)
            row=_row(d,m,start=start);row.update(evaluator_contract="evaluator_contract_"+v,error_series_source=str(folder))
            payload={"row":row,"body_frame_bias":{"forward_signed_mean_m":1.,"right_signed_mean_m":2.,"up_signed_mean_m":3.},
                     "audit":{"passed":True,"trace_open_count":1}}
            path=folder/"EVALUATION_RESULT.json";path.write_text(json.dumps(payload));record["evaluations"][v]=str(path)
        records.append(record)
    out=tmp_path/"clean/08_AGGREGATE"
    summary=aggregate.aggregate_stage(sequences=seqs,records=records,output_root=out,
        code_commit="synthetic_aggregation",budget_ledger={"synthetic_fixture":True})
    assert summary["selection"]["selected_method_id"]=="LC01-S"
    table=list(csv.DictReader((out/"HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv").open()))
    assert list(table[0])==list(aggregate.TABLE_FIELDS)
    assert len(table)==31
    assert len([r for r in table if r["main_row"]=="True" and r["method_id"]=="LC01-S"])==3
    assert all(r["main_row"]=="False" for r in table if r["start_convention"]=="CONTRACT_START")
    assert len(list(csv.DictReader((out/"DELTA_TABLE_V3.csv").open())))==42
