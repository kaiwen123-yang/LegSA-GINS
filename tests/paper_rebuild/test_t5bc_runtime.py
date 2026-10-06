"""Synthetic fixtures and mocked subprocesses only: zero native/evaluator/trace calls."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from legsa_gins.paper_rebuild.hext import t5bc_runtime as r
from legsa_gins.paper_rebuild.hext.t5bc_config_fidelity import STATIC_ECHO_KEYS, GNSS_ROLE


COMMIT = "f" * 40
TABLE = b"1 30 120 10 1 1 1 0 0 0 1 1 1 90 2.933193 1 1 1\n1.5 30 120 10 1 1 1 0 0 0 1 1 1 91 2.933193 1 1 1\n"


def ref(path):
    return {"path": str(path), "sha256": sha256(Path(path).read_bytes()).hexdigest()}


def matrix(spec, *, n=61):
    runs = {}
    cases = ["C00_clean_normal"] + [f"D{i:02}_seed_00" for i in range(1, 61)]
    slots = [(seq, cfg, var, None) for seq in ("BY2", "BY2H", "BY2O")
             for var in ("R5W", "R5SIGMA", "B3")
             for cfg in (("F02", "A04", "F04") if var == "B3" else ("F04",))]
    slots += [("BY2", "F04", var, case) for case in cases for var in ("R5", "R5W", "R5SIGMA", "B3")]
    slots += [("BY2", cfg, "IDENTITY", None) for cfg in ("F02", "F04")]
    for seq, cfg, var, case in slots:
        item = deepcopy(spec)
        item.update(sequence_id=seq, configuration_id=cfg, variant=var, subset_case_id=case,
                    run_id="__".join((seq, cfg, var, case or "SEQUENCE")))
        semi = case not in (None, "C00_clean_normal")
        item["data_roles"] = {"data_mode": "semisynthetic" if semi else "real_clean" if case == "C00_clean_normal" else "real_raw",
                              "synthetic_data_used": False, "semisynthetic_data_used": semi}
        item["output_relpath"] = r._native_relative(item)
        runs[item["run_id"]] = item
    return {"task": "T5bc", "stage_id": r.STAGE, "code_freeze": COMMIT,
            "execution_ready": True, "preregistered": True,
            "budget": {"subset_N": 61, "matrix_native": 259, "identity_native": 2,
                       "matrix_evaluator": 518, "identity_evaluator": 0},
            "matrix": {"subset": {"case_ids": cases}}, "registered_runs": runs,
            "registered_evaluator_ids": [key+"__"+v for key, item in runs.items()
                                         if item["variant"] != "IDENTITY" for v in ("v3", "v2")]}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    clean, code, scratch = (tmp_path / name for name in ("clean", "code", r.STAGE))
    for path in (clean, code, scratch):
        path.mkdir()
    sequence = SimpleNamespace(sequence_id="BY2", code_root=code, clean_root=clean,
        raw_root=tmp_path/"never_read_raw", trace=tmp_path/"never_read_raw/trace.csv",
        trace_sha256="a"*64, window=(1., 2.), base_time=1772784000.)
    config = {"run_id": "FROZEN_RUN", "case_id": "C00_clean_normal", "data_mode": "synthetic_fixture_not_scientific_evidence",
              "synthetic_data_used": False, "semisynthetic_data_used": False,
              "outputpath": "/immutable/old/output", "enable_multi_state_qm": False,
              "enable_qa_fallback": False, "enable_raw_doppler": False,
              "enable_go2_roll_pitch_prior": False, "enable_go2_horizontal_velocity_prior": False}
    config.update(r.PROVENANCE_FLAGS)
    providers = {}
    for key in r.PROVIDER_KEYS:
        path = clean / key
        path.write_bytes(TABLE if key == "gnsspath" else b"synthetic fixture only\n")
        config[key] = str(path)
        providers[key] = ref(path)
    cfg = clean / "frozen.yaml"
    cfg.write_text(yaml.safe_dump(config))
    echo = {key: 0 for key in STATIC_ECHO_KEYS}
    echo.update(run_id=config["run_id"], data_mode=config["data_mode"], synthetic_data_used=False,
                semisynthetic_data_used=False)
    echo["actual_solver_input_paths"] = {"propagation_imu": config["imupath"], GNSS_ROLE: config["gnsspath"]}
    echo["actual_solver_input_roles"] = {"propagation_imu": "source_backed_propagation", GNSS_ROLE: "validity_gated_measurements"}
    manifest = clean / "RUN_MANIFEST.json"
    manifest.write_text(json.dumps(echo))
    executables = {}
    for role, directory in (("frozen", "p13_v21_cpp"), ("candidate", "t5bc_v3_candidate_cpp")):
        path = code / "build" / directory / "legsa_v23_port_core_demo"
        path.parent.mkdir(parents=True)
        path.write_text("synthetic binary identity only, never executed: " + role)
        path.chmod(0o755)
        executables[role] = ref(path)
    monkeypatch.setattr(r, "BINARY_SHA256", executables["frozen"]["sha256"])
    prepared = scratch / "03_PROVIDER_TABLES/weighted.gnss"
    prepared.parent.mkdir()
    prepared.write_bytes(TABLE.replace(b"2.933193", b"0.0"))
    reference = clean / "r5_reference.gnss"
    reference.write_bytes(TABLE)
    sidecar = scratch / "03_PROVIDER_TABLES/baseline.csv"
    sidecar.write_text("time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n1,0,-0.35,0,0,0.01,1\n1.5,0,-0.35,0,0,0.01,1\n")
    model = {"dual_antenna_measurement_model": "baseline3d", "baseline3d_path": str(sidecar),
             "baseline3d_length_m": .35, "baseline3d_k_b": 1.7}
    spec = {"frozen_config": ref(cfg), "frozen_echo": ref(manifest), "frozen_providers": providers,
            "raw_source_hashes": {str(sequence.raw_root/"observations.csv"): "b"*64},
            "prepared_gnss": ref(prepared), "r5_reference": ref(reference), "sidecar": ref(sidecar),
            "baseline3d": model, "baseline_median_m": .35,
            "evaluation": {"window": list(sequence.window), "base_time": sequence.base_time,
                           "trace": {"path": str(sequence.trace), "sha256": sequence.trace_sha256}}}
    raw_manifest = prepared.parent / "prepared_raw_manifest.json"
    raw_manifest.write_text(json.dumps({"source_sha256": providers["gnsspath"]["sha256"],
        "pinned_r5_source": ref(reference), "rows": [{"time_token": token, "itow_ms": i,
        "raw_yaw_token": yaw, "std_R5W_token": "0.0", "std_R5SIGMA_token": "1.5", "raw_valid": True,
        "b_n": 0., "b_e": -.35, "b_d": 0., "pAcc1": 0., "pAcc2": .01}
        for i,(token,yaw) in enumerate((("1","90"),("1.5","91")))]}))
    spec["prepared_raw_manifest"] = ref(raw_manifest)
    contract = matrix(spec)
    for variant, payload in (("R5", TABLE), ("R5SIGMA", TABLE.replace(b"2.933193", b"1.5")),
                             ("B3", b"".join(line.rsplit(b" ",1)[0]+b" 0\n" for line in TABLE.splitlines()))):
        path = prepared.parent / (variant + ".gnss")
        path.write_bytes(payload)
        for item in contract["registered_runs"].values():
            if item["variant"] == variant: item["prepared_gnss"] = ref(path)
    evaluator = code / "synthetic_evaluator.py"
    evaluator.write_text("# synthetic evaluator identity, never executed\n")
    monkeypatch.setattr(r, "EVALUATOR_SHA256", ref(evaluator)["sha256"])
    contract.update(frozen={"executable": executables["frozen"], "evaluator_sha256": r.EVALUATOR_SHA256},
                    candidate=executables["candidate"])
    calls = []
    def choose(variant="R5W", subset=False):
        key = "__".join(("BY2", "F04", variant, "C00_clean_normal" if variant == "R5" else "D01_seed_00" if subset else "SEQUENCE"))
        spec = contract["registered_runs"][key]
        return dict(sequence=sequence, contract=contract, run_spec=spec,
                    output_root=scratch/spec["output_relpath"], scratch_root=scratch, code_commit=COMMIT,
                    launch_ledger=scratch/"LAUNCH_LEDGERS"/(("identity_native" if variant == "IDENTITY" else "matrix_native")+".jsonl"))
    def fake_native(command, **kwargs):
        calls.append(command)
        root = Path(command[command.index("--output-dir")+1])
        copied = yaml.safe_load(Path(command[command.index("--config")+1]).read_text())
        output_echo = deepcopy(echo)
        output_echo["actual_solver_input_paths"][GNSS_ROLE] = copied["gnsspath"]
        if copied.get("dual_antenna_measurement_model") == "baseline3d":
            output_echo.update(model)
            output_echo["actual_solver_input_paths"][r.B3_ROLE] = model["baseline3d_path"]
            output_echo["actual_solver_input_roles"][r.B3_ROLE] = r.B3_PURPOSE
        (root/"RUN_MANIFEST.json").write_text(json.dumps(output_echo))
        (root/"KF_GINS_Navresult.nav").write_text("% synthetic mocked native\n0 1 30 120 10 0 0 0 0 0 90\n1 1.5 30 120 10 0 0 0 0 0 91\n")
        (root/"KF_GINS_STD.txt").write_text("1 .1 .1 .1 .1 .1 .1 .1 .1 .1\n1.5 .1 .1 .1 .1 .1 .1 .1 .1 .1\n")
        binary = command[command.index("--config")-1]
        opened = [command[command.index("--config")+1], copied["imupath"], copied["gnsspath"]]
        if "baseline3d_path" in copied:
            opened.append(copied["baseline3d_path"])
        log = '123 execve("'+binary+'", ["synthetic"], 0x0) = 0\n'
        log += "".join('123 openat(AT_FDCWD, '+json.dumps(path)+', O_RDONLY) = 3\n' for path in opened)
        (root/"NATIVE_OPENAT.strace").write_text(log)
        return SimpleNamespace(returncode=0, stdout="synthetic mocked subprocess only", stderr="")
    monkeypatch.setattr(r, "run_process_group", fake_native)
    return SimpleNamespace(choose=choose, contract=contract, sequence=sequence, scratch=scratch,
                           echo=echo, config=config, calls=calls, fake_native=fake_native, evaluator=evaluator)


def test_draft_rejected_before_any_pin_or_output(setup, monkeypatch):
    args = setup.choose()
    setup.contract["execution_ready"] = False
    monkeypatch.setattr(r, "_pin", lambda *_: pytest.fail("draft must not read any scientific file"))
    with pytest.raises(PermissionError, match="DRAFT_NOT_AUTHORIZED"):
        r.run_native(**args)
    assert not args["output_root"].exists() and not setup.calls


@pytest.mark.parametrize("mode", ["budget_bool", "budget_formula", "unselected_case", "extra_eval", "slot", "freeze"])
def test_exact_registration_and_integer_budgets(setup, mode):
    contract = deepcopy(setup.contract)
    if mode == "budget_bool": contract["budget"]["subset_N"] = True
    if mode == "budget_formula": contract["budget"]["matrix_native"] += 1
    if mode == "unselected_case": contract["matrix"]["subset"]["case_ids"] = ["D99_seed_00"]
    if mode == "extra_eval": contract["registered_evaluator_ids"].append("EXTRA__v3")
    if mode == "slot": next(iter(contract["registered_runs"].values()))["output_relpath"] = "05_NATIVE_SEQUENCES/other"
    if mode == "freeze": contract["code_freeze"] = "0"*40
    with pytest.raises(PermissionError):
        r.validate_registration(contract, code_commit=COMMIT)


def test_separate_durable_no_retry_ledgers_full_dynamic_budget(tmp_path):
    calls = []
    allowed = [f"run{i}" for i in range(24)]
    ledger = tmp_path/"matrix.jsonl"
    for name in allowed:
        calls.append(r.reserve_slot(ledger, name, allowed, kind="matrix_native", budget=24, contract_sha256="x"*64))
    assert calls[-1]["ordinal"] == 24
    with pytest.raises(RuntimeError, match="NO_RETRY"):
        r.reserve_slot(ledger, "run0", allowed, kind="matrix_native", budget=24, contract_sha256="x"*64)
    with pytest.raises(RuntimeError, match="SCOPE_OR_FREEZE"):
        r.reserve_slot(ledger, "run0", allowed, kind="identity_native", budget=24, contract_sha256="x"*64)
    assert len(ledger.read_text().splitlines()) == 24


@pytest.mark.parametrize("variant", ["R5", "R5W", "R5SIGMA", "B3", "IDENTITY"])
def test_native_variants_clone_and_seal_exactly_once(setup, variant):
    args = setup.choose(variant)
    frozen = Path(args["run_spec"]["frozen_config"]["path"]).read_bytes()
    result = r.run_native(**args)
    assert result["status"] == "COMPLETED" and result["trace_open_count"] == 0
    assert result["effective_echo_gate"]["legacy_static_field_count"] == 211
    assert len(setup.calls) == 1
    assert result["raw_source_hashes"] == args["run_spec"]["raw_source_hashes"]
    assert result["provider_hashes"]["imupath"] == args["run_spec"]["frozen_providers"]["imupath"]["sha256"]
    payload = (args["output_root"]/"T5BC_RUNTIME_CONFIG.yaml").read_bytes()
    if variant == "IDENTITY":
        assert payload == frozen and result["evaluator_status"] == "NOT_APPLICABLE_IDENTITY"
    elif variant == "B3":
        assert result["input_identities"]["config_byte_gate"]["existing_changed_line_count"] == 1
        assert result["effective_echo_gate"]["additional_model_field_count"] == 4
    else:
        assert yaml.safe_load(payload)["gnsspath"] == args["run_spec"]["prepared_gnss"]["path"]
    assert ref(Path(result["native_summary"]["path"])) == result["native_summary"]
    with pytest.raises(FileExistsError): r.run_native(**args)
    assert len(setup.calls) == 1


def test_non_yaw_and_std_validity_independently_checked(setup):
    args = setup.choose()
    prepared = Path(args["run_spec"]["prepared_gnss"]["path"])
    prepared.write_bytes(prepared.read_bytes().replace(b"30 120", b"31 120"))
    args["run_spec"]["prepared_gnss"] = ref(prepared)
    with pytest.raises(RuntimeError, match="PROVIDER_BYTE_OR_NUMERIC_GATE"): r.run_native(**args)
    assert not setup.calls and not args["output_root"].exists()


@pytest.mark.parametrize("std", ["-1", "nan", "inf"])
def test_no_clipping_of_invalid_scalar_std(std):
    with pytest.raises(RuntimeError, match="HARD_STOP_T5BC_PROVIDER"):
        r.validate_scalar_table(TABLE, TABLE.replace(b"2.933193", std.encode()), TABLE)
    assert r.validate_scalar_table(TABLE, TABLE.replace(b"2.933193", b"0"), TABLE)["std_clipping_used"] is False


@pytest.mark.parametrize("mode", ["missing_log", "echo", "provider_mutation", "forbidden_read"])
def test_consumed_native_hardstop_always_seals(setup, monkeypatch, mode):
    args = setup.choose()
    def fake(command, **kwargs):
        result = setup.fake_native(command, **kwargs)
        root = args["output_root"]
        if mode == "missing_log": (root/"NATIVE_OPENAT.strace").unlink()
        if mode == "echo":
            echo = json.loads((root/"RUN_MANIFEST.json").read_text()); echo["yaw_std_min_deg"] = 999
            (root/"RUN_MANIFEST.json").write_text(json.dumps(echo))
        if mode == "provider_mutation": Path(setup.config["imupath"]).write_text("synthetic drift")
        if mode == "forbidden_read":
            with (root/"NATIVE_OPENAT.strace").open("a") as stream:
                stream.write('123 openat(AT_FDCWD, "/unregistered/input.txt", O_RDONLY) = 3\n')
        return result
    monkeypatch.setattr(r, "run_process_group", fake)
    with pytest.raises(RuntimeError, match="HARD_STOP"):
        r.run_native(**args)
    summary = json.loads((args["output_root"]/"T5BC_NATIVE_SUMMARY.json").read_text())
    assert summary["status"] == "HARD_STOP" and summary["native_invocation_count"] == 1
    assert (args["output_root"]/"OUTPUT_SEAL.json").exists()
    assert len(args["launch_ledger"].read_text().splitlines()) == 1


@pytest.mark.parametrize("mode,status", [("nonzero", "HARD_STOP_UNCLASSIFIABLE_NATIVE_FAILURE"),
    ("diverged", "ALGORITHM_FAILURE_DIVERGED"), ("std", "UNAVAILABLE_NATIVE_OUTPUT_INVALID"),
    ("missing_enabled_nonzero", "HARD_STOP_UNCLASSIFIABLE_NATIVE_FAILURE")])
def test_native_failsoft_with_complete_access_only(setup, monkeypatch, mode, status):
    args = setup.choose()
    def fake(command, **kwargs):
        result = setup.fake_native(command, **kwargs)
        root = args["output_root"]
        if mode in ("nonzero", "missing_enabled_nonzero"): result.returncode = 1
        if mode == "missing_enabled_nonzero":
            log = root/"NATIVE_OPENAT.strace"
            log.write_text("\n".join(line for line in log.read_text().splitlines() if setup.config["imupath"] not in line)+"\n")
        if mode == "diverged":
            nav = root/"KF_GINS_Navresult.nav"
            nav.write_text(nav.read_text().replace("10 0 0 0", "10 51 0 0"))
        if mode == "std": (root/"KF_GINS_STD.txt").write_text("2 .1 .1 .1 .1 .1 .1 .1 .1 .1\n")
        return result
    monkeypatch.setattr(r, "run_process_group", fake)
    if status.startswith("HARD_STOP"):
        with pytest.raises(RuntimeError,match=status):r.run_native(**args)
        assert json.loads((args["output_root"]/"T5BC_NATIVE_SUMMARY.json").read_text())["status"]=="HARD_STOP"
    else:
        assert r.run_native(**args)["status"] == status
    assert len(setup.calls) == 1


def test_subset_semisynthetic_role_is_inherited_exactly(setup, monkeypatch):
    args = setup.choose(subset=True)
    path = Path(args["run_spec"]["frozen_config"]["path"])
    config = yaml.safe_load(path.read_text()); config["semisynthetic_data_used"] = True
    config["case_id"] = args["run_spec"]["subset_case_id"]
    path.write_text(yaml.safe_dump(config))
    args["run_spec"]["frozen_config"] = ref(path)
    echo_path = Path(args["run_spec"]["frozen_echo"]["path"])
    setup.echo["semisynthetic_data_used"] = True
    echo_path.write_text(json.dumps(setup.echo))
    args["run_spec"]["frozen_echo"] = ref(echo_path)
    result = r.run_native(**args)
    assert result["semisynthetic_data_used"] is True and result["synthetic_data_used"] is False


def test_wrong_subset_case_id_is_rejected_before_launch(setup):
    args = setup.choose(subset=True)
    with pytest.raises(RuntimeError, match="FROZEN_SUBSET_CASE_ID"):
        r.run_native(**args)
    assert not setup.calls and not args["output_root"].exists()


def test_raw_reference_is_rejected_before_opening_payload(setup, monkeypatch):
    args = setup.choose()
    args["run_spec"]["frozen_config"]["path"] = str(setup.sequence.raw_root/"forbidden.yaml")
    monkeypatch.setattr(r, "_pin", lambda *_: pytest.fail("must not open raw reference"))
    with pytest.raises(RuntimeError, match="OUTSIDE_CLEAN_ROOT"):
        r.run_native(**args)
    assert not setup.calls and not args["output_root"].exists()


def test_changed_provider_hash_is_prelaunch_hardstop(setup):
    args = setup.choose()
    Path(setup.config["go2_attitude_prior_path"]).write_text("synthetic changed disabled provider")
    with pytest.raises(RuntimeError, match="INPUT_IDENTITY"):
        r.run_native(**args)
    assert not setup.calls and not args["output_root"].exists()


def evaluation_args(setup, native, version="v2"):
    spec = setup.choose()["run_spec"]
    return dict(sequence=setup.sequence, evaluator=setup.evaluator, contract=setup.contract,
                run_spec=spec, native_summary=native, version=version,
                output_root=setup.scratch/"06_EVAL"/version/spec["run_id"], scratch_root=setup.scratch,
                code_commit=COMMIT, launch_ledger=setup.scratch/"LAUNCH_LEDGERS/evaluator.jsonl")


def fake_eval(setup, calls, *, consistent=True, audit_passed=True):
    def fake(**kwargs):
        calls.append(kwargs)
        root = kwargs["outdir"]; root.mkdir(parents=True)
        errors = pd.DataFrame({"time": [1., 1.5], "err_n_m": [1., 1.], "err_e_m": [2., 2.],
            "err_u_m": [3., 3.], "horizontal_err_m": [np.sqrt(5.)]*2, "position_3d_err_m": [np.sqrt(14.)]*2,
            "roll_err_deg": [0., 0.], "pitch_err_deg": [0., 0.], "yaw_err_deg": [-1., 1.]})
        errors.to_csv(root/"error_series.csv", index=False)
        return {"outdir": str(root), "runtime_seconds": .1,
                "audit": {"passed": audit_passed, "exit_code": 0, "trace_open_count": 1,
                          "bag_open_count": 0, "fpl_open_count": 0, "write_scope": {"pass": True}},
                "capture": {"trace_sha256": setup.sequence.trace_sha256, "trace_handle_hash_count": 1,
                            "selected_columns": r.SELECTED_COLUMNS, "reference_epoch_count": 20,
                            "consistency": {"passed": consistent}}}
    return fake


@pytest.mark.parametrize("version", ["v2", "v3"])
def test_evaluate_sealed_same_native_std_and_version_transform(setup, monkeypatch, version):
    native = r.run_native(**setup.choose())
    calls = []
    monkeypatch.setattr(r, "evaluate", fake_eval(setup, calls))
    args = evaluation_args(setup, native, version)
    result = r.evaluate_native(**args)
    assert result["status"] == "COMPLETED" and result["row"]["metrics_admitted"] is True
    assert result["row"]["yaw_rmse_deg"] == pytest.approx(1.)
    assert result["row"]["code_commit"] == result["code_commit"] == COMMIT
    assert result["row"]["config_hash"] == result["config_hash"] == native["config_hash"]
    assert result["raw_source_hashes"] == result["row"]["raw_source_hashes"] == native["raw_source_hashes"]
    assert result["provider_hashes"] == result["row"]["provider_hashes"] == native["provider_hashes"]
    assert all(result[key] == result["row"][key] == value for key, value in r.PROVENANCE_FLAGS.items())
    assert len(calls) == 1 and calls[0]["std"] == Path(native["std_path"])
    assert calls[0]["consistency_policy"] == r.POLICY
    assert (calls[0]["nav"] == Path(native["nav_path"])) == (version == "v2")
    assert result["transform"]["changed_columns_zero_based"] == ([2, 3, 4] if version == "v3" else [])
    assert not setup.sequence.trace.exists()


def test_d12_unavailable_without_stale_metrics(setup, monkeypatch):
    native = r.run_native(**setup.choose()); calls = []
    monkeypatch.setattr(r, "evaluate", fake_eval(setup, calls, consistent=False))
    monkeypatch.setattr(r, "window_metrics", lambda *_: pytest.fail("metrics must not run"))
    result = r.evaluate_native(**evaluation_args(setup, native))
    assert result["status"] == "UNAVAILABLE_EVALUATION_FAILED"
    assert result["row"]["code_commit"] == COMMIT
    assert result["row"]["config_hash"] == native["config_hash"]
    assert result["row"]["metrics_admitted"] is False and "yaw_rmse_deg" not in result["row"]
    assert len(calls) == 1


def test_evaluator_access_failure_hard_sealed_and_no_retry(setup, monkeypatch):
    native = r.run_native(**setup.choose()); calls = []
    monkeypatch.setattr(r, "evaluate", fake_eval(setup, calls, audit_passed=False))
    args = evaluation_args(setup, native)
    with pytest.raises(RuntimeError, match="PROCESS_OR_ACCESS"):
        r.evaluate_native(**args)
    assert (args["output_root"]/"T5BC_EVALUATION_SUMMARY.json").exists()
    assert len(args["launch_ledger"].read_text().splitlines()) == 1
    with pytest.raises(FileExistsError): r.evaluate_native(**args)
    assert len(calls) == 1


def test_identity_cannot_consume_evaluation_slot(setup):
    args = setup.choose("IDENTITY")
    native = r.run_native(**args)
    eval_args = evaluation_args(setup, native)
    eval_args["run_spec"] = args["run_spec"]
    with pytest.raises(PermissionError, match="IDENTITY_EVALUATION_FORBIDDEN"):
        r.evaluate_native(**eval_args)
    assert not eval_args["launch_ledger"].exists()


def test_forged_cross_run_native_summary_fails_before_reservation(setup):
    native = r.run_native(**setup.choose())
    native["std_path"] = "/synthetic/other-run/STD"
    args = evaluation_args(setup, native)
    with pytest.raises(RuntimeError, match="SUMMARY_BINDING"):
        r.evaluate_native(**args)
    assert not args["output_root"].exists() and not args["launch_ledger"].exists()


def test_changed_contract_cannot_evaluate_previous_native(setup):
    native = r.run_native(**setup.choose())
    setup.contract["reviewer_regression_changed_contract"] = True
    args = evaluation_args(setup, native)
    with pytest.raises(RuntimeError, match="NATIVE_CONTRACT_BINDING"):
        r.evaluate_native(**args)
    assert not args["output_root"].exists() and not args["launch_ledger"].exists()


@pytest.mark.parametrize("field", ["receiver_imu_as_body_imu", "per_case_tuning", "old_runtime_input_count"])
def test_forbidden_provenance_stops_before_reservation(setup, field):
    args = setup.choose()
    path = Path(args["run_spec"]["frozen_config"]["path"])
    config = yaml.safe_load(path.read_text())
    config[field] = 1 if field == "old_runtime_input_count" else True
    path.write_text(yaml.safe_dump(config)); args["run_spec"]["frozen_config"] = ref(path)
    with pytest.raises(RuntimeError, match="FORBIDDEN_CONFIG_PROVENANCE"):
        r.run_native(**args)
    assert not setup.calls and not args["launch_ledger"].exists()


def test_raw_provenance_required_without_opening_raw_payload(setup):
    args = setup.choose(); args["run_spec"]["raw_source_hashes"] = {}
    with pytest.raises(RuntimeError, match="RAW_HASH_PROVENANCE_REQUIRED"):
        r.run_native(**args)
    assert not setup.calls and not args["launch_ledger"].exists()


def test_final_matrix_exact_259_native_518_eval_and_seed_zero_only(setup):
    allowed, budget = r.validate_registration(setup.contract, code_commit=COMMIT)
    assert budget == {'matrix_native': 259, 'identity_native': 2, 'evaluator': 518}
    specs = [setup.contract['registered_runs'][key] for key in allowed['matrix_native']]
    assert sum(row['subset_case_id'] is None for row in specs) == 15
    assert sum(row['subset_case_id'] is not None for row in specs) == 244
    assert not any(row['variant'] in ('R5W','R5SIGMA') and row['configuration_id']=='F02' for row in specs)


def test_generated_hash_binding_keeps_science_and_paths_immutable(setup):
    original = r.scientific_contract_sha256(setup.contract)
    changed = deepcopy(setup.contract)
    spec = changed['registered_runs'][setup.choose()['run_spec']['run_id']]
    for key in r.GENERATED_REFERENCE_KEYS: spec[key]['sha256'] = None
    assert r.scientific_contract_sha256(changed) == original
    spec['prepared_gnss']['path'] += '.different'
    assert r.scientific_contract_sha256(changed) != original


def test_irregular_subset_time_is_invalid_without_nearest_reference_matching():
    frozen = TABLE.replace(b'1.5 30', b'1.503 30')
    candidate = frozen.splitlines(keepends=True)
    candidate[1] = candidate[1].rsplit(b' ',1)[0]+b' 0\n'
    candidate = b''.join(candidate)
    manifest = {'source_sha256':sha256(frozen).hexdigest(), 'rows':[
        {'time_token':'1','raw_valid':True,'raw_yaw_token':'90','std_R5W_token':'2.933193'},
        {'time_token':'1.503','raw_valid':False,'raw_yaw_token':None,'std_R5W_token':None}]}
    assert r.validate_scalar_table(frozen, candidate, TABLE, manifest=manifest)['exact_time_manifest']
    manifest['rows'][1]['raw_valid'] = True
    with pytest.raises(RuntimeError, match='VALIDITY'):
        r.validate_scalar_table(frozen, candidate, TABLE, manifest=manifest)


def test_subset_outer_roles_do_not_mutate_native_frozen_metadata(setup):
    args = setup.choose(subset=True)
    path = Path(args['run_spec']['frozen_config']['path'])
    payload = path.read_bytes().replace(b'C00_clean_normal', b'D01_seed_00')
    path.write_bytes(payload); args['run_spec']['frozen_config'] = ref(path)
    result = r.run_native(**args)
    assert result['data_mode'] == 'semisynthetic' and result['semisynthetic_data_used'] is True
    assert result['original_native_config_data_roles']['semisynthetic_data_used'] is False
    copied = yaml.safe_load((args['output_root']/'T5BC_RUNTIME_CONFIG.yaml').read_bytes())
    assert copied['semisynthetic_data_used'] is False


def test_zero_yaw_input_class_requires_full_processing_and_exact_native_reason(tmp_path, monkeypatch):
    root=tmp_path
    imu=root/'imu'; imu.write_text('0 0\n1 0\n2 0\n')
    gnss=root/'gnss'; gnss.write_bytes(b''.join(line.rsplit(b' ',1)[0]+b' 0\n' for line in TABLE.splitlines()))
    (root/'PORT_RUNTIME_LOOP_TRACE.csv').write_text('loop_index,timestamp_after_process\n0,1\n1,2\n')
    (root/'PORT_GNSS_UPDATE_TRACE.csv').write_text('position_update,velocity_update,yaw_update,yaw_mode\n1,1,0,NONE\n')
    reason='FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch'
    (root/'stderr.log').write_text(reason+'\n')
    cfg={'imupath':str(imu),'gnsspath':str(gnss),'starttime':0,'endtime':2,'enable_dual_yaw':True}
    monkeypatch.setattr(r,'expected_counts',lambda *_: {'dual_yaw_attempt_count':0,'position_update_count':1,
        'receiver_velocity_update_count':1,'last_processed_imu_time':2})
    result=r.classify_heading_failure(root,cfg,variant='R5')
    assert result['passed'] and result['classification']=='ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT'
    (root/'stderr.log').write_text(reason+'\nANOTHER_ERROR\n')
    assert not r.classify_heading_failure(root,cfg,variant='R5')['passed']


def test_all_rejected_class_uses_frozen_positive_count_evidence(tmp_path, monkeypatch):
    root=tmp_path
    (root/'imu').write_text('0 0\n1 0\n2 0\n'); (root/'gnss').write_bytes(TABLE)
    (root/'PORT_RUNTIME_LOOP_TRACE.csv').write_text('loop_index,timestamp_after_process\n0,1\n1,2\n')
    (root/'PORT_GNSS_UPDATE_TRACE.csv').write_text('position_update,velocity_update,yaw_update,yaw_mode\n1,1,1,REJECT\n')
    (root/'stderr.log').write_text('FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch\n')
    cfg={'imupath':str(root/'imu'),'gnsspath':str(root/'gnss'),'starttime':0,'endtime':2,'enable_dual_yaw':True}
    monkeypatch.setattr(r,'expected_counts',lambda *_: {'dual_yaw_attempt_count':1,'position_update_count':1,
        'receiver_velocity_update_count':1,'last_processed_imu_time':2})
    result=r.classify_heading_failure(root,cfg,variant='R5')
    assert result['passed'] and result['classification']=='ALGORITHM_FAILURE_ALL_YAW_REJECTED'
    (root/'PORT_GNSS_UPDATE_TRACE.csv').write_text('position_update,velocity_update,yaw_update,yaw_mode\n1,1,1,NORMAL\n')
    assert not r.classify_heading_failure(root,cfg,variant='R5')['passed']


def test_b3_no_input_proof_reads_sidecar_not_zero_scalar_column(tmp_path,monkeypatch):
    root=tmp_path
    (root/'imu').write_text('0 0\n1 0\n2 0\n');(root/'gnss').write_bytes(TABLE)
    (root/'sidecar').write_text('time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n1,,,,,,0\n1.5,,,,,,0\n')
    (root/'PORT_RUNTIME_LOOP_TRACE.csv').write_text('loop_index,timestamp_after_process\n0,1\n1,2\n')
    (root/'PORT_GNSS_UPDATE_TRACE.csv').write_text('position_update,velocity_update,yaw_update,yaw_mode\n1,1,0,NONE\n')
    (root/'stderr.log').write_text('FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch\n')
    cfg={'imupath':str(root/'imu'),'gnsspath':str(root/'gnss'),'baseline3d_path':str(root/'sidecar'),
         'starttime':0,'endtime':2,'enable_dual_yaw':True}
    monkeypatch.setattr(r,'expected_counts',lambda *_:{'dual_yaw_attempt_count':0,'position_update_count':1,
        'receiver_velocity_update_count':1,'last_processed_imu_time':2})
    proof=r.classify_heading_failure(root,cfg,variant='B3')
    assert proof['passed'] and not proof['scalar_yaw_valid_used_for_b3_classification']
    assert proof['baseline3d_diagnostics_available'] is False and proof['sidecar_valid_count']==0
    (root/'sidecar').write_text('time,b_n,b_e,b_d,pAcc1,pAcc2,valid\n1,0,-.35,0,.01,.01,1\n1.5,,,,,,0\n')
    assert not r.classify_heading_failure(root,cfg,variant='B3')['passed']


def test_nonzero_native_with_proven_d8_divergence_is_algorithm_failure(setup,monkeypatch):
    args=setup.choose()
    def fake(command,**kwargs):
        result=setup.fake_native(command,**kwargs);result.returncode=1
        path=args['output_root']/'KF_GINS_Navresult.nav'
        path.write_text(path.read_text().replace('10 0 0 0','10 51 0 0'))
        return result
    monkeypatch.setattr(r,'run_process_group',fake)
    result=r.run_native(**args)
    assert result['status']=='ALGORITHM_FAILURE_DIVERGED' and result['bounded_gate']['passed'] is False
