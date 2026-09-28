"""Identity orchestration tests with fake evaluators and synthetic local data."""
import csv
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean5_sequence import evaluator_identity as identity
from legsa_gins.paper_rebuild.manifest import sha256_file


def summary(distance=0.,yaw=0.):
    return {"position":{"horizontal_rmse_m":distance*.6,"horizontal_p95_m":distance*.6,
                         "horizontal_max_m":distance*.6,"position_3d_rmse_m":distance,
                         "up_rmse_m":distance*.8,"vertical_p95_m":distance*.8,"vertical_max_m":distance*.8},
            "attitude":{"yaw_rmse_deg":yaw,"yaw_p95_deg":yaw,"yaw_max_deg":yaw}}


def fake_evaluate(calls,*,fail_name=None,change_baseline_bytes=False):
    def evaluate(**kwargs):
        calls.append(kwargs)
        outdir=Path(kwargs["outdir"])
        outdir.mkdir(parents=True,exist_ok=False)
        if outdir.name==fail_name:
            (outdir/"evaluator_stderr.log").write_text("synthetic forced failure")
            raise RuntimeError("synthetic forced failure")
        distance=1000. if outdir.name=="swap_inst" else 0.
        yaw=90. if outdir.name=="yaw90_inst" else 0.
        if outdir.name.startswith("C00_"):
            method=outdir.name.removeprefix("C00_")
            distance=2.
            yaw=identity.C00[method]["yaw_round6"]
        metrics=summary(distance,yaw)
        text=json.dumps(metrics,sort_keys=True)
        if change_baseline_bytes and outdir.name=="plain_inst":text+="\n"
        (outdir/"summary.json").write_text(text)
        pd.DataFrame({"time":[10.,11.,12.],"position_3d_err_m":[distance]*3}).to_csv(outdir/"error_series.csv",index=False)
        capture={"selected_columns":dict(identity.EXPECTED_COLUMNS),"trace_header":list(identity.TRACE_HEADER),
                 "trace_handle_hash_count":1,"observation_only":True,"trace_sha256":kwargs["trace_sha256"]}
        return {"outdir":str(outdir),"summary":metrics,"runtime_seconds":.01,
                "audit":{"passed":True,"trace_open_count":1},
                "capture":capture if kwargs["instrument"] else None}
    return evaluate


def fixture_registry(tmp_path):
    clean,raw,code=(tmp_path/name for name in ("clean","raw","code"))
    for path in (clean,raw,code):path.mkdir()
    return SimpleNamespace(clean_root=clean,raw_root=raw,code_root=code,
        sequences={"BY2":SimpleNamespace(trace_path=raw/"trace_by2_synthetic_placeholder.csv")})


def make_c00_metadata(registry):
    attempt=registry.clean_root/"canonical_synthetic"
    identities,results,sealed=[],[],[]
    for method,item in identity.C00.items():
        output=attempt/item["directory"]/item["run_id"]
        output.mkdir(parents=True)
        for name in ("KF_GINS_Navresult.nav","KF_GINS_STD.txt","RUN_MANIFEST.json"):
            (output/name).write_text("synthetic identity fixture\n")
            sealed.append({"run_id":item["run_id"],"run_root":str(output),"relative_path":name,
                "sha256":sha256_file(output/name),"size_bytes":(output/name).stat().st_size,
                "terminal_status":"COMPLETED_EVALUABLE","sealed_before_trace":True})
        base={"case_id":"C00_clean_normal","run_id":item["run_id"],"method_id":method,"output_root":str(output)}
        identities.append({**base,"effective_profile":item["profile"],"terminal_status":"COMPLETED_EVALUABLE"})
        frozen={field:summary(2.,item["yaw_round6"])[group][key] for field,(group,key) in identity.METRIC_SUMMARY_PATHS.items()}
        results.append({**base,"effective_configuration_id":item["profile"],"evaluation_status":"COMPLETED",
                        **frozen,"position_3d_p95_m":2.,"position_3d_max_m":2.})
    for relative,rows in (("11_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv",identities),
                          ("12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv",results),
                          ("11_OUTPUT_SEAL/OUTPUT_HASH_MANIFEST.csv",sealed)):
        path=attempt/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
    (attempt/"11_OUTPUT_SEAL/OUTPUT_SEAL_JOURNAL.json").write_text(json.dumps({
        "schema_version":"paper_rebuild.canonical541_output_seal.v1","passed":True,
        "sealed_before_offline_trace":True,"trace_open_count_before_seal":0,"file_count":len(sealed),
        "manifest_sha256":sha256_file(attempt/"11_OUTPUT_SEAL/OUTPUT_HASH_MANIFEST.csv"),
        "unique_registry_sha256":sha256_file(attempt/"11_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv")}))
    return attempt


