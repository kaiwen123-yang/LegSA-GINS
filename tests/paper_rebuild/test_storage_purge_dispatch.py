"""Behavioral regression tests; callbacks are spies and perform no filesystem I/O."""

from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from legsa_gins.paper_rebuild.storage_purge_dispatch import (
    DispatchRejected, dispatch, seal_receipt,
)


BINDING = {"audit_id": "new-audit", "code_commit": "a" * 40}
HASHES = {"ledger_sha256": "b" * 64, "plan_sha256": "c" * 64}
GATES = {"preflight": ["IO_PROBE", "C1", "C2", "C3"],
         "quarantine": ["C4"], "c5": ["C5"], "purge": ["D"]}


def receipt(phase, context, previous=None):
    fields = {"phase": phase, "status": "PASS", "exit_code": 0,
              "gates": dict.fromkeys(GATES[phase], "PASS"),
              "preflight_id": context.preflight_id,
              "binding": dict(context.binding), "control_hashes": dict(context.control_hashes)}
    if phase != "preflight":
        fields.update(preflight_sha256=context.preflight_sha256,
                      previous_receipt_sha256=previous.receipt_sha256)
    return seal_receipt(fields)


@pytest.fixture
def stages():
    return {
        "preflight": Mock(side_effect=lambda ch: receipt("preflight", ch)),
        "quarantine": Mock(side_effect=lambda p: receipt("quarantine", p, p.preflight_receipt)),
        "c5": Mock(side_effect=lambda p, q: receipt("c5", p, q)),
        "purge": Mock(side_effect=lambda p, q, c: receipt("purge", p, c)),
    }


def run(stages, **overrides):
    args = dict(expected_binding=BINDING, expected_control_hashes=HASHES,
                required_gates=GATES, **stages)
    args.update(overrides)
    return dispatch(**args)


def changed(original, **changes):
    return seal_receipt(dict(original, **changes))


def assert_not_called(stages, *names):
    for name in names:
        stages[name].assert_not_called()


def test_success_calls_each_once_with_identical_permit_and_prior_receipts(stages):
    result = run(stages)
    for stage in stages.values():
        assert stage.call_count == 1
    assert stages["quarantine"].call_args.args == (result.permit,)
    assert stages["c5"].call_args.args[0] is result.permit
    assert stages["purge"].call_args.args[0] is result.permit
    assert stages["c5"].call_args.args[1] is result.quarantine_receipt
    assert stages["purge"].call_args.args[1] is result.quarantine_receipt
    assert stages["purge"].call_args.args[2] is result.c5_receipt
    assert result.permit.preflight_id == stages["preflight"].call_args.args[0].preflight_id
    assert result.purge_receipt.to_dict()["previous_receipt_sha256"] == result.c5_receipt.receipt_sha256


@pytest.mark.parametrize("bad_probe", ["FAIL", "ERROR", False, None, {"status": "PASS"}])
def test_failed_probe_never_launches_quarantine_even_with_overall_pass(stages, bad_probe):
    def preflight(challenge):
        result = receipt("preflight", challenge)
        result["gates"]["IO_PROBE"] = bad_probe
        return seal_receipt(result)
    stages["preflight"].side_effect = preflight
    with pytest.raises(DispatchRejected, match="gates"):
        run(stages)
    assert stages["preflight"].call_count == 1
    assert_not_called(stages, "quarantine", "c5", "purge")


@pytest.mark.parametrize("changes", [
    {"status": "FAIL"}, {"status": "COMPLETED"}, {"status": True},
    {"phase": "quarantine"}, {"exit_code": 1}, {"exit_code": -9},
    {"exit_code": False}, {"exit_code": 0.0}, {"exit_code": "0"},
    {"exit_code": None}, {"gates": {}}, {"gates": ["PASS"]},
    {"gates": {"IO_PROBE": "PASS", "C1": "PASS", "C2": "PASS"}},
    {"gates": dict.fromkeys(["IO_PROBE", "C1", "C2", "C3"], True)},
    {"gates": {**dict.fromkeys(GATES["preflight"], "PASS"), "EXTRA": "FAIL"}},
    {"binding": {**BINDING, "audit_id": "old-audit"}},
    {"control_hashes": {**HASHES, "ledger_sha256": "e" * 64}},
    {"control_hashes": {"ledger_sha256": "not-a-hash"}},
    {"preflight_id": "old-preflight"},
])
def test_invalid_preflight_never_dispatches(stages, changes):
    stages["preflight"].side_effect = lambda ch: changed(receipt("preflight", ch), **changes)
    with pytest.raises(DispatchRejected):
        run(stages)
    assert_not_called(stages, "quarantine", "c5", "purge")


@pytest.mark.parametrize("missing", ["phase", "status", "exit_code", "gates",
                                    "preflight_id", "binding", "control_hashes", "receipt_sha256"])
def test_missing_preflight_field_is_not_implicit_success(stages, missing):
    def preflight(ch):
        result = receipt("preflight", ch)
        del result[missing]
        return result if missing == "receipt_sha256" else seal_receipt(result)
    stages["preflight"].side_effect = preflight
    with pytest.raises(DispatchRejected):
        run(stages)
    assert_not_called(stages, "quarantine", "c5", "purge")


@pytest.mark.parametrize("raw", [None, True, 0, "PASS", []])
def test_no_receipt_is_not_success(stages, raw):
    stages["preflight"].side_effect = None
    stages["preflight"].return_value = raw
    with pytest.raises(DispatchRejected):
        run(stages)
    assert_not_called(stages, "quarantine", "c5", "purge")


