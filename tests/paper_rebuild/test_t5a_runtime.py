"""Synthetic-only T5a identity/budget/failure tests; no real native/trace access."""
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from legsa_gins.paper_rebuild.hext import t5a_runtime as se

def _nav(path, rows):
    path.write_text("% synthetic fixture only\n" + "\n".join(" ".join(str(v) for v in row) for row in rows) + "\n")
    return se.sha256_file(path)


def _base_rows():
    return [[0, 1., 30., 120., 10., 0., 0., 0., 0., 0., 0.],
            [1, 1.5, 30., 120., 10., 0., 0., 0., 0., 0., 0.]]


def test_lla_d8_uses_metres_and_first_fixed_frame_not_degrees(tmp_path):
    path = tmp_path / "nav"
    rows = _base_rows()
    rows[1][2] += .2
    digest = _nav(path, rows)
    gate = se.bounded_lla_native(path, expected_sha256=digest)
    assert not gate["passed"]
    assert gate["maxima"]["position_displacement_m"] > 20000
    assert gate["first_violation"]["file_line_one_based"] == 3
    assert gate["source_nav_sha256"] == digest
    rows[1][2] = rows[0][2]
    rows[1][4] += 1000
    rows[1][5:8] = [30., 40., 0.]
    digest = _nav(path, rows)
    assert se.bounded_lla_native(path, expected_sha256=digest)["passed"]


@pytest.mark.parametrize("column,value,reason", [(5, 50.01, "speed_mps"), (4, 1010.01, "height_displacement_m"),
                                                 (10, float("nan"), "NONFINITE_NUMERIC_NATIVE_ROW")])
def test_lla_d8_rejects_all_nonfinite_fields_and_bound_crossings(tmp_path, column, value, reason):
    path = tmp_path / "nav"
    rows = _base_rows()
    rows[1][column] = value
    gate = se.bounded_lla_native(path, expected_sha256=_nav(path, rows))
    assert not gate["passed"] and reason in gate["first_violation"]["reasons"]
    json.dumps(gate, allow_nan=False)


def test_d8_wrong_nav_hash_and_column_count_fail_closed(tmp_path):
    path = tmp_path / "nav"
    _nav(path, _base_rows())
    with pytest.raises(RuntimeError, match="IDENTITY"):
        se.bounded_lla_native(path, expected_sha256="0" * 64)
    rows = [r[:-1] for r in _base_rows()]
    with pytest.raises(ValueError, match="column count"):
        se.bounded_lla_native(path, expected_sha256=_nav(path, rows))


def test_native_argv_isolates_outputs_without_config_outputpath_change(tmp_path):
    argv = se.native_argv(tmp_path / "binary", tmp_path / "config", tmp_path / "new")
    assert argv[argv.index("--output-dir") + 1] == str(tmp_path / "new")
    assert argv[argv.index("--debug-output-dir") + 1] == str(tmp_path / "new")
    assert "--debug-update-timeline" in argv


@pytest.mark.parametrize("kind,size", [("native",16),("evaluator",32)])
def test_reservation_consumes_exact_budget_without_retry(tmp_path,kind,size):
    allowed = {"run"+str(i) for i in range(size)}
    ledger = tmp_path / kind
    for i in range(size):
        assert se.reserve_slot(ledger,"run"+str(i),allowed,kind=kind)["ordinal"] == i+1
    with pytest.raises(RuntimeError, match="NO_RETRY"):
        se.reserve_slot(ledger,"run0",allowed,kind=kind)
    with pytest.raises(PermissionError, match="unregistered"):
        se.reserve_slot(ledger,"run_more",allowed|{"run_more"},kind=kind)
    assert len(ledger.read_text().splitlines()) == size


def test_only_gnsspath_field_changes_and_duplicates_denied():
    old = b"gnsspath: old\noutputpath: frozen\nenable_multi_state_qm: false\nenable_qa_fallback: false\nyaw_std: 2.933193\n"
    new, gate = se.clone_runtime_config(old,expected_sha256=sha256(old).hexdigest(),gnsspath="new")
    before, after = yaml.safe_load(old), yaml.safe_load(new)
    assert after.pop("gnsspath") == "new"
    before.pop("gnsspath")
    assert after == before and gate["non_gnsspath_sha256_before"] == gate["non_gnsspath_sha256_after"]
    assert gate["enable_multi_state_qm"] is False and gate["enable_qa_fallback"] is False
    with pytest.raises(RuntimeError,match="CONFIG_IDENTITY"):
        se.clone_runtime_config(old,expected_sha256="0"*64,gnsspath="new")
    duplicate = b"gnsspath: a\ngnsspath: b\n"
    with pytest.raises(ValueError,match="duplicate"):
        se.clone_runtime_config(duplicate,expected_sha256=sha256(duplicate).hexdigest(),gnsspath="new")