def test_synthetic_geometry_is_exact_1000m_with_three_changed_geodetic_fields(tmp_path):
    inputs=identity.create_synthetic_inputs(tmp_path/"SYNTHETIC_INPUTS")
    plain=pd.read_csv(inputs["trace"]["plain"]["path"])
    swapped=pd.read_csv(inputs["trace"]["swap"]["path"])
    yaw=pd.read_csv(inputs["trace"]["yaw90"]["path"])
    assert list(plain.columns)==list(identity.TRACE_HEADER)
    actual,processed=plain[["lat","lon","height"]].to_numpy(),plain[["processed_lat","processed_lon","processed_height"]].to_numpy()
    assert np.all(actual!=processed)
    offsets=[np.linalg.norm(identity._lla_to_ecef(*p)-identity._lla_to_ecef(*a)) for p,a in zip(processed,actual)]
    assert max(abs(value-1000.) for value in offsets)<1e-6
    assert np.array_equal(swapped[["lat","lon","height"]].to_numpy(),processed)
    assert np.all(yaw.yaw.to_numpy()-plain.yaw.to_numpy()==90.)
    ecef=np.array([identity._lla_to_ecef(*position) for position in actual])
    assert np.max(np.abs(np.diff(ecef,axis=0)-np.array([2.,-1.,.5])))<1e-6
    assert np.array_equal(np.diff(plain.yaw.to_numpy()),np.full(10,2.))
    assert inputs["synthetic_data_used"] and not inputs["eligible_for_real_result_tables"]
    for record in [*inputs["trace"].values(),inputs["nav"],inputs["std"]]:
        assert sha256_file(record["path"])==record["sha256"]


