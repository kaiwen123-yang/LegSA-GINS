"""H-EXT-03 aggregation fixtures are synthetic; no native/evaluator/trace reads."""
import csv
import gzip
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.hext import aggregate, figures


def _source(version="v3", **overrides):
    return {**dict.fromkeys(aggregate.METRIC_FIELDS, 1.5),
            "evaluation_status": "COMPLETED", "evaluator_contract": "evaluator_contract_"+version,
            "output_epoch_count": 2, "matched_epoch_count": 2, "coverage_ratio": 1.,
            "code_commit": "synthetic_fixture", **overrides}


def _normalized(sequence, method, version="v3", **overrides):
    return aggregate.normalize_row(_source(version, **overrides), sequence_id=sequence,
        method_id=method, config="LIT", start="FILE_START" if method == "LC01" else "FROZEN_V21",
        geometric_status="NOT_APPLICABLE", notes=json.dumps({"result_reused": True}))


def _errors(times):
    return pd.DataFrame({"time": times, **{field: np.arange(1., len(times)+1.) for field in
        ("horizontal_err_m", "position_3d_err_m", "err_u_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg")}})


def _failed_payload(version="v3", *, algorithm=True):
    status = "NOT_RUN_ALGORITHM_FAILURE" if algorithm else "UNAVAILABLE_EVALUATION_FAILED"
    return {"row": _source(version, evaluation_status=status, evaluation_invoked=not algorithm,
        failure_classification="ALGORITHM_FAILURE_DIVERGED" if algorithm else "FAILED_EVALUATOR_CONSISTENCY",
        error_series_source="this_rejected_series_must_never_be_read"),
        "body_frame_bias": {"forward_signed_mean_m": 999},
        "audit": {"passed": algorithm, "trace_open_count": 0 if algorithm else 1,
                  "technical_passed": True, "consistency_passed": False}}


def test_d7_and_d12_explicit_dispositions_have_no_admitted_metrics():
    for algorithm in (True, False):
        payload = _failed_payload(algorithm=algorithm)
        row, bias = aggregate.validate_evaluation_payload(payload, version="v3", continuation_v11=True)
        assert all(row[key] == "UNAVAILABLE" for key in aggregate.METRIC_FIELDS)
        assert row["matched_epoch_count"] == "UNAVAILABLE"
        assert row["error_series_source"] == "UNAVAILABLE"
        assert "forward_signed_mean_m" not in bias
        with pytest.raises(ValueError, match="gate failed"):
            aggregate.validate_evaluation_payload(payload, version="v3")
    payload = _failed_payload(algorithm=False)
    payload["audit"]["technical_passed"] = False
    with pytest.raises(ValueError, match="gate failed"):
        aggregate.validate_evaluation_payload(payload, version="v3", continuation_v11=True)
    payload = _failed_payload()
    payload["audit"]["trace_open_count"] = 1
    with pytest.raises(ValueError, match="gate failed"):
        aggregate.validate_evaluation_payload(payload, version="v3", continuation_v11=True)