def test_native_rechecks_non_yaw_bytes_and_exact_std():
    left = b"0 1 2 3 4 5 6 7 8 9 10 11 12 90 2.933193 1 1 1\n"
    assert se._non_yaw_gate(left,left.replace(b" 90 ",b" 91 "))["passed"]
    with pytest.raises(RuntimeError,match="NON_YAW_BYTE"):
        se._non_yaw_gate(left,left.replace(b" 12 ",b" 13 "))
    with pytest.raises(RuntimeError,match="STD_OR_VALIDITY"):
        se._non_yaw_gate(left,left.replace(b"2.933193",b"2.0"))


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    scratch, clean, raw, code = (tmp_path / name for name in ("scratch", "clean", "raw", "code"))
    native = scratch / "03_NATIVE/BY2H/F04/R5"
    native.mkdir(parents=True)
    nav = native / "KF_GINS_Navresult.nav"
    nav.write_text("% synthetic-only native\n"
                   "0 413.000000 30.0000000000 120.0000000000 50.000 0 0 0 1 2 90\n"
                   "1 414.000000 30.0000000000 120.0000000000 50.000 0 0 0 1 2 91\n"
                   "2 415.000000 30.0000000000 120.0000000000 50.000 0 0 0 1 2 92\n")
    std = native / "KF_GINS_STD.txt"
    std.write_text("413 .1 .1 .1 .1 .1 .1 .1 .1 .1\n414 .1 .1 .1 .1 .1 .1 .1 .1 .1\n415 .1 .1 .1 .1 .1 .1 .1 .1 .1\n")
    evaluator = tmp_path / "synthetic-evaluator.py"
    evaluator.write_text("# synthetic identity only; never executed\n")
    monkeypatch.setattr(se, "EVALUATOR_SHA256", _hash(evaluator))
    sequence = SimpleNamespace(sequence_id="BY2H", hext_scratch=scratch, clean_root=clean,
        raw_root=raw, code_root=code, trace=raw/"never-open-trace.csv", trace_sha256="a"*64,
        window=(413., 683.), base_time=1772784000.)
    args = dict(sequence=sequence, evaluator=evaluator, nav=nav, std=std,
        outdir=scratch/"04_EVAL/v2/BY2H__F04__R5", version="v2",
        identity={"run_id":"BY2H__F04__R5", "method_id":"F04", "configuration_id":"F04", "variant":"R5",
                  "synthetic_data_used":True,"data_mode":"synthetic_test_only"},
        expected_nav_sha256=_hash(nav), expected_std_sha256=_hash(std), baseline_median_m=.354,
        bounded_gate={"passed":True,"source_nav_sha256":_hash(nav)},
        scratch_root=scratch,launch_ledger=scratch/"EVALUATOR_LEDGER.jsonl",
        allowed_run_ids={"BY2H__F04__R5__v3","BY2H__F04__R5__v2"})
    calls = []
    def fake_evaluate(**kwargs):
        calls.append(kwargs)
        directory = kwargs["outdir"]
        directory.mkdir(parents=True)
        errors = pd.DataFrame({"time":[413.,414.,415.], "err_n_m":[1.,1.,1.],"err_e_m":[2.,2.,2.],
            "err_u_m":[3.,3.,3.],"horizontal_err_m":[np.sqrt(5.)]*3,"position_3d_err_m":[np.sqrt(14.)]*3,
            "roll_err_deg":[0.,0.,0.],"pitch_err_deg":[0.,0.,0.],"yaw_err_deg":[-1.,0.,1.]})
        errors.to_csv(directory/"error_series.csv",index=False)
        return {"outdir":str(directory),"runtime_seconds":.25,
            "audit":{"passed":True,"exit_code":0,"trace_open_count":1,"bag_open_count":0,"fpl_open_count":0,
                     "write_scope":{"pass":True}},
            "capture":{"trace_sha256":sequence.trace_sha256,"trace_handle_hash_count":1,
                       "selected_columns":dict(se.SELECTED_COLUMNS),"reference_epoch_count":30,
                       "consistency":{"passed":True}}}
    monkeypatch.setattr(se,"evaluate",fake_evaluate)
    return args,calls,fake_evaluate


