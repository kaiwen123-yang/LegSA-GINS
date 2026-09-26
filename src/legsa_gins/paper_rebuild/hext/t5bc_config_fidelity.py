"""T5bc byte-preserving config clones and exact effective-option checks.

This pure library never reads a dataset or invokes a binary. Existing frozen
configuration bytes are never serialized from YAML. A B3 clone appends only its
four explicit input/model keys after replacing only the GNSS path line.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

import yaml

from .t5a_config_fidelity import (
    STATIC_ECHO_KEYS, _exact, flat_key_values, flat_string,
    validate_gnsspath_only_bytes,
)
from .t5a_runtime import clone_runtime_config, _runtime_mapping

B3_KEYS = ("dual_antenna_measurement_model", "baseline3d_path",
           "baseline3d_length_m", "baseline3d_k_b")
B3_ROLE = "dual_antenna_baseline3d"
B3_PURPOSE = "three_dimensional_gnss_baseline_measurement"
GNSS_ROLE = "gnss_position_receiver_velocity_dual_yaw"


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _model_values(baseline3d):
    if set(baseline3d) != set(B3_KEYS):
        raise ValueError("B3 requires exactly its four declared config keys")
    result = dict(baseline3d)
    if result["dual_antenna_measurement_model"] != "baseline3d":
        raise ValueError("B3 model must be baseline3d")
    path = result["baseline3d_path"]
    if not isinstance(path, str) or not path or any(c in path for c in "\r\n"):
        raise ValueError("Invalid B3 path")
    for key in B3_KEYS[2:]:
        value = result[key]
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("B3 length and calibration scale must be explicit positive numbers")
        result[key] = float(value)
    return result


def _extra_lines(values, newline):
    result = b""
    for key in B3_KEYS:
        value = values[key]
        token = json.dumps(value, ensure_ascii=False, allow_nan=False)
        line = (key + ": " + token).encode("utf-8") + newline
        native = flat_key_values(line)
        if set(native) != {key}:
            raise ValueError("B3 key cannot round-trip through the frozen flat parser")
        decoded = flat_string(native[key]) if isinstance(value, str) else float(native[key])
        if not _exact(decoded, value) or not _exact(yaml.safe_load(line)[key], value):
            raise ValueError("B3 config value cannot round-trip through the frozen flat parser")
        result += line
    return result


def validate_config_bytes(frozen_bytes, candidate_bytes, *, gnsspath=None, baseline3d=None):
    """Independent gate a; no normalization of unchanged bytes is permitted."""
    before = _runtime_mapping(frozen_bytes)
    _runtime_mapping(candidate_bytes)  # Duplicate declarations are forbidden.
    values = _model_values(baseline3d) if baseline3d is not None else None
    if any(key in before for key in B3_KEYS):
        raise RuntimeError("HARD_STOP_T5BC_CONFIG_BYTE_GATE: model keys already exist in frozen config")
    core = candidate_bytes
    if values is not None:
        if not frozen_bytes.endswith(b"\n"):
            raise RuntimeError("HARD_STOP_T5BC_CONFIG_BYTE_GATE: append requires existing final newline")
        newline = b"\r\n" if frozen_bytes.endswith(b"\r\n") else b"\n"
        suffix = _extra_lines(values, newline)
        if not candidate_bytes.endswith(suffix):
            raise RuntimeError("HARD_STOP_T5BC_CONFIG_BYTE_GATE: B3 suffix differs")
        core = candidate_bytes[:-len(suffix)]
    if gnsspath is not None:
        gate = validate_gnsspath_only_bytes(frozen_bytes, core, expected_gnsspath=gnsspath)
        changed_lines = gate["changed_line_count"]
    else:
        if core != frozen_bytes:
            raise RuntimeError("HARD_STOP_T5BC_CONFIG_BYTE_GATE: frozen config bytes changed")
        gate = {"passed": True, "frozen_prefix_bytes_identical": True}
        changed_lines = 0
    after = _runtime_mapping(candidate_bytes)
    if values is not None and any(after.get(key) is not False for key in
                                  ("enable_multi_state_qm", "enable_qa_fallback")):
        raise RuntimeError("HARD_STOP_T5BC_CONFIG_SCOPE: frozen pilot requires QM and QA false")
    return {"passed": True, "original_config_bytes_sha256": _sha(frozen_bytes),
            "candidate_config_sha256": _sha(candidate_bytes),
            "existing_changed_line_count": changed_lines,
            "added_line_count": len(B3_KEYS) if values is not None else 0,
            "added_keys": list(B3_KEYS) if values is not None else [],
            "original_line_gate": gate,
            "model": "baseline3d" if values is not None else "scalar",
            "serialization_policy": "LINE_TEXT_REPLACEMENT_OR_EXACT_APPEND_NO_YAML_ROUNDTRIP"}


def clone_config(frozen_bytes, *, expected_sha256, gnsspath=None, baseline3d=None):
    """Make an identity, scalar-provider, or B3 clone without YAML dumping."""
    if _sha(frozen_bytes) != expected_sha256:
        raise RuntimeError("HARD_STOP_T5BC_FROZEN_CONFIG_HASH")
    _runtime_mapping(frozen_bytes)
    if baseline3d is not None:
        values = _model_values(baseline3d)
        newline = b"\r\n" if frozen_bytes.endswith(b"\r\n") else b"\n"
        core = frozen_bytes
        if gnsspath is not None:
            core, _ = clone_runtime_config(frozen_bytes, expected_sha256=expected_sha256, gnsspath=gnsspath)
        candidate = core + _extra_lines(values, newline)
    elif gnsspath is not None:
        candidate, _ = clone_runtime_config(frozen_bytes, expected_sha256=expected_sha256,
                                           gnsspath=gnsspath)
    else:
        candidate = frozen_bytes
    gate = validate_config_bytes(frozen_bytes, candidate, gnsspath=gnsspath, baseline3d=baseline3d)
    return candidate, gate


def compare_effective_echo(candidate, frozen, *, gnsspath=None, baseline3d=None):
    """Gate b: all 211 legacy fields plus every enabled B3 input parameter."""
    expected = deepcopy({key: frozen[key] for key in STATIC_ECHO_KEYS if key in frozen})
    missing = [key for key in STATIC_ECHO_KEYS if key not in frozen or key not in candidate]
    if gnsspath is not None:
        expected["actual_solver_input_paths"][GNSS_ROLE] = gnsspath
    values = _model_values(baseline3d) if baseline3d is not None else None
    if values is not None:
        expected["actual_solver_input_paths"][B3_ROLE] = values["baseline3d_path"]
        expected["actual_solver_input_roles"][B3_ROLE] = B3_PURPOSE
        expected.update(values)
        missing.extend(key for key in B3_KEYS if key not in candidate)
    elif candidate.get("dual_antenna_measurement_model", "scalar") != "scalar":
        raise RuntimeError("HARD_STOP_T5BC_EFFECTIVE_ECHO: identity/scalar run activated B3")
    mismatches = [key for key, value in expected.items()
                  if key in candidate and not _exact(candidate[key], value)]
    if missing or mismatches:
        raise RuntimeError("HARD_STOP_T5BC_EFFECTIVE_ECHO: " +
                           json.dumps({"missing": missing, "mismatches": mismatches}))
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(",", ":"),
                                        allow_nan=False).encode()
    return {"passed": True, "legacy_static_field_count": len(STATIC_ECHO_KEYS),
            "additional_model_field_count": len(B3_KEYS) if values is not None else 0,
            "comparison": "EXACT_RECURSIVE_JSON_VALUE_EQUALITY_NO_TOLERANCE",
            "fields": list(expected), "expected_sha256": _sha(canonical(expected)),
            "candidate_sha256": _sha(canonical({key: candidate[key] for key in expected})),
            "permitted_input_changes": (["gnsspath"] if gnsspath is not None else []) +
                                       (list(B3_KEYS) if values is not None else [])}


WITNESS_CHANGED_KEYS = ("case_id", "run_id", "run_label", "gnsspath", "outputpath")

def derive_expected_echo_from_witness(target_bytes, witness_bytes, witness_echo, *, changed_keys):
    """D37 static expectation only; never claim a missing historical echo exists."""
    if set(changed_keys) != set(WITNESS_CHANGED_KEYS) or len(changed_keys) != 5:
        raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_CHANGED_KEYS")
    def lines(payload):
        rows = payload.splitlines(keepends=True)
        keys = {}
        for index, line in enumerate(rows):
            parsed = flat_key_values(line)
            for key in parsed:
                if key in keys:
                    raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_DUPLICATE_KEY")
                keys[key] = index
        return rows, keys
    a, ak = lines(target_bytes)
    b, bk = lines(witness_bytes)
    if len(a) != len(b) or ak != bk:
        raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_LINE_STRUCTURE")
    actual = {key for key, index in ak.items() if a[index] != b[index]}
    permitted = {ak[key] for key in WITNESS_CHANGED_KEYS if key in ak}
    if actual != set(WITNESS_CHANGED_KEYS) or any(x != y and i not in permitted for i,(x,y) in enumerate(zip(a,b))):
        raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_NON_METADATA_BYTES")
    target, donor = _runtime_mapping(target_bytes), _runtime_mapping(witness_bytes)
    if {k:v for k,v in target.items() if k not in WITNESS_CHANGED_KEYS} != {k:v for k,v in donor.items() if k not in WITNESS_CHANGED_KEYS}:
        raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_SCIENCE_FIELDS")
    for key in ("case_id", "run_id", "run_label"):
        if witness_echo[key] != donor[key]:
            raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_DONOR_METADATA")
    if witness_echo["actual_solver_input_paths"][GNSS_ROLE] != donor["gnsspath"]:
        raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_DONOR_GNSS")
    expected = deepcopy(witness_echo)
    expected.update({key: target[key] for key in ("case_id", "run_id", "run_label")})
    expected["actual_solver_input_paths"][GNSS_ROLE] = target["gnsspath"]
    return expected, {"status": "DERIVED_EXPECTED_OPTIONS_FROM_BYTE_IDENTICAL_CONFIG",
        "historical_target_echo_available": False, "scientific_config_bytes_equal": True,
        "changed_keys": sorted(actual), "target_config_sha256": _sha(target_bytes),
        "witness_config_sha256": _sha(witness_bytes)}