def test_frozen_full_rate_errors_use_exact_windows_with_hash_gate(tmp_path):
    seq = SimpleNamespace(clean_root=tmp_path/"clean", raw_root=tmp_path/"raw",
                          hext_scratch=tmp_path/"scratch", code_root=tmp_path/"code", window=(3186.,3563.))
    path = seq.hext_scratch/"frozen_error_series.csv.gz"
    path.parent.mkdir()
    path.write_bytes(gzip.compress(_errors([3369.939,3369.94,3411.95,3411.951,3495.94,3508.94]).to_csv(index=False).encode("utf-8-sig")))
    descriptor = dict(sequence_id="BY2O", method_id="F04", version="v3", path="<HEXT_SCRATCH>/"+path.name,
                      sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    rows = aggregate.frozen_comparison_segments({"BY2O":seq}, error_descriptors=[descriptor])
    selected = [r for r in rows if r["method_id"]=="F04" and r["evaluator_contract"].endswith("v3")]
    assert [r["count"] for r in selected] == [6,2,2]
    assert selected[1]["h_rmse_m"] == pytest.approx(np.sqrt((2**2+3**2)/2))
    assert all(r["count"] == "UNAVAILABLE" for r in rows if r not in selected)
    assert all("NAV_10HZ_NOT_USED" in r["unavailable_reason"] for r in rows if r not in selected)
    descriptor["sha256"] = "0"*64
    with pytest.raises(ValueError, match="hash mismatch"):
        aggregate.frozen_comparison_segments({"BY2O":seq}, error_descriptors=[descriptor])


def test_continuation_full_topology_failure_visibility_and_paper_starts(tmp_path, monkeypatch):
    seqs = {s:SimpleNamespace(sequence_id=s, clean_root=tmp_path/"clean", raw_root=tmp_path/"raw",
        hext_scratch=tmp_path/"scratch", code_root=tmp_path/"code", window=w)
        for s,w in (("BY2",(66.,340.)),("BY2H",(413.,683.)),("BY2O",(3186.,3563.)))}
    frozen = {v:[_normalized(s,m,v) for s in seqs for m in aggregate.LEGSA_METHODS]+
        [_normalized("BY2","LC01",v,yaw_rmse_deg=2.9948274600591076),_normalized("BY2","EXT05C",v)]
        for v in ("v3","v2")}
    monkeypatch.setattr(aggregate,"load_frozen_rows",lambda *a,**k:(frozen,{"synthetic_fixture":True}))
    ids = [("BY2",m,"FILE_START") for m in ("LC01-S","EXT05C-S")]
    ids += [("BY2H",m,s) for m in aggregate.EXTERNAL_METHODS for s in ("FILE_START","CONTRACT_START")]
    ids += [("BY2O",m,"FILE_START") for m in aggregate.EXTERNAL_METHODS]
    records = []
    for index,(sequence,method,start) in enumerate(ids):
        base = tmp_path/"scratch"/str(index)
        base.mkdir(parents=True)
        bad = sequence=="BY2H" and method=="EXT05C-S" and start=="FILE_START"
        geometry = {"terminal_status":"UNAVAILABLE","error":"horizontal baseline threshold failed"}
        native = base/"native.json"
        native.write_text(json.dumps({"geometric_audit":geometry if sequence=="BY2H" else {"thresholds_pass":True}}))
        gap = base/"gaps.json"
        gap.write_text("[]")
        record = dict(run_id=str(index),sequence_id=sequence,configuration_id=method,start_mode=start,
            native_summary_path=str(native),gap_log_path=str(gap),evaluations={},evaluation_dispositions={},
            native_status="ALGORITHM_FAILURE_DIVERGED" if bad else "COMPLETED")
        for version in ("v3","v2"):
            folder = base/version
            folder.mkdir()
            if bad:
                payload = _failed_payload(version)
            else:
                _errors(list(seqs[sequence].window)).to_csv(folder/"error_series.csv",index=False)
                payload = {"row":_source(version,error_series_source=str(folder)),"body_frame_bias":{},
                           "audit":{"passed":True,"trace_open_count":1}}
            result = folder/"EVALUATION_RESULT.json"
            result.write_text(json.dumps(payload))
            record["evaluations"][version] = str(result)
            record["evaluation_dispositions"][version] = ("NEW_H03_D7_CLASSIFICATION" if bad else
                "REUSED_H02_COMPLETED" if index == 0 else "NEW_H03_EVALUATED")
        records.append(record)
    out = tmp_path/"clean/08_AGGREGATE"
    summary = aggregate.aggregate_stage(sequences=seqs,records=records,output_root=out,
        code_commit="synthetic_fixture",budget_ledger={"synthetic_fixture":True},continuation_v11=True)
    with (out/"HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows)==31
    reused = next(r for r in rows if r["sequence_id"]=="BY2" and r["method_id"]=="LC01-S")
    new = next(r for r in rows if r["sequence_id"]=="BY2" and r["method_id"]=="EXT05C-S")
    assert json.loads(reused["notes"])["result_reused"] is True
    assert json.loads(new["notes"])["result_reused"] is False
    assert json.loads(reused["notes"])["native_result_reused"] is True
    assert json.loads(reused["notes"])["scientific_code_commit"] == "synthetic_fixture"
    assert reused["code_commit"] == "synthetic_fixture"
    assert summary["primary_starts"]==aggregate.H03_PRIMARY_STARTS
    assert summary["native_registered_count"]==14 and summary["new_native_budget"]==0
    assert summary["evaluation_disposition_counts"]["NOT_RUN_ALGORITHM_FAILURE"]==2
    assert summary["native_classification_counts"]["ALGORITHM_FAILURE_DIVERGED"]==1
    assert len([r for r in rows if r["manuscript_row"]=="True"])==12
    paper = [r for r in rows if r["method_id"]=="LC01-S" and r["manuscript_row"]=="True"]
    assert {r["sequence_id"]:r["start_convention"] for r in paper}==aggregate.H03_PRIMARY_STARTS
    failed = next(r for r in rows if r["evaluation_status"]=="NOT_RUN_ALGORITHM_FAILURE")
    assert failed["h_rmse_m"]=="UNAVAILABLE"
    geometric = next(r for r in paper if r["sequence_id"]=="BY2H")
    assert geometric["evaluation_status"]=="AVAILABLE_GEOMETRIC_AUDIT_FAIL"
    with (out/"WINDOW_SEGMENT_SUMMARY.csv").open() as handle:
        segments = list(csv.DictReader(handle))
    assert len(segments)==56
    assert len([r for r in segments if r["status"]=="NOT_RUN_ALGORITHM_FAILURE"])==2
    assert len([r for r in segments if r["status"]=="UNAVAILABLE_FROZEN_SAME_WINDOW_SEGMENT"])==12
    methods, selected = figures.select_plot_rows(rows,summary["selection"])
    assert methods==("LC01-S","F02","A04","F04")
    assert selected[("BY2H","LC01-S")]["start_convention"]=="CONTRACT_START"
    text = figures.caption(summary["selection"],rows)
    assert "amended_after_results_seen=true" in text and "direction is mixed" in text
    geometric["start_convention"]="FILE_START"
    with pytest.raises(ValueError,match="differs from D9"):
        figures.select_plot_rows(rows,summary["selection"])