def test_v2_uses_original_same_run_std_canonical_policy_and_sequence_window(setup):
    args,calls,_ = setup
    result = se.evaluate_native(**args)
    assert len(calls)==1
    assert calls[0]["nav"]==args["nav"] and calls[0]["std"]==args["std"]
    assert calls[0]["instrument"] is True and calls[0]["measure_resources"] is True
    assert calls[0]["consistency_policy"]=="canonical_v2_wgs84_full_support"
    row = result["row"]
    assert row["evaluation_status"]=="COMPLETED" and row["metrics_admitted"] is True
    assert row["output_epoch_count"]==3 and row["coverage_ratio"]==1.
    assert row["yaw_rmse_deg"]==pytest.approx(np.sqrt(2/3))
    assert row["sequence_window_start_s"]==413 and row["main_table_admission"] is False
    assert result["transform"]["std_transformed"] is False
    assert json.loads((args["outdir"]/"EVALUATION_RESULT.json").read_text())["row"]==row
    assert not args["sequence"].trace.exists()


def test_v3_changes_only_llh_tokens_and_never_transforms_std(setup):
    args,calls,_ = setup
    args["version"]="v3"
    before_nav,before_std=args["nav"].read_bytes(),args["std"].read_bytes()
    result=se.evaluate_native(**args)
    actual=calls[0]["nav"]
    assert actual!=args["nav"] and calls[0]["std"]==args["std"]
    old=[line.split() for line in before_nav.decode().splitlines() if not line.startswith("%")]
    new=[line.split() for line in actual.read_text().splitlines()]
    for left,right in zip(old,new):
        assert [left[k] for k in range(11) if k not in (2,3,4)]==[right[k] for k in range(11) if k not in (2,3,4)]
        assert left[2:5]!=right[2:5]
    assert args["nav"].read_bytes()==before_nav and args["std"].read_bytes()==before_std
    assert result["row"]["uncertainty_status"]=="UNTRANSPORTED_STD_DIAGNOSTIC_ONLY"
    assert result["transform"]["output_sha256"]==_hash(actual)


def test_d12_consistency_failure_never_admits_metrics_or_calls_metric_helpers(setup,monkeypatch):
    args,_,fake=setup
    args["identity"].update(yaw_rmse_deg=1.,horizontal_rmse_m=.1,coverage_ratio=1.)
    def false_consistency(**kwargs):
        result=fake(**kwargs);result["capture"]["consistency"]["passed"]=False;return result
    monkeypatch.setattr(se,"evaluate",false_consistency)
    monkeypatch.setattr(se,"window_metrics",lambda *a,**k:pytest.fail("No metrics after consistency failure"))
    result=se.evaluate_native(**args)
    assert result["row"]["evaluation_status"]=="UNAVAILABLE_EVALUATION_FAILED"
    assert result["row"]["metrics_admitted"] is False
    assert result["audit"]["technical_passed"] is True and result["audit"]["consistency_passed"] is False
    assert not any(name in result["row"] for name in ("yaw_rmse_deg","horizontal_rmse_m","coverage_ratio"))
    assert result["body_frame_bias"]["status"]=="UNAVAILABLE_EVALUATION_FAILED"


@pytest.mark.parametrize("gate", [{"passed":False},{"passed":True,"source_nav_sha256":"0"*64},None])
def test_unbound_or_failed_d8_denied_before_creation_or_launch(setup,gate):
    args,calls,_=setup
    args["bounded_gate"]=gate
    with pytest.raises(ValueError,match="identity-bound"):
        se.evaluate_native(**args)
    assert calls==[] and not args["outdir"].exists()


@pytest.mark.parametrize("role", ["nav","std","evaluator"])
def test_source_hash_failure_precedes_process_and_output(setup,role):
    args,calls,_=setup
    args[role].write_text("changed synthetic bytes")
    with pytest.raises(RuntimeError,match="INPUT_IDENTITY"):
        se.evaluate_native(**args)
    assert calls==[] and not args["outdir"].exists()