def test_synthetic_invocation_order_hook_byte_parity_and_independent_gate(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    root=registry.clean_root/"identity";root.mkdir()
    calls=[]
    monkeypatch.setattr(identity.evaluation_process,"evaluate",fake_evaluate(calls))
    result=identity.run_synthetic(registry=registry,evaluator=Path("synthetic_evaluator.py"),identity_root=root,proof={"synthetic_source":True})
    assert result["passed"]
    assert [Path(call["outdir"]).name for call in calls]==["plain_uninst","plain_inst","swap_inst","yaw90_inst"]
    assert [call["instrument"] for call in calls]==[False,True,True,True]
    assert all(Path(call["trace"]).is_relative_to(root/"SYNTHETIC_INPUTS") for call in calls)
    assert all(row["byte_identical"] for row in result["instrumented_uninstrumented_byte_parity"].values())
    assert all(result["checks"].values())
    assert (root/"A2_2_SYNTHETIC_GATE.json").is_file()


def test_byte_difference_fails_even_when_all_numeric_metrics_identical(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    root=registry.clean_root/"identity";root.mkdir()
    monkeypatch.setattr(identity.evaluation_process,"evaluate",fake_evaluate([],change_baseline_bytes=True))
    result=identity.run_synthetic(registry=registry,evaluator="fake.py",identity_root=root,proof={})
    assert not result["passed"]
    assert "changed baseline evaluator bytes" in result["failures"][0]
    assert json.loads((root/"A2_2_SYNTHETIC_GATE.json").read_text())["passed"] is False
    assert (root/"SCRATCH/plain_inst/summary.json").is_file()


def test_synthetic_failure_preserves_artifacts_and_stops_before_c00(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    root=registry.clean_root/"identity"
    calls=[]
    monkeypatch.setattr(identity,"source_proof",lambda *_:{"synthetic_source":True})
    monkeypatch.setattr(identity.evaluation_process,"evaluate",fake_evaluate(calls,fail_name="swap_inst"))
    monkeypatch.setattr(identity,"run_known_c00",lambda **_:pytest.fail("C00 must not run after synthetic failure"))
    result=identity.run_known_and_synthetic(registry,registry.clean_root/"unused","fake.py",root)
    assert not result["passed_known_and_synthetic"]
    assert result["A2_1"] is None
    assert (root/"SCRATCH/swap_inst/evaluator_stderr.log").read_text()=="synthetic forced failure"
    assert len(calls)==3


def test_c00_known_reproduction_uses_locked_trace_hash_without_parent_read(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    attempt=make_c00_metadata(registry)
    root=registry.clean_root/"identity";root.mkdir()
    trace=registry.sequences["BY2"].trace_path
    assert not trace.exists()  # fake child accepts identity only; parent must not open it
    monkeypatch.setattr(identity,"selected_lock",lambda *_:{"rows":{trace.name:{"sha256":"e"*64}},
        "path":"synthetic_hash_lock.csv","sha256":"a"*64})
    calls=[]
    monkeypatch.setattr(identity.evaluation_process,"evaluate",fake_evaluate(calls))
    result=identity.run_known_c00(registry=registry,canonical_attempt=attempt,evaluator="fake.py",identity_root=root)
    assert result["passed"]
    assert [Path(call["outdir"]).name for call in calls]==["C00_A04","C00_F04"]
    assert all(call["trace_sha256"]=="e"*64 and call["window"]==[66.,340.] for call in calls)
    assert "10_INTERNAL_ABLATION_RUNS" in str(calls[0]["nav"])
    assert "08_FULL_ALGORITHM_RUNS" in str(calls[1]["nav"])
    assert [row["comparison"]["yaw_round6_gate"]["fresh_yaw_rmse_rounded_6"] for row in result["runs"]]==[1.934076,1.954959]
    assert all(len(row["comparison"]["metric_comparisons"])==12 for row in result["runs"])
    assert result["raw_reference_identity"]["parent_reference_open_count"]==0


def test_c00_missing_3d_summary_fields_come_from_new_csv(tmp_path):
    outdir=tmp_path/"fresh";outdir.mkdir()
    pd.DataFrame({"time":[1.,2.,3.],"position_3d_err_m":[1.,2.,4.]}).to_csv(outdir/"error_series.csv",index=False)
    result=identity._result_metrics({"outdir":str(outdir),"summary":summary(3.,2.)})
    assert result["position_3d_p95_m"]==pytest.approx(3.8)
    assert result["position_3d_max_m"]==4.
    assert result["position_3d_rmse_m"]==3.


def test_c00_comparison_preserves_frozen_tokens_and_fixed_tolerance():
    metrics={field:summary(2.,1.934076)[group][key] for field,(group,key) in identity.METRIC_SUMMARY_PATHS.items()}
    metrics.update(position_3d_p95_m=2.,position_3d_max_m=2.)
    frozen={"row":{field:format(value,".17g") for field,value in metrics.items()},"physical_csv_row":7}
    assert identity.compare_c00(metrics,frozen,method="A04")["passed"]
    metrics["horizontal_rmse_m"]+=2e-10
    result=identity.compare_c00(metrics,frozen,method="A04")
    assert not result["passed"]
    row=next(row for row in result["metric_comparisons"] if row["field"]=="horizontal_rmse_m")
    assert row["frozen_physical_csv_row"]==7 and row["relative_tolerance"]==1e-10
    assert row["frozen_token"]==frozen["row"]["horizontal_rmse_m"]


@pytest.mark.parametrize("expected,difference,passed",[(.1,5e-11,False),(100.,5e-9,True),(0.,0.,True),(0.,1e-15,False)])
def test_c00_relative_tolerance_and_zero_reference_rule(expected,difference,passed):
    metrics={field:summary(2.,1.934076)[group][key] for field,(group,key) in identity.METRIC_SUMMARY_PATHS.items()}
    metrics.update(position_3d_p95_m=2.,position_3d_max_m=2.,horizontal_rmse_m=expected)
    frozen={"row":{field:str(value) for field,value in metrics.items()},"physical_csv_row":7}
    metrics["horizontal_rmse_m"]+=difference
    result=identity.compare_c00(metrics,frozen,method="A04")
    assert result["passed"] is passed
    row=next(row for row in result["metric_comparisons"] if row["field"]=="horizontal_rmse_m")
    if expected!=0:
        assert row["relative_difference"]==abs(metrics["horizontal_rmse_m"]-expected)/abs(expected)
    assert row["zero_reference_requires_exact_zero"]


def test_c00_tampered_nav_fails_seal_before_evaluator_launch(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    attempt=make_c00_metadata(registry)
    root=registry.clean_root/"identity";root.mkdir()
    trace=registry.sequences["BY2"].trace_path
    monkeypatch.setattr(identity,"selected_lock",lambda *_:{"rows":{trace.name:{"sha256":"e"*64}},
        "path":"synthetic_hash_lock.csv","sha256":"a"*64})
    nav=attempt/"10_INTERNAL_ABLATION_RUNS/RUN_00006/KF_GINS_Navresult.nav"
    nav.write_text("synthetic mutation after seal")
    monkeypatch.setattr(identity.evaluation_process,"evaluate",lambda **_:pytest.fail("No evaluator launch for a changed sealed input"))
    result=identity.run_known_c00(registry=registry,canonical_attempt=attempt,evaluator="fake.py",identity_root=root)
    assert not result["passed"]
    assert "differs from Canonical output seal" in result["failures"][0]
    assert (root/"A2_1_C00_REPRODUCTION_GATE.json").is_file()


def test_c00_seal_manifest_must_match_journal_hash(tmp_path):
    registry=fixture_registry(tmp_path)
    attempt=make_c00_metadata(registry)
    path=attempt/"11_OUTPUT_SEAL/OUTPUT_HASH_MANIFEST.csv"
    with path.open("a") as handle:handle.write("\n")
    with pytest.raises(ValueError,match="integrity mismatch"):
        identity._c00_seal(attempt)


def test_partial_identity_is_never_a_joint_header_pass(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    root=registry.clean_root/"identity"
    monkeypatch.setattr(identity,"source_proof",lambda *_:{})
    order=[]
    def synthetic(**kwargs):order.append("synthetic");return {"passed":True}
    def known(**kwargs):order.append("known");return {"passed":True}
    monkeypatch.setattr(identity,"run_synthetic",synthetic)
    monkeypatch.setattr(identity,"run_known_c00",known)
    result=identity.run_known_and_synthetic(registry,"unused","fake.py",root)
    assert order==["synthetic","known"]
    assert result["passed_known_and_synthetic"] and result["ready_for_header_gate"]
    assert result["full_identity_gate"]=="PENDING_A2_3_HEADER_EVIDENCE"
    assert result["real_sequence_evaluations_executed"]==0


def test_source_proof_records_original_function_lines_and_rejects_wrong_hash(tmp_path,monkeypatch):
    source=tmp_path/"synthetic_evaluator.py"
    source.write_text("def load_trace(path, base_time):\n"+"".join(
        f"    {name}_col = find_col([{role!r}])\n" for name,role in
        (("time","time"),("lat","lat"),("lon","lon"),("alt","height"),("yaw","yaw"),("pitch","pitch"),("roll","roll")))+
        "    return path\n")
    with pytest.raises(ValueError,match="SHA256"):
        identity.source_proof(source)
    monkeypatch.setattr(identity.evaluation_process,"EVALUATOR_SHA256",sha256_file(source))
    result=identity.source_proof(source)
    assert result["line_start"]==1 and result["line_end"]==9
    assert result["expected_selected_columns"]["lat"]=="lat"
    assert result["column_resolution"]["lat"]["assignment_source_line"]==3
    assert result["column_resolution"]["lat"]["expected_synthetic_column"]=="lat"
    assert result["unselected_synthetic_columns"]==["processed_lat","processed_lon","processed_height"]
    assert result["evaluator_modified"] is False


def test_existing_identity_outputs_are_never_overwritten(tmp_path,monkeypatch):
    registry=fixture_registry(tmp_path)
    root=registry.clean_root/"identity"
    (root/"SCRATCH").mkdir(parents=True)
    monkeypatch.setattr(identity,"source_proof",lambda *_:pytest.fail("No source work after overwrite rejection"))
    with pytest.raises(FileExistsError,match="no retry"):
        identity.run_known_and_synthetic(registry,"unused","fake.py",root)


def test_real_raw_directory_cannot_hold_identity_outputs(tmp_path):
    registry=fixture_registry(tmp_path)
    with pytest.raises(ValueError,match="confined non-raw"):
        identity.run_known_and_synthetic(registry,"unused","fake.py",registry.raw_root/"identity")


@pytest.mark.skipif(not os.environ.get("LEGSA_EXACT_EVALUATOR"),reason="Optional archived evaluator synthetic-only identity test")
def test_live_archived_evaluator_synthetic_only_all_four_calls(tmp_path):
    registry=fixture_registry(tmp_path)
    registry.code_root=Path(__file__).resolve().parents[2]
    evaluator=Path(os.environ["LEGSA_EXACT_EVALUATOR"])
    root=registry.clean_root/"live_synthetic_identity";root.mkdir()
    result=identity.run_synthetic(registry=registry,evaluator=evaluator,identity_root=root,
                                  proof=identity.source_proof(evaluator))
    assert result["passed"],result["failures"]
    assert len(result["runs"])==4
    assert all(run["audit"]["synthetic_data_used"] is True for run in result["runs"])
    assert all(run["audit"]["raw_open_count"]==0 for run in result["runs"])
    assert all(item["byte_identical"] for item in result["instrumented_uninstrumented_byte_parity"].values())
    assert all(result["checks"].values())
    for run in result["runs"]:
        if run["instrumented"]:
            assert all(row["assignment_source_line"] is not None for row in run["selection_gate"]["actual_column_resolution"].values())