@pytest.mark.parametrize("phase", ["preflight", "quarantine", "c5", "purge"])
def test_exception_propagates_without_retry_or_later_calls(stages, phase):
    failure = RuntimeError("actual phase failure")
    stages[phase].side_effect = failure
    with pytest.raises(RuntimeError) as exc:
        run(stages)
    assert exc.value is failure
    order = list(stages)
    assert stages[phase].call_count == 1
    assert_not_called(stages, *order[order.index(phase) + 1:])


@pytest.mark.parametrize("phase", ["quarantine", "c5", "purge"])
@pytest.mark.parametrize("changes", [
    {"status": "FAIL"}, {"exit_code": 2}, {"gates": {}},
    {"preflight_id": "replaced"}, {"preflight_sha256": "d" * 64},
    {"previous_receipt_sha256": "d" * 64},
    {"binding": {**BINDING, "audit_id": "different"}},
    {"control_hashes": {**HASHES, "plan_sha256": "d" * 64}},
])
def test_downstream_failures_and_identity_substitution_stop_immediately(stages, phase, changes):
    original = stages[phase].side_effect
    stages[phase].side_effect = lambda *args: changed(original(*args), **changes)
    with pytest.raises(DispatchRejected):
        run(stages)
    order = list(stages)
    assert stages[phase].call_count == 1
    assert_not_called(stages, *order[order.index(phase) + 1:])


def test_old_valid_pass_receipt_cannot_be_replayed_in_new_dispatch(stages):
    first = run(stages)
    old = first.permit.preflight_receipt.to_dict()
    for spy in stages.values():
        spy.reset_mock()
    stages["preflight"].side_effect = lambda ch: old
    with pytest.raises(DispatchRejected, match="stale"):
        run(stages)
    assert stages["preflight"].call_args.args[0].preflight_id != first.permit.preflight_id
    assert_not_called(stages, "quarantine", "c5", "purge")


def test_old_receipt_nonce_edit_without_rehash_is_rejected(stages):
    old = run(stages).permit.preflight_receipt.to_dict()
    for spy in stages.values():
        spy.reset_mock()
    stages["preflight"].side_effect = lambda ch: dict(old, preflight_id=ch.preflight_id)
    with pytest.raises(DispatchRejected, match="SHA-256"):
        run(stages)
    assert_not_called(stages, "quarantine", "c5", "purge")


def test_permit_and_receipts_are_immutable_and_detached(stages):
    result = run(stages)
    with pytest.raises(FrozenInstanceError):
        result.permit.preflight_id = "changed"
    detached = result.quarantine_receipt.to_dict()
    detached["binding"]["audit_id"] = "changed"
    assert result.quarantine_receipt.to_dict()["binding"] == BINDING


@pytest.mark.parametrize("target", ["permit", "preflight_receipt", "prior_receipt"])
def test_forced_mutation_of_immutable_authorization_stops_next_stage(stages, target):
    original = stages["c5"].side_effect
    def mutate(permit, prior):
        response = original(permit, prior)
        if target == "permit":
            object.__setattr__(permit, "preflight_id", "bad")
        elif target == "preflight_receipt":
            object.__setattr__(permit.preflight_receipt, "canonical_json", b"{}")
        else:
            object.__setattr__(prior, "receipt_sha256", "f" * 64)
        return response
    stages["c5"].side_effect = mutate
    with pytest.raises(DispatchRejected, match="mutated"):
        run(stages)
    stages["purge"].assert_not_called()


def test_challenge_forced_mutation_cannot_authorize_quarantine(stages):
    def mutate(ch):
        object.__setattr__(ch, "preflight_id", "previous-id")
        return receipt("preflight", ch)
    stages["preflight"].side_effect = mutate
    with pytest.raises(DispatchRejected, match="mutated"):
        run(stages)
    assert_not_called(stages, "quarantine", "c5", "purge")


def test_callers_mutable_input_maps_do_not_change_frozen_authorization(stages):
    binding, hashes = dict(BINDING), dict(HASHES)
    gates = {key: list(value) for key, value in GATES.items()}
    def preflight(ch):
        binding["audit_id"] = "changed"
        hashes["plan_sha256"] = "f" * 64
        gates["c5"].clear()
        return receipt("preflight", ch)
    stages["preflight"].side_effect = preflight
    result = run(stages, expected_binding=binding, expected_control_hashes=hashes, required_gates=gates)
    assert dict(result.permit.binding) == BINDING
    assert dict(result.permit.control_hashes) == HASHES


@pytest.mark.parametrize("override", [
    {"required_gates": {}},
    {"required_gates": {**GATES, "c5": []}},
    {"required_gates": {**GATES, "c5": "C5"}},
    {"required_gates": {**GATES, "c5": ["C5", "C5"]}},
    {"required_gates": {**GATES, "c5": [""]}},
    {"expected_binding": {}}, {"expected_binding": {"audit_id": 1}},
    {"expected_control_hashes": {}},
    {"expected_control_hashes": {"ledger": "x" * 64}},
    {"quarantine": None},
])
def test_bad_configuration_fails_before_any_callback(stages, override):
    with pytest.raises(DispatchRejected):
        run(stages, **override)
    assert_not_called(stages, *stages)


def test_sealing_is_canonical_and_does_not_mutate_input():
    first = {"b": {"y": 1, "x": 2}, "a": "evidence"}
    sealed = seal_receipt(first)
    assert "receipt_sha256" not in first
    assert sealed == seal_receipt({"a": "evidence", "b": {"x": 2, "y": 1}})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_nonfinite_or_non_json_evidence_cannot_be_sealed(value):
    with pytest.raises(DispatchRejected):
        seal_receipt({"value": value})