@pytest.mark.parametrize("role", ["nav","std","evaluator"])
def test_post_evaluation_hash_drift_is_hard_even_on_consistency_failure(setup,monkeypatch,role):
    args,_,fake=setup
    def drift(**kwargs):
        result=fake(**kwargs)
        args[role].write_bytes(args[role].read_bytes()+b"\n# mutation")
        result["capture"]["consistency"]["passed"]=False
        return result
    monkeypatch.setattr(se,"evaluate",drift)
    with pytest.raises(RuntimeError,match="INPUT_IDENTITY"):
        se.evaluate_native(**args)
    assert not (args["outdir"]/"EVALUATION_RESULT.json").exists()


def test_evaluator_process_exception_is_not_converted_to_unavailable(setup,monkeypatch):
    args,_,_=setup
    def fail(**kwargs):
        raise RuntimeError("synthetic evaluator_returncode=1")
    monkeypatch.setattr(se,"evaluate",fail)
    with pytest.raises(RuntimeError,match="evaluator_returncode=1"):
        se.evaluate_native(**args)
    assert not (args["outdir"]/"EVALUATION_RESULT.json").exists()


@pytest.mark.parametrize("bad", ["audit","capture","missing_consistency","columns"])
def test_technical_audit_or_identity_failure_cannot_be_d12_soft(setup,monkeypatch,bad):
    args,_,fake=setup
    def invalid(**kwargs):
        result=fake(**kwargs)
        result["capture"]["consistency"]["passed"]=False
        if bad=="audit":result["audit"]["passed"]=False
        elif bad=="capture":result["capture"]["trace_sha256"]="0"*64
        elif bad=="columns":result["capture"]["selected_columns"]["yaw"]="not_the_frozen_yaw_column"
        else:result["capture"].pop("consistency")
        return result
    monkeypatch.setattr(se,"evaluate",invalid)
    with pytest.raises(RuntimeError,match="HARD_STOP_SENSITIVITY_EVALUATOR"):
        se.evaluate_native(**args)


def test_nav_outside_window_rejected_without_clipping(setup):
    args,calls,_=setup
    args["sequence"].window=(414.,683.)
    with pytest.raises(ValueError,match="outside the frozen"):
        se.evaluate_native(**args)
    assert calls==[] and not args["outdir"].exists()


def test_evaluated_error_support_outside_window_is_hard(setup,monkeypatch):
    args,_,fake=setup
    def bad_errors(**kwargs):
        result=fake(**kwargs)
        path=Path(result["outdir"])/"error_series.csv"
        errors=pd.read_csv(path);errors.loc[2,"time"]=684.;errors.to_csv(path,index=False)
        return result
    monkeypatch.setattr(se,"evaluate",bad_errors)
    with pytest.raises(RuntimeError,match="ERROR_SUPPORT"):
        se.evaluate_native(**args)


def test_frozen_output_root_and_cross_run_std_are_rejected(setup):
    args,calls,_=setup
    original=args["outdir"]
    args["outdir"]=args["sequence"].clean_root/"stages/CLEAN6_SENSOR_MODEL_V21/forbidden"
    with pytest.raises(ValueError,match="registered scratch"):
        se.evaluate_native(**args)
    args["outdir"]=original
    args["std"]=args["std"].parent.parent/"another_run/KF_GINS_STD.txt"
    with pytest.raises(ValueError,match="same native"):
        se.evaluate_native(**args)
    assert calls==[]


@pytest.mark.parametrize("baseline", [float("nan"),0.,-1.])
def test_invalid_baseline_denied_before_output_or_evaluation(setup,baseline):
    args,calls,_=setup
    args["baseline_median_m"]=baseline
    with pytest.raises(ValueError,match="baseline"):
        se.evaluate_native(**args)
    assert calls==[] and not args["outdir"].exists()


