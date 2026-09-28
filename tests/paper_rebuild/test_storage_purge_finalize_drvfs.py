"""Final ledger must prove the actual same-preflight chain and inherited B hashes."""
import importlib.util
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import storage_purge as base
from legsa_gins.paper_rebuild.storage_purge_dispatch import seal_receipt, DispatchRejected
from test_storage_purge_drvfs import world, fresh_ledger

spec = importlib.util.spec_from_file_location("drvfs_finalizer", Path(__file__).resolve().parents[2]
    / "scripts/paper_rebuild/storage_purge_finalize_drvfs.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def receipt_chain():
    binding = {"audit":"<CLEAN_ROOT>/storage_purge/20260911T010203Z", "rename_strategy":"drvfs_plain_rename_b_sha256.v1"}
    hashes = {key:"a"*64 for key in ("policy_sha256", "closure_sha256", "plan_sha256", "ledger_sha256")}
    snapshots = {}
    previous = None
    for phase, name, gates in zip(("preflight", "quarantine", "c5", "purge"), mod.RECEIPTS,
            (("IO_PROBE", "C1", "C2", "C3"), ("C4",), ("C5",), ("C1", "C2", "C3", "C4", "C5", "D"))):
        fields = dict(phase=phase, status="PASS", exit_code=0, preflight_id="unique",
                      binding=binding, control_hashes=hashes, gates={g:"PASS" for g in gates})
        if previous:
            fields.update(preflight_sha256=pre["receipt_sha256"],
                          preflight_literal_sha256=base._digest(snapshots[mod.RECEIPTS[0]]),
                          previous_receipt_sha256=previous["receipt_sha256"])
        receipt = seal_receipt(fields)
        if previous is None:
            pre = receipt
        snapshots[name] = base._json_bytes(receipt)
        previous = receipt
    return snapshots, hashes


def test_same_preflight_receipts_validate():
    snapshots, hashes = receipt_chain()
    assert len(mod.validate_receipts(snapshots, hashes)) == 4


@pytest.mark.parametrize("name,gate", [("GATE_PRE_MOVE.json", "IO_PROBE"), ("PURGE_RESULT.json", "D")])
def test_missing_probe_or_d_gate_is_rejected(name, gate):
    import json
    snapshots, hashes = receipt_chain()
    receipt = json.loads(snapshots[name])
    receipt["gates"].pop(gate)
    snapshots[name] = base._json_bytes(seal_receipt(receipt))
    with pytest.raises(DispatchRejected, match="required and reported gates"):
        mod.validate_receipts(snapshots, hashes)


@pytest.mark.parametrize("key", ["ledger_sha256", "plan_sha256", "policy_sha256", "closure_sha256"])
def test_actual_control_pin_substitution_fails(key):
    snapshots, hashes = receipt_chain()
    hashes[key] = "b"*64
    with pytest.raises(base.PurgeError, match="actual control bytes"):
        mod.validate_receipts(snapshots, hashes)


@pytest.mark.parametrize("field,value", [
    ("preflight_id", "stale"), ("preflight_sha256", "c"*64),
    ("previous_receipt_sha256", "c"*64), ("preflight_literal_sha256", "c"*64),
    ("status", "FAIL"), ("exit_code", 1), ("gates", {"C5":"FAIL"}),
])
def test_self_hashed_but_invalid_downstream_cannot_finalize(field, value):
    import json
    snapshots, hashes = receipt_chain()
    receipt = json.loads(snapshots["C5_RECEIPT.json"])
    receipt[field] = value
    snapshots["C5_RECEIPT.json"] = base._json_bytes(seal_receipt(receipt))
    with pytest.raises((base.PurgeError, DispatchRejected)):
        mod.validate_receipts(snapshots, hashes)


def history():
    row = dict(original_relative_path="stages/S/file.nav", sha256="a"*64, size_bytes=8)
    events = [dict(row, sequence=i+1, action=action, time_utc=f"2026-09-11T00:00:0{i}+00:00",
                   event_sha256=str(i)*64, payload_rehashed=False, sha256_origin="B_LEDGER",
                   source_absent=True, destination_present=True, size_matches_ledger=True)
              for i,action in enumerate(mod.ACTIONS)]
    return {"entries":[row]}, events


def test_enriched_ledger_preserves_b_fields_and_truthful_operation_bounds():
    control, events = history()
    row = mod.enrich(control, events)[0]
    assert all(row[k] == value for k,value in control["entries"][0].items())
    assert row["payload_rehashed"] is False and row["sha256_origin"] == "B_LEDGER"
    assert row["terminal"] == "PURGED"


@pytest.mark.parametrize("mutation", ["old_hash_action", "missing_purge", "wrong_hash", "false_rehash", "out_of_order"])
def test_incomplete_or_misrepresented_journal_is_rejected(mutation):
    control, events = history()
    if mutation == "old_hash_action": events[1]["action"] = "MOVED_HASH_VERIFIED"
    elif mutation == "missing_purge": events.pop()
    elif mutation == "wrong_hash": events[1]["sha256"] = "c"*64
    elif mutation == "false_rehash": events[1]["payload_rehashed"] = True
    else: events[1]["time_utc"] = "2026-09-10T00:00:00+00:00"
    with pytest.raises(base.PurgeError):
        mod.enrich(control, events)


def test_actual_fixture_driver_to_literal_final_archive(world, monkeypatch):
    import gzip
    import json
    world.instance().run()
    (world.audit / "CONTINUATION_IMPORT.json").write_bytes(b"{}\n")
    (world.audit / "UNKNOWN_BY_CLASS.csv").write_bytes(b"extension,directory_type,file_count,logical_bytes\n")
    original = (world.audit / "DELETION_LEDGER.json").read_bytes()
    monkeypatch.setattr(base, "hash_file", lambda *args, **kwargs: pytest.fail("payload hash forbidden"))
    receipt = mod.finalize(world.clean, world.code, world.policy, world.audit)
    final_bytes = (world.audit / "FINAL/DELETION_LEDGER.json").read_bytes()
    archive = world.code / "docs/paper_rebuild/purge" / ("DELETION_LEDGER_"+world.audit.name+".json.gz")
    assert gzip.decompress(archive.read_bytes()) == final_bytes
    assert archive.read_bytes()[4:8] == bytes(4)
    assert receipt["final_ledger_sha256"] == base._digest(final_bytes)
    assert (world.audit / "DELETION_LEDGER.json").read_bytes() == original
    assert json.loads(final_bytes)["file_count"] == 2
    assert mod.finalize(world.clean, world.code, world.policy, world.audit) == receipt


def test_full_finalizer_rejects_missing_c5_check_keys(world):
    import json
    world.instance().run()
    (world.audit / "CONTINUATION_IMPORT.json").write_bytes(b"{}\n")
    (world.audit / "UNKNOWN_BY_CLASS.csv").write_bytes(b"extension,directory_type,file_count,logical_bytes\n")
    c5 = json.loads((world.audit / "C5_RECEIPT.json").read_bytes())
    c5["checks"] = {"dummy":"PASS"}
    c5 = seal_receipt(c5)
    (world.audit / "C5_RECEIPT.json").write_bytes(base._json_bytes(c5))
    purge = json.loads((world.audit / "PURGE_RESULT.json").read_bytes())
    purge["previous_receipt_sha256"] = c5["receipt_sha256"]
    (world.audit / "PURGE_RESULT.json").write_bytes(base._json_bytes(seal_receipt(purge)))
    with pytest.raises(base.PurgeError, match="C5 independent checks"):
        mod.finalize(world.clean, world.code, world.policy, world.audit)
    assert not (world.audit / "FINAL").exists()


@pytest.mark.parametrize("cache", [False, True])
def test_fresh_b_finalizer_uses_planning_summary_and_keeps_storage_evidence(world, cache):
    import json
    fresh_ledger(world, cache=cache)
    world.instance().run()
    (world.audit / "PLANNING_SUMMARY.json").write_bytes(b'{"status":"PLANNED"}\n')
    (world.audit / "UNKNOWN_BY_CLASS.csv").write_bytes(b"extension,directory_type,file_count,logical_bytes\n")
    mod.finalize(world.clean, world.code, world.policy, world.audit)
    final = json.loads((world.audit / "FINAL/DELETION_LEDGER.json").read_bytes())
    assert "PLANNING_SUMMARY.json" in final["sources"]
    assert "CONTINUATION_IMPORT.json" not in final["sources"]
    assert final["storage_regression_tests"]["passed"] == 7
    assert final["c5_checks"]["storage_regression_tests"] == "PASS"


@pytest.mark.parametrize("field,value", [("status", "FAIL"), ("passed", 0), ("passed", 7.0),
                                        ("skipped", 1), ("test_files", []), ("xml_sha256", "f" * 64)])
def test_finalizer_rejects_incomplete_or_miscounted_storage_regression(world, field, value):
    import json
    world.instance().run()
    (world.audit / "CONTINUATION_IMPORT.json").write_bytes(b"{}\n")
    (world.audit / "UNKNOWN_BY_CLASS.csv").write_bytes(b"extension,directory_type,file_count,logical_bytes\n")
    c5_path = world.audit / "C5_RECEIPT.json"
    c5 = json.loads(c5_path.read_bytes())
    c5["storage_regression_tests"][field] = value
    c5 = seal_receipt(c5)
    c5_path.write_bytes(base._json_bytes(c5))
    purge_path = world.audit / "PURGE_RESULT.json"
    purge = json.loads(purge_path.read_bytes())
    purge["previous_receipt_sha256"] = c5["receipt_sha256"]
    purge_path.write_bytes(base._json_bytes(seal_receipt(purge)))
    with pytest.raises(base.PurgeError, match="storage"):
        mod.finalize(world.clean, world.code, world.policy, world.audit)
    assert not (world.audit / "FINAL").exists()


@pytest.mark.parametrize("field", ["source_absent", "destination_present", "size_matches_ledger"])
def test_finalizer_requires_each_authorized_move_postcondition(field):
    control, events = history()
    events[1][field] = False
    with pytest.raises(base.PurgeError, match="three authorized postconditions"):
        mod.enrich(control, events)
