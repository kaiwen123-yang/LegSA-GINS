"""Controller-only synthetic fixtures: no native/evaluator/Git/raw/trace execution."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from legsa_gins.paper_rebuild.hext import t5bc_execution as c
from legsa_gins.paper_rebuild.hext import t5bc_runtime as rt


FREEZE = "b"*40
NAV = b"% synthetic unit fixture only\n0 1.000000 30 120 10 0 0 0 0 0 90\n0 1.050000 30 120 10 0 0 0 0 0 91\n0 1.100000 30 120 10 0 0 0 0 0 92\n"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    code, clean, scratch = (tmp_path/name for name in ("code", "clean", rt.STAGE))
    for path in (code, clean, scratch): path.mkdir()
    def make(path, payload=b"synthetic fixture only\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return c._reference(path)
    source = code/"synthetic_frozen_source.py"
    make(source)
    monkeypatch.setattr(c, "_source_files", lambda: {source})
    contexts = {seq: SimpleNamespace(sequence_id=seq, code_root=code, clean_root=clean,
        raw_root=tmp_path/"NEVER_READ_RAW", trace=tmp_path/"NEVER_READ_RAW"/(seq+"_trace.csv"),
        trace_sha256="a"*64, base_time=1., window=(1., 2.)) for seq in ("BY2", "BY2H", "BY2O")}
    executable = make(code/"frozen_binary")
    candidate = make(code/"candidate_binary", b"synthetic candidate binary never invoked\n")
    evaluator = make(code/"evaluator.py")
    providers = {key: make(clean/key) for key in rt.PROVIDER_KEYS}
    cfg, echo, r5 = (make(clean/name) for name in ("config.yaml", "echo.json", "r5.gnss"))
    runs = {}
    slots = [(seq, cfg_id, variant, None) for seq in contexts for variant in ("R5W", "R5SIGMA", "B3")
             for cfg_id in (("F02", "A04", "F04") if variant == "B3" else ("F04",))]
    cases = ["C00_clean_normal"]+[f"D{i:02}_seed_00" for i in range(1,61)]
    slots += [("BY2", "F04", variant, case) for case in cases for variant in ("R5", "R5W", "R5SIGMA", "B3")]
    slots += [("BY2", cfg_id, "IDENTITY", None) for cfg_id in ("F02", "F04")]
    for seq, cfg_id, variant, case in slots:
        run_id = "__".join((seq, cfg_id, variant)) + ("__" + case if case else "")
        context = contexts[seq]
        spec = dict(run_id=run_id, sequence_id=seq, configuration_id=cfg_id, variant=variant, subset_case_id=case,
            frozen_config=cfg, frozen_echo=echo, frozen_providers=providers, r5_reference=r5,
            raw_source_hashes={str(context.raw_root/(seq+"_observations.csv")): "c"*64},
            evaluation={"window": list(context.window), "base_time": context.base_time,
                        "trace": {"path": str(context.trace), "sha256": context.trace_sha256}})
        spec["output_relpath"] = rt._native_relative(spec)
        runs[run_id] = spec
    identity_ids = [key for key, spec in runs.items() if spec["variant"] == "IDENTITY"]
    sample = clean/"synthetic_native.nav"; sample.write_bytes(NAV)
    comparators = {}
    comparator_hashes = {}
    for run_id in identity_ids:
        path = clean/run_id/"NAV_10HZ.csv.gz"; path.parent.mkdir()
        c.storage.thin_nav(sample, path)
        comparators[run_id] = c._reference(path)
        comparator_hashes["BY2_"+runs[run_id]["configuration_id"]] = comparators[run_id]["sha256"]
    figures = {f"FIG{i:02}": [make(clean/"figures"/f"FIG{i:02}.png")] for i in range(28)}
    render = make(clean/"figures/RENDER_MANIFEST.json")
    contract = {"task": "T5bc", "stage_id": rt.STAGE, "execution_ready": True, "preregistered": True,
        "code_freeze": FREEZE, "budget": {"subset_N": 61, "matrix_native": 259, "identity_native": 2,
            "matrix_evaluator": 518, "identity_evaluator": 0}, "matrix": {"subset": {"case_ids": cases}},
        "registered_runs": runs, "registered_evaluator_ids": [key+"__"+version for key,spec in runs.items()
            if spec["variant"] != "IDENTITY" for version in ("v3", "v2")],
        "frozen": {"executable": executable, "evaluator_sha256": evaluator["sha256"],
                   "identity_nav_10hz_sha256": comparator_hashes}, "candidate": candidate,
        "execution_control": {"identity_comparators": comparators, "frozen_figures": figures,
                              "render_manifest": render, "extra_frozen_pins": {}}}
    receipt = {"status": "PASS_CODE_FREEZE_PUSHED", "code_freeze": FREEZE, "head_commit": FREEZE,
        "remote_commit": FREEZE, "tracked_worktree_clean": True, "resolved_contract_sha256": c._digest(contract), "scientific_contract_sha256": rt.scientific_contract_sha256(contract),
        "source_sha256": {source.name: c._reference(source)["sha256"]}}
    calls, behavior = [], {}
    def fake_native(context, **kwargs):
        spec, root = kwargs["run_spec"], Path(kwargs["output_root"])
        calls.append(("native", spec["run_id"]))
        if spec["variant"] != "IDENTITY":
            gate = c._read(scratch/"02_IDENTITY_GATE/IDENTITY_GATE.json")
            assert gate["status"] == "PASS_BOTH_IDENTITIES" and len(gate["identities"]) == 2
        root.mkdir(parents=True, exist_ok=False)
        allowed, budgets = rt.validate_registration(contract, code_commit=FREEZE)
        kind = "identity_native" if spec["variant"] == "IDENTITY" else "matrix_native"
        entry = rt.reserve_slot(kwargs["launch_ledger"], spec["run_id"], allowed[kind],
                                kind=kind, budget=budgets[kind], contract_sha256=rt.scientific_contract_sha256(contract))
        rt._write(root/"LAUNCH_RESERVATION.json", entry)
        nav = root/"KF_GINS_Navresult.nav"
        nav.write_bytes(NAV.replace(b"0 0 90", b"0 0 95") if behavior.get("identity_mismatch") and spec["variant"] == "IDENTITY" else NAV)
        std = root/"KF_GINS_STD.txt"; std.write_bytes(b"synthetic same-run STD fixture\n")
        status = behavior.get("native_status", "ALGORITHM_FAILURE_DIVERGED") if behavior.get("diverged_run") == spec["run_id"] else "COMPLETED"
        record = {**{key:spec[key] for key in rt.IDENTITY_KEYS}, "code_commit": FREEZE,
            "config_hash": spec["frozen_config"]["sha256"],
            "contract_sha256": rt.scientific_contract_sha256(contract), "run_spec_sha256": c._digest(spec), "status": status, "trace_open_count": 0,
            "failure_classification": status if status != "COMPLETED" else "NONE",
            "input_identities": {"binary": candidate if spec["variant"] in ("B3", "IDENTITY") else executable},
            "nav_path": str(nav), "nav_sha256": rt.sha256_file(nav), "std_path": str(std), "std_sha256": rt.sha256_file(std),
            "effective_echo_gate": {"passed": True, "legacy_static_field_count": 211},
            "data_mode": "synthetic", "synthetic_data_used": True, "semisynthetic_data_used": False,
            "controlled_degradation_applied": False, "original_native_config_data_roles": {"data_mode": "synthetic"},
            "raw_source_hashes": spec["raw_source_hashes"],
            "provider_hashes": {key: ref["sha256"] for key, ref in providers.items()}, **rt.PROVENANCE_FLAGS}
        return rt._seal(root, record, filename="T5BC_NATIVE_SUMMARY.json")
    def fake_evaluate(context, evaluator_path, **kwargs):
        if behavior.pop("interrupt_before_first_eval", False):
            raise KeyboardInterrupt("synthetic process interruption before any evaluator reservation")
        spec, version = kwargs["run_spec"], kwargs["version"]
        run_id = spec["run_id"]+"__"+version
        calls.append(("evaluator", run_id))
        root = Path(kwargs["output_root"]); root.mkdir(parents=True, exist_ok=False)
        allowed, budgets = rt.validate_registration(contract, code_commit=FREEZE)
        entry = rt.reserve_slot(kwargs["launch_ledger"], run_id, allowed["evaluator"], kind="evaluator",
            budget=budgets["evaluator"], contract_sha256=rt.scientific_contract_sha256(contract))
        rt._write(root/"LAUNCH_RESERVATION.json", entry)
        record = {"run_id": run_id, "code_commit": FREEZE, "status": "COMPLETED",
                  "native_summary": kwargs["native_summary"]["native_summary"], "evaluation_invoked": True,
                  "audit": {"trace_open_count": 1}}
        return rt._seal(root, record, filename="T5BC_EVALUATION_SUMMARY.json")
    monkeypatch.setattr(rt, "run_native", fake_native)
    monkeypatch.setattr(rt, "evaluate_native", fake_evaluate)
    args = dict(contract=contract, contexts=contexts, evaluator=evaluator, scratch_root=scratch,
                archive_root=clean/"stages"/rt.STAGE, code_freeze_receipt=receipt)
    return SimpleNamespace(args=args, contract=contract, receipt=receipt, scratch=scratch,
        calls=calls, behavior=behavior, contexts=contexts, archive=args["archive_root"])


def test_draft_and_stale_git_receipt_fail_before_io(setup, monkeypatch):
    setup.contract["execution_ready"] = False
    monkeypatch.setattr(c, "_protected_pins", lambda *_: pytest.fail("draft I/O forbidden"))
    with pytest.raises(PermissionError, match="DRAFT_NOT_AUTHORIZED"):
        c.execute_registered(**setup.args)
    assert not (setup.scratch/"09_HANDOFF").exists() and not setup.calls
    setup.contract["execution_ready"] = True
    setup.receipt["remote_commit"] = "0"*40
    with pytest.raises(PermissionError, match="GIT_FREEZE_RECEIPT"):
        c.execute_registered(**setup.args)


def test_two_identity_gates_precede_matrix_and_full_resume_is_read_only(setup):
    c.execute_identities(**setup.args)
    result = c.execute_registered(**setup.args)
    assert result["budget_reserved"] == {"identity_native": 2, "matrix_native": 259, "evaluator": 518}
    assert result["trace_open_count_native"] == 0 and result["trace_open_count_evaluator"] == 518
    assert all(run_id.endswith("IDENTITY") for _,run_id in setup.calls[:2])
    assert len(setup.calls) == 779
    assert set(result["checkpoints"]) == {seq+"_"+label for seq in ("BY2","BY2H","BY2O") for label in ("PRE","POST")}
    before = c._inventory(setup.scratch)
    resumed = c.execute_registered(**setup.args)
    assert resumed == result and c._inventory(setup.scratch) == before and len(setup.calls) == 779
    assert not any(context.trace.exists() for context in setup.contexts.values())


def test_identity_mismatch_blocks_every_matrix_and_persists_hard_stop(setup):
    setup.behavior["identity_mismatch"] = True
    with pytest.raises(RuntimeError, match="SCALAR_OFF_NAV_10HZ_BYTE_IDENTITY"):
        c.execute_identities(**setup.args)
    assert len(setup.calls) == 1 and setup.calls[0][1].endswith("IDENTITY")
    assert (setup.scratch/"09_HANDOFF/EXECUTION/CONTROLLER_HARD_STOP.json").exists()
    with pytest.raises(RuntimeError, match="AUTOMATIC_CONTINUATION_FORBIDDEN"):
        c.execute_identities(**setup.args)
    assert len(setup.calls) == 1


def test_resume_completed_native_after_process_interruption_never_reruns_it(setup):
    setup.behavior["interrupt_before_first_eval"] = True
    c.execute_identities(**setup.args)
    with pytest.raises(KeyboardInterrupt): c.execute_registered(**setup.args)
    assert len(setup.calls) == 3
    assert not (setup.scratch/"09_HANDOFF/EXECUTION/CONTROLLER_HARD_STOP.json").exists()
    c.execute_identities(**setup.args)
    result = c.execute_registered(**setup.args)
    assert result["status"] == "COMPLETE_REGISTERED_EXECUTION"
    natives = [run_id for role,run_id in setup.calls if role == "native"]
    assert len(natives) == len(set(natives)) == 261


@pytest.mark.parametrize("native_status", ["ALGORITHM_FAILURE_DIVERGED", "UNAVAILABLE_NATIVE_PROCESS_FAILED"])
def test_denied_native_keeps_two_uninvoked_eval_terminals_and_budget_actual(setup, native_status):
    setup.behavior["diverged_run"] = "BY2__F04__B3"
    setup.behavior["native_status"] = native_status
    c.execute_identities(**setup.args)
    result = c.execute_registered(**setup.args)
    assert result["budget_reserved"]["evaluator"] == 516
    assert len(result["evaluation_terminals"]) == 518
    skipped = c._read(result["evaluation_terminals"]["BY2__F04__B3__v3"]["path"])
    assert skipped["evaluation_invoked"] is False and skipped["row"]["metrics_admitted"] is False
    from legsa_gins.paper_rebuild.hext import t5bc_reporting
    for version in ("v3", "v2"):
        payload = c._read(result["evaluation_terminals"]["BY2__F04__B3__"+version]["path"])
        assert payload["code_commit"] == payload["row"]["code_commit"] == FREEZE
        assert payload["config_hash"] == payload["row"]["config_hash"] == setup.contract["registered_runs"]["BY2__F04__B3"]["frozen_config"]["sha256"]
        assert payload["row"]["evaluator_contract"] == "evaluator_contract_"+version
        row = t5bc_reporting._candidate(payload, sequence="BY2", profile="F04", variant="B3",
                                        version=version, data_mode="synthetic")
        expected = "NOT_RUN_ALGORITHM_FAILURE" if native_status == "ALGORITHM_FAILURE_DIVERGED" else "NOT_RUN_NATIVE_UNAVAILABLE"
        assert row["evaluation_status"] == expected and row["failure_classification"] == native_status
        assert payload["row"]["reason"] == native_status


@pytest.mark.parametrize("mode", ["terminal", "archive", "figure"])
def test_resume_rechecks_every_hash_and_never_overwrites_evidence(setup, mode):
    c.execute_identities(**setup.args)
    result = c.execute_registered(**setup.args)
    if mode == "terminal":
        path = setup.scratch/"02_IDENTITY_GATE/BY2/F02/KF_GINS_Navresult.nav"
    elif mode == "archive":
        path = setup.archive/"02_IDENTITY_GATE/BY2/F02/KF_GINS_Navresult.nav"
    else:
        path = Path(setup.contract["execution_control"]["frozen_figures"]["FIG00"][0]["path"])
    path.write_bytes(b"synthetic tampering test\n")
    with pytest.raises(RuntimeError, match="HARD_STOP"):
        c.execute_registered(**setup.args)
    assert len(setup.calls) == 779 and path.read_bytes() == b"synthetic tampering test\n"


def test_partial_archive_never_repairs_or_overwrites(tmp_path):
    source, dest = tmp_path/"source", tmp_path/"dest"
    source.mkdir(); dest.mkdir()
    (source/"a").write_bytes(b"original")
    (dest/"a").write_bytes(b"partial")
    with pytest.raises(RuntimeError, match="ARCHIVE_BYTES_OR_MEMBER_SET"):
        c.archive_tree_once(source, dest)
    assert (dest/"a").read_bytes() == b"partial"


def test_identity_gate_cannot_be_reused_with_changed_candidate_contract(setup):
    c.execute_identities(**setup.args)
    c.execute_registered(**setup.args)
    setup.contract["candidate"]["sha256"] = "0"*64
    setup.receipt["resolved_contract_sha256"] = c._digest(setup.contract)
    setup.receipt["scientific_contract_sha256"] = rt.scientific_contract_sha256(setup.contract)
    with pytest.raises(RuntimeError, match="RECEIPT_CHANGED"):
        c.execute_registered(**setup.args)
    assert len(setup.calls) == 779


def test_source_freeze_covers_indirect_modules_dynamic_resources_and_observer(monkeypatch):
    root = Path(c.__file__).resolve().parents[4]
    indirect = root/"src/legsa_gins/paper_rebuild/clean5_sequence/generation_audit.py"
    monkeypatch.setitem(sys.modules, "legsa_gins.synthetic_indirect_dependency", SimpleNamespace(__file__=str(indirect)))
    sources = c._source_files()
    assert indirect in sources
    assert Path(rt.canonical.__file__).resolve() in sources
    assert root/"src/legsa_gins/paper_rebuild/clean6_canonical_v2/resources.py" in sources
    assert root/"scripts/paper_rebuild/clean5_evaluator_observer/sitecustomize.py" in sources


def test_missing_indirect_source_pin_blocks_before_any_native(setup, monkeypatch):
    code = setup.contexts["BY2"].code_root
    monkeypatch.setattr(c, "_source_files", lambda: {
        code/"synthetic_frozen_source.py", code/"indirect_generation_audit.py"})
    with pytest.raises(RuntimeError, match="IMPORTED_SOURCE_NOT_IN_FREEZE_RECEIPT"):
        c.execute_identities(**setup.args)
    assert not setup.calls


def test_matrix_cannot_launch_identity_or_run_without_identity_phase(setup):
    with pytest.raises(PermissionError, match='BOTH_IDENTITIES_REQUIRED'):
        c.execute_registered(**setup.args)
    assert not setup.calls
    result=c.execute_identities(**setup.args)
    assert result['budget_reserved']=={'identity_native':2,'matrix_native':0,'evaluator':0}
    assert len(setup.calls)==2
    assert c.execute_identities(**setup.args)==result and len(setup.calls)==2


def test_identity_binding_allows_only_later_generated_digest_hydration(setup):
    spec=setup.contract['registered_runs']['BY2__F04__B3']
    spec['prepared_gnss']={'path':str(setup.scratch/'03_PROVIDER_TABLES/BY2/B3/disabled.gnss'),'sha256':None}
    setup.receipt['resolved_contract_sha256']=c._digest(setup.contract)
    setup.receipt['scientific_contract_sha256']=rt.scientific_contract_sha256(setup.contract)
    first=c.execute_identities(**setup.args)
    spec['prepared_gnss']['sha256']='a'*64
    setup.receipt['resolved_contract_sha256']=c._digest(setup.contract)
    assert rt.scientific_contract_sha256(setup.contract)==first['contract_sha256']
    setup.behavior["interrupt_before_first_eval"]=True
    with pytest.raises(KeyboardInterrupt): c.execute_registered(**setup.args)
    assert len(setup.calls)==3
    # The same identities are reused; no second identity native call is made.
    spec['prepared_gnss']['path'] += '.changed'
    setup.receipt['resolved_contract_sha256']=c._digest(setup.contract)
    with pytest.raises(PermissionError,match='GIT_FREEZE_RECEIPT'):
        c.execute_registered(**setup.args)
    assert len(setup.calls)==3


def test_archive_missing_member_can_be_copied_later_but_existing_bytes_never_changed(tmp_path,monkeypatch):
    source,dest=tmp_path/'source',tmp_path/'dest';source.mkdir()
    for i in range(200):(source/str(i)).write_bytes(b'synthetic immutable archive\n')
    original=Path.open
    def failing(path,*args,**kwargs):
        if path==dest/'199' and args and args[0]=='xb':raise OSError('synthetic archive I/O failure')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',failing)
    with pytest.raises(c.ArchivePending) as error:c.archive_tree_once(source,dest)
    assert error.value.report['failed_file_count']/error.value.report['attempted_file_count']==.005
    monkeypatch.setattr(Path,'open',original)
    before=(dest/'0').read_bytes()
    assert c.archive_tree_once(source,dest)['status']=='ARCHIVE_VERIFIED'
    assert (dest/'0').read_bytes()==before and c._inventory(source)==c._inventory(dest)


def test_archive_one_percent_applies_per_batch_not_cumulative_dilution(tmp_path,monkeypatch):
    audit=tmp_path/'audit';large=tmp_path/'large';large.mkdir()
    for i in range(200):(large/str(i)).write_bytes(b'previous good batch')
    assert c.archive_tree_bounded(large,tmp_path/'large_out',audit_root=audit)['status']=='ARCHIVE_VERIFIED'
    small=tmp_path/'small';small.mkdir();(small/'only').write_bytes(b'new small batch')
    original=Path.open
    def failing(path,*args,**kwargs):
        if path==tmp_path/'small_out/only' and args and args[0]=='xb':raise OSError('synthetic I/O')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',failing)
    with pytest.raises(RuntimeError,match='EXCEED_ONE_PERCENT'):
        c.archive_tree_bounded(small,tmp_path/'small_out',audit_root=audit)
    records=[c._read(path) for path in sorted(audit.glob('BATCH_*.json'))]
    assert records[-1]['batch_failure_fraction']==1.
    assert records[-1]['aggregate_failed_file_count']/records[-1]['aggregate_attempted_file_count']<.01