def native_fixture(tmp_path, monkeypatch):
    clean, code, scratch = (tmp_path / key for key in ("clean", "code", "scratch"))
    for directory in (clean, code, scratch):
        directory.mkdir()
    sequence = SimpleNamespace(sequence_id="BY2", clean_root=clean, code_root=code,
        raw_root=tmp_path/"never-open-raw", trace=tmp_path/"never-open-raw/trace", window=(1.,2.))
    cfg = {"run_id":"RUN_00004", "outputpath":"/immutable/old/output", "stage_id":"FROZEN_STAGE",
           "protocol_id":"FROZEN_PROTOCOL", "case_id":"C00", "algorithm_id":"AB1111",
           "data_mode":"real_clean", "runtime_role":"frozen_role",
           "enable_multi_state_qm":False, "enable_qa_fallback":False}
    cfg.update({key:False for key in se.CONFIG_FLAG_TO_MANIFEST})
    cfg.update(enable_dual_yaw=True,enable_raw_doppler=True,enable_go2_roll_pitch_prior=True,
               enable_go2_horizontal_velocity_prior=True)
    for key in se.PROVIDER_KEYS:
        path = clean / key
        path.write_bytes(b"synthetic fixture only\n")
        cfg[key] = str(path)
    Path(cfg["gnsspath"]).write_bytes(b"1 0 0 0 0 0 0 0 0 0 0 0 0 90 2.933193 1 1 1\n")
    hashes = {key:se.sha256_file(cfg[key]) for key in se.PROVIDER_KEYS}
    original = clean / "frozen.yaml"
    original.write_text(yaml.safe_dump(cfg))
    binary = code / "build/p13_v21_cpp/legsa_v23_port_core_demo"
    binary.parent.mkdir(parents=True)
    binary.write_text("synthetic identity only, never executed\n")
    binary.chmod(0o755)
    monkeypatch.setattr(se,"BINARY_SHA256",se.sha256_file(binary))
    replacement = scratch / "02_PROVIDER_TABLES/BY2/R5/gnss.txt"
    replacement.parent.mkdir(parents=True)
    replacement.write_bytes(Path(cfg["gnsspath"]).read_bytes().replace(b" 90 ",b" 91 "))
    contract = {"frozen":{"runtime_configs":{"BY2_F04":{"run_id":"RUN_00004","sha256":se.sha256_file(original)}},
        "gnss18_sha256":{"BY2":hashes["gnsspath"]},"executable":{"sha256":se.BINARY_SHA256}}}
    args = dict(sequence=sequence,contract=contract,frozen_config_path=original,
        expected_config_sha256=se.sha256_file(original),frozen_provider_hashes=hashes,
        prepared_gnss={"path":str(replacement),"sha256":se.sha256_file(replacement),"byte_gate":{"passed":True}},
        output_root=scratch/"03_NATIVE/BY2/F04/R5",scratch_root=scratch,code_commit="f"*40,
        slot_identity={"run_id":"BY2__F04__R5","sequence_id":"BY2","configuration_id":"F04","variant":"R5"},
        launch_ledger=scratch/"NATIVE_LEDGER.jsonl",allowed_run_ids={"BY2__F04__R5"})
    return args,cfg

def _synthetic_outputs(command, speed=0.):
    root = Path(command[command.index("--output-dir") + 1])
    config = yaml.safe_load(Path(command[command.index("--config") + 1]).read_text())
    rows = _base_rows()
    rows[1][5] = speed
    _nav(root / "KF_GINS_Navresult.nav", rows)
    (root / "KF_GINS_STD.txt").write_text("1 " + "0 " * 9 + "\n1.5 " + "0 " * 9 + "\n")
    native = {key: config[key] for key in ("run_id", "stage_id", "protocol_id", "case_id", "algorithm_id", "data_mode")}
    native.update({target: config[key] for key, target in se.CONFIG_FLAG_TO_MANIFEST.items()})
    native.update(se.FLAGS, phase=config["stage_id"], port_role=config["runtime_role"])
    enabled = se._enabled_inputs(config)
    native["actual_solver_input_paths"] = {role: config[key] for role, (key, _) in enabled.items()}
    native["actual_solver_input_roles"] = {role: purpose for role, (_, purpose) in enabled.items()}
    (root / "RUN_MANIFEST.json").write_text(json.dumps(native))
    (root / "NATIVE_OPENAT.strace").write_text("synthetic mocked log; no executable invocation\n")
    return root


@pytest.mark.parametrize("mode,status",[("complete","COMPLETED"),("diverged","ALGORITHM_FAILURE_DIVERGED"),
    ("nonzero","UNAVAILABLE_NATIVE_PROCESS_FAILED"),("timeout","UNAVAILABLE_NATIVE_PROCESS_FAILED"),
    ("std_misaligned","UNAVAILABLE_NATIVE_OUTPUT_INVALID")])
