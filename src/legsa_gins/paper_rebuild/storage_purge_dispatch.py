"""Fail-closed, synchronous dispatch for one storage-purge authorization.

This module performs no I/O.  The caller supplies trusted phase implementations;
it does not infer success from process launch, an absent exception, or old PASS
files.  Every callback must return an explicit, self-hashed PASS receipt.  Each
invocation has a fresh challenge, and downstream receipts bind both that
preflight and their immediately preceding receipt.  Callbacks must report their
actual exit status and gates; hashing cannot attest that a dishonest callback
performed its work.

``preflight(challenge)`` is followed, only after validation, by
``quarantine(permit)``, ``c5(permit, quarantine_receipt)``, and
``purge(permit, quarantine_receipt, c5_receipt)``.  No callback is retried.
Required gates are configured explicitly for all four phases.  All receipt
gates, including additional gates, must be the literal string ``PASS``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
import uuid


PHASES = ("preflight", "quarantine", "c5", "purge")
Pairs = tuple[tuple[str, str], ...]


class DispatchRejected(ValueError):
    """An explicit receipt or authorization binding was invalid."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DispatchRejected("receipt must contain finite JSON values") from exc


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def seal_receipt(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Copy JSON receipt fields and add their canonical SHA-256 (not a signature)."""
    if not isinstance(fields, Mapping) or any(not isinstance(k, str) for k in fields):
        raise DispatchRejected("receipt must be a mapping with string keys")
    body = dict(fields)
    body.pop("receipt_sha256", None)
    copied = json.loads(_canonical(body))
    copied["receipt_sha256"] = _sha(_canonical(copied))
    return copied


def _pairs(value: Any, name: str, *, hashes: bool = False) -> Pairs:
    if not isinstance(value, Mapping) or not value:
        raise DispatchRejected(f"{name} must be a nonempty mapping")
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise DispatchRejected(f"{name} requires nonempty string keys and values")
        if hashes and re.fullmatch(r"[0-9a-f]{64}", item) is None:
            raise DispatchRejected(f"{name} requires lowercase SHA-256 values")
    return tuple(sorted(value.items()))


@dataclass(frozen=True, slots=True)
class PreflightChallenge:
    preflight_id: str
    binding: Pairs
    control_hashes: Pairs


@dataclass(frozen=True, slots=True)
class ValidatedReceipt:
    phase: str
    receipt_sha256: str
    canonical_json: bytes

    def to_dict(self) -> dict[str, Any]:
        """Return a detached copy; mutations cannot alter the validated receipt."""
        return json.loads(self.canonical_json)


@dataclass(frozen=True, slots=True)
class DispatchPermit:
    preflight_id: str
    binding: Pairs
    control_hashes: Pairs
    preflight_sha256: str
    preflight_receipt: ValidatedReceipt


@dataclass(frozen=True, slots=True)
class DispatchResult:
    permit: DispatchPermit
    quarantine_receipt: ValidatedReceipt
    c5_receipt: ValidatedReceipt
    purge_receipt: ValidatedReceipt


def _identity(value: Any) -> tuple[Any, ...]:
    """Snapshot even frozen objects, detecting callback bypasses of dataclass guards."""
    if isinstance(value, PreflightChallenge):
        return (value.preflight_id, value.binding, value.control_hashes)
    if isinstance(value, ValidatedReceipt):
        return (value.phase, value.receipt_sha256, value.canonical_json)
    if isinstance(value, DispatchPermit):
        return (value.preflight_id, value.binding, value.control_hashes,
                value.preflight_sha256, id(value.preflight_receipt),
                _identity(value.preflight_receipt))
    raise DispatchRejected("unexpected authorization object")


def _call(callback: Callable[..., Any], *args: Any) -> Any:
    before = tuple(_identity(arg) for arg in args)
    result = callback(*args)  # Exceptions deliberately propagate; never retry.
    if tuple(_identity(arg) for arg in args) != before:
        raise DispatchRejected("callback mutated authorization or prior receipt")
    return result


def _validate(raw: Any, *, phase: str, challenge: PreflightChallenge,
              gates: tuple[str, ...], preflight_sha256: str | None = None,
              previous_receipt_sha256: str | None = None) -> ValidatedReceipt:
    if not isinstance(raw, Mapping):
        raise DispatchRejected(f"{phase}: explicit receipt mapping required")
    sealed = seal_receipt(raw)
    if raw.get("receipt_sha256") != sealed["receipt_sha256"]:
        raise DispatchRejected(f"{phase}: receipt SHA-256 mismatch or missing")
    if sealed.get("phase") != phase or sealed.get("status") != "PASS":
        raise DispatchRejected(f"{phase}: explicit phase and PASS status required")
    exit_code = sealed.get("exit_code")
    if type(exit_code) is not int or exit_code != 0:
        raise DispatchRejected(f"{phase}: integer exit_code zero required")
    reported_gates = sealed.get("gates")
    if (not isinstance(reported_gates, dict) or not reported_gates
            or any(not isinstance(k, str) or not k for k in reported_gates)
            or not set(gates).issubset(reported_gates)
            or any(value != "PASS" for value in reported_gates.values())):
        raise DispatchRejected(f"{phase}: all required and reported gates must PASS")
    if sealed.get("preflight_id") != challenge.preflight_id:
        raise DispatchRejected(f"{phase}: stale or substituted preflight identity")
    if _pairs(sealed.get("binding"), "binding") != challenge.binding:
        raise DispatchRejected(f"{phase}: binding mismatch")
    if _pairs(sealed.get("control_hashes"), "control_hashes", hashes=True) != challenge.control_hashes:
        raise DispatchRejected(f"{phase}: control hashes mismatch")
    if preflight_sha256 is not None and sealed.get("preflight_sha256") != preflight_sha256:
        raise DispatchRejected(f"{phase}: preflight SHA-256 mismatch")
    if previous_receipt_sha256 is not None and sealed.get("previous_receipt_sha256") != previous_receipt_sha256:
        raise DispatchRejected(f"{phase}: predecessor receipt SHA-256 mismatch")
    return ValidatedReceipt(phase, sealed["receipt_sha256"], _canonical(sealed))


def dispatch(*, expected_binding: Mapping[str, str],
             expected_control_hashes: Mapping[str, str],
             required_gates: Mapping[str, tuple[str, ...] | list[str]],
             preflight: Callable[[PreflightChallenge], Mapping[str, Any]],
             quarantine: Callable[[DispatchPermit], Mapping[str, Any]],
             c5: Callable[[DispatchPermit, ValidatedReceipt], Mapping[str, Any]],
             purge: Callable[[DispatchPermit, ValidatedReceipt, ValidatedReceipt],
                             Mapping[str, Any]]) -> DispatchResult:
    """Run exactly one fresh, fully bound sequence or raise at its first failure.

    Receipts require phase, status, exit_code, gates, preflight_id, binding,
    control_hashes and receipt_sha256.  Downstream receipts additionally require
    preflight_sha256 and previous_receipt_sha256.  Use ``seal_receipt`` only
    after recording a phase's actual outcomes.  A failure can follow partial
    callback side effects; this dispatcher neither rolls those back nor resumes.
    """
    if not isinstance(required_gates, Mapping) or set(required_gates) != set(PHASES):
        raise DispatchRejected("required_gates must configure exactly all four phases")
    frozen_gates = {}
    for phase in PHASES:
        values = required_gates[phase]
        if (not isinstance(values, (tuple, list)) or not values
                or any(not isinstance(v, str) or not v for v in values)
                or len(set(values)) != len(values)):
            raise DispatchRejected(f"{phase}: nonempty unique required gates needed")
        frozen_gates[phase] = tuple(values)
    if not all(callable(callback) for callback in (preflight, quarantine, c5, purge)):
        raise DispatchRejected("all four phase implementations must be callable")
    challenge = PreflightChallenge(uuid.uuid4().hex,
                                   _pairs(expected_binding, "expected_binding"),
                                   _pairs(expected_control_hashes, "expected_control_hashes", hashes=True))
    preflight_receipt = _validate(_call(preflight, challenge), phase="preflight",
                                  challenge=challenge, gates=frozen_gates["preflight"])
    permit = DispatchPermit(challenge.preflight_id, challenge.binding,
                            challenge.control_hashes, preflight_receipt.receipt_sha256,
                            preflight_receipt)

    def validate_next(raw: Any, phase: str, previous: ValidatedReceipt) -> ValidatedReceipt:
        return _validate(raw, phase=phase, challenge=challenge, gates=frozen_gates[phase],
                         preflight_sha256=preflight_receipt.receipt_sha256,
                         previous_receipt_sha256=previous.receipt_sha256)

    quarantine_receipt = validate_next(_call(quarantine, permit), "quarantine", preflight_receipt)
    c5_receipt = validate_next(_call(c5, permit, quarantine_receipt), "c5", quarantine_receipt)
    purge_receipt = validate_next(_call(purge, permit, quarantine_receipt, c5_receipt),
                                  "purge", c5_receipt)
    return DispatchResult(permit, quarantine_receipt, c5_receipt, purge_receipt)