def test_native_mock_outputs_sealed_and_failsoft_without_retry(tmp_path,monkeypatch,mode,status):
    args,cfg = native_fixture(tmp_path,monkeypatch)
    calls=[]
    def fake(command,**kwargs):
        calls.append(command)
        root=_synthetic_outputs(command,51. if mode=="diverged" else 0.)
        if mode=="std_misaligned":
            (root/"KF_GINS_STD.txt").write_text("2 " + "0 "*9 + "\n")
        if mode=="timeout":
            raise RuntimeError("synthetic timeout")
        return SimpleNamespace(returncode=1 if mode=="nonzero" else 0,stdout="synthetic",stderr="")
    monkeypatch.setattr(se,"run_process_group",fake)
    monkeypatch.setattr(se,"audit_native_access",lambda *a:{"passed":True,"trace_open_count":0})
    result=se.run_native(**args)
    assert result["status"]==status and len(calls)==1
    assert result["native_run_id_retained"]=="RUN_00004"
    assert result["run_id"]=="BY2__F04__R5" and result["trace_open_count"]==0
    assert result["native_summary"]["sha256"]==se.sha256_file(result["native_summary"]["path"])
    assert result["evaluator_invocation_count"]==0
    assert yaml.safe_load((args["output_root"]/"T5A_RUNTIME_CONFIG.yaml").read_text())["outputpath"]==cfg["outputpath"]
    with pytest.raises(FileExistsError,match="no previous attempt"):
        se.run_native(**args)
    assert len(calls)==1


@pytest.mark.parametrize("mode",["input_drift","native_identity","access_violation"])
def test_native_identity_access_failure_hard_even_when_process_nonzero(tmp_path,monkeypatch,mode):
    args,cfg = native_fixture(tmp_path,monkeypatch)
    def fake(command,**kwargs):
        root=_synthetic_outputs(command)
        if mode=="input_drift":
            Path(cfg["imupath"]).write_text("synthetic mutation")
        if mode=="native_identity":
            manifest=json.loads((root/"RUN_MANIFEST.json").read_text())
            manifest["run_id"]="WRONG"
            (root/"RUN_MANIFEST.json").write_text(json.dumps(manifest))
        return SimpleNamespace(returncode=1,stdout="",stderr="")
    monkeypatch.setattr(se,"run_process_group",fake)
    monkeypatch.setattr(se,"audit_native_access",lambda *a:{"passed":mode!="access_violation",
        "violation_detected":mode=="access_violation","trace_open_count":0})
    with pytest.raises(RuntimeError,match="HARD_STOP"):
        se.run_native(**args)
    assert (args["output_root"]/"HARD_STOP.json").exists()
    assert (args["output_root"]/"T5A_NATIVE_SUMMARY.json").exists() == (mode == "access_violation")


@pytest.mark.parametrize("mode", ["missing", "malformed", "incomplete"])
@pytest.mark.parametrize("returncode", [0, 1])
def test_native_unknown_access_is_sealed_hard_stop_even_when_process_fails(tmp_path, monkeypatch, mode, returncode):
    args, _ = native_fixture(tmp_path, monkeypatch)
    def fake(command, **kwargs):
        root = _synthetic_outputs(command)
        if mode == "missing":
            (root / "NATIVE_OPENAT.strace").unlink()
        return SimpleNamespace(returncode=returncode, stdout="synthetic", stderr="")
    def audit(*args):
        if mode == "malformed":
            raise ValueError("synthetic malformed strace")
        return {"passed": False, "violation_detected": False,
                "status": "UNAVAILABLE_ACCESS_AUDIT", "trace_open_count": "UNAVAILABLE"}
    monkeypatch.setattr(se, "run_process_group", fake)
    monkeypatch.setattr(se, "audit_native_access", audit)
    with pytest.raises(RuntimeError, match="HARD_STOP_T5A_NATIVE_ACCESS_AUDIT"):
        se.run_native(**args)
    summary = json.loads((args["output_root"] / "T5A_NATIVE_SUMMARY.json").read_text())
    assert summary["status"] == "HARD_STOP"
    assert summary["trace_open_count"] == "UNAVAILABLE"
    assert summary["native_invocation_count"] == 1
    assert summary["evaluator_invocation_count"] == 0
    assert (args["output_root"] / "OUTPUT_SEAL.json").is_file()
    assert len(args["launch_ledger"].read_text().splitlines()) == 1
