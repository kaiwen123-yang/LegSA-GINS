#!/usr/bin/env python3
"""Pure CSV metadata preparation; no file I/O, navigation or velocity generation.

The caller reads each registered input once. This function verifies those bytes
once and appends dependency fields while preserving every original field byte.
Source/plan pins are supplied provenance; the runner verifies their registration.
"""
from collections import Counter
import hashlib
import io
import json
import math
import struct

import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.hv_a1_dependencies import dependencies, SCOPE

SCHEMA = "HV_CALIBRATED_GNSS18_TIME_V1"
CHUNK_SIZE = 8192
ADDED_FIELDS = (
    "dependency_schema",
    "dependency_source_row_index",
    "dependency_source_time_bits_hex",
    "dependency_supported",
    "dependency_ready_source_time_s",
)
REQUIRED_FIELDS = (
    "time", "valid", "update_flag", "go2_source_valid", "a1_heading_valid",
    "frame_candidate", "prior_policy",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _verify_bytes(data, pin, role):
    require(isinstance(data, bytes), role + ": immutable bytes required")
    require(isinstance(pin, dict) and isinstance(pin.get("path"), str)
            and bool(pin["path"]), role + ": source path required")
    require(type(pin.get("size_bytes")) is int and pin["size_bytes"] >= 0,
            role + ": byte-size pin required")
    require(len(data) == pin["size_bytes"], role + ": input size mismatch")
    digest = hashlib.sha256(data).hexdigest()
    require(digest == pin.get("sha256"), role + ": input SHA mismatch")
    return dict(path=pin["path"], sha256=digest, size_bytes=len(data),
                hash_passes=1)


def _physical_lines(data):
    """Split only at LF, as std::getline does; retain each exact line ending."""
    start = 0
    while start < len(data):
        end = data.find(b"\n", start)
        if end < 0:
            yield data[start:], b""
            return
        raw = data[start:end]
        if raw.endswith(b"\r"):
            yield raw[:-1], b"\r\n"
        else:
            yield raw, b"\n"
        start = end + 1


def _cells(raw, role):
    require(b"\r" not in raw, role + ": bare carriage return")
    text = raw.decode("utf-8")
    require(bool(text.strip()), role + ": whitespace-only native row")
    result, cell, quoted = [], [], False
    for char in text:
        if char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            result.append("".join(cell).strip())
            cell = []
        else:
            cell.append(char)
    require(not quoted, role + ": unclosed physical quote/multiline field")
    result.append("".join(cell).strip())
    return result


def _boolean(value, name):
    value = value.lower()
    require(value in ("0", "1", "false", "true"), name + ": explicit boolean required")
    return value in ("1", "true")


def _finite_time(value):
    time = float(value)
    require(math.isfinite(time), "nonfinite HV source time")
    return time


def _historical_endpoints(data):
    gnss = np.loadtxt(io.StringIO(data.decode("utf-8")), dtype=np.float64, ndmin=2)
    require(gnss.ndim == 2 and gnss.shape[0] > 0 and gnss.shape[1] == 18,
            "historical GNSS18 shape")
    require(np.isfinite(gnss[:, 0]).all() and np.all(np.diff(gnss[:, 0]) > 0),
            "historical GNSS18 time order")
    require(np.isin(gnss[:, 17], [0., 1.]).all(), "historical A1 validity flags")
    rows = np.flatnonzero(gnss[:, 17] == 1.)
    require(np.isfinite(gnss[rows, 13]).all(), "finite yaw at actual generating endpoints")
    return gnss[rows, 0].copy(), rows.tolist(), len(gnss)


def prepare_bytes(hv_bytes, gnss_bytes, *, hv_pin, gnss_pin, source_pins,
                  plan_pin, expected_rows=None, expected_helper_calls=None,
                  sequence_id="SYNTHETIC"):
    """Return (augmented_csv_bytes, manifest), with no filesystem access.

    Support is the original generator support, not old validity and not arrival.
    Unsupported rows always have empty ready metadata, even when interpolation
    computed outside/gap values. Ready for a supported row is max(HV source time,
    the latest nonzero endpoint's ORIGINAL GNSS row time), never its rounded knot.
    """
    require(isinstance(sequence_id, str) and bool(sequence_id), "sequence identity required")
    require(isinstance(source_pins, dict) and bool(source_pins), "source pins required")
    require(isinstance(plan_pin, dict) and bool(plan_pin), "plan pin required")
    for value, name in ((expected_rows, "expected_rows"),
                        (expected_helper_calls, "expected_helper_calls")):
        require(value is None or (type(value) is int and value >= 0),
                name + ": nonnegative integer required")
    # Copy provenance only; no implied source/plan file verification here.
    provenance = json.loads(json.dumps(dict(source_pins=source_pins, plan_pin=plan_pin),
                                       allow_nan=False))
    hv_identity = _verify_bytes(hv_bytes, hv_pin, "HV")
    gnss_identity = _verify_bytes(gnss_bytes, gnss_pin, "historical GNSS")
    endpoint_times, endpoint_rows, gnss_rows = _historical_endpoints(gnss_bytes)
    lines = iter(_physical_lines(hv_bytes))
    try:
        header, header_eol = next(lines)
    except StopIteration as exc:
        raise ValueError("missing HV header") from exc
    fields = _cells(header, "HV header")
    require(len(fields) == len(set(fields)) and all(fields), "ambiguous HV header")
    require(not set(fields).intersection(ADDED_FIELDS), "dependency column collision")
    require(set(REQUIRED_FIELDS).issubset(fields), "required original HV columns absent")
    require(header_eol in (b"\n", b"\r\n"), "HV header must have a line ending")
    positions = {name: fields.index(name) for name in REQUIRED_FIELDS}
    output = bytearray(header + b"," + ",".join(ADDED_FIELDS).encode("ascii") + header_eol)
    pending, queries = [], []
    row_count = helper_calls = supported_count = blank_lines = prefix_count = 0
    original_valid_count = 0
    kinds, endings = Counter(), Counter()
    endings[header_eol.decode("ascii")] += 1

    def flush():
        nonlocal helper_calls, supported_count, prefix_count
        if not queries:
            # Bare LF blanks are the only skipped native lines.
            for raw, eol, record in pending:
                require(record is None and raw == b"" and eol == b"\n", "blank-line identity")
                output.extend(eol)
            pending.clear()
            return
        helper_calls += 1
        results = dependencies(queries, endpoint_times, round_to_ms=True, maximum_gap_s=1.2)
        require(len(results) == len(queries), "full chunk dependency count")
        dependency_index = 0
        for raw, eol, record in pending:
            if record is None:
                output.extend(eol)
                continue
            index, time, old_valid, update, source_valid, old_support = record
            dep = results[dependency_index]
            dependency_index += 1
            support = dep["support"]
            require(type(support) is bool and dep["query_time"] == time, "helper row identity")
            require(old_support == support, "a1_heading_valid/support mismatch")
            require(old_valid == update == (source_valid and support), "valid/update/source-support mismatch")
            ready = ""
            if support:
                latest = dep["latest_endpoint_source_time"]
                require(latest is not None and math.isfinite(latest), "supported endpoint time required")
                ready = repr(float(max(time, latest)))
                supported_count += 1
            metadata = (SCHEMA, str(index), struct.pack(">d", time).hex(),
                        "1" if support else "0", ready)
            suffix = b"," + ",".join(metadata).encode("ascii")
            emitted = raw + suffix + eol
            require(emitted[:len(raw)] == raw, "original field prefix changed")
            output.extend(emitted)
            prefix_count += 1
            kinds[dep["kind"]] += 1
        require(dependency_index == len(results), "all chunk rows consumed")
        pending.clear()
        queries.clear()

    for raw, eol in lines:
        endings[eol.decode("ascii")] += 1
        if raw == b"" and eol == b"\n":
            pending.append((raw, eol, None))
            blank_lines += 1
            continue
        # Empty CRLF is a nonempty "\\r" record for native std::getline.
        require(raw != b"", "empty CRLF/unterminated native record")
        cells = _cells(raw, "HV data")
        require(len(cells) == len(fields), "HV physical CSV width")
        row = {name: cells[index] for name, index in positions.items()}
        require(row["frame_candidate"] == "FLU_to_FRD_Go2_RP_injected_A1_NED"
                and row["prior_policy"] == "SENSOR_MODEL_V21_horizontal_weak_prior",
                "actual HV generator identity")
        time = _finite_time(row["time"])
        valid = _boolean(row["valid"], "valid")
        update = _boolean(row["update_flag"], "update_flag")
        source = _boolean(row["go2_source_valid"], "go2_source_valid")
        support = _boolean(row["a1_heading_valid"], "a1_heading_valid")
        record = (row_count, time, valid, update, source, support)
        pending.append((raw, eol, record))
        queries.append(time)
        original_valid_count += int(valid)
        row_count += 1
        if len(queries) == CHUNK_SIZE:
            flush()
    flush()
    require(expected_rows is None or row_count == expected_rows, "full original provider row count")
    require(expected_helper_calls is None or helper_calls == expected_helper_calls,
            "registered helper call count")
    require(prefix_count == row_count, "all original row prefixes verified")
    derived = bytes(output)
    manifest = dict(
        schema=SCHEMA, sequence_id=sequence_id, dependency_scope=SCOPE,
        input_pins=dict(hv=hv_identity, historical_gnss=gnss_identity),
        **provenance,
        derived_csv=dict(sha256=hashlib.sha256(derived).hexdigest(), size_bytes=len(derived)),
        original_fields=fields, appended_fields=list(ADDED_FIELDS),
        provider_rows=row_count, supported_rows=supported_count,
        unsupported_rows=row_count-supported_count,
        ready_empty_rows=row_count-supported_count,
        original_valid_rows=original_valid_count,
        original_flags_consistency_checked_rows=row_count,
        prefix_preserved_rows=prefix_count, original_field_bytes_preserved=True,
        original_order_and_line_endings_preserved=True, preserved_bare_lf_blank_lines=blank_lines,
        line_endings=dict(endings), helper_calls=helper_calls, helper_chunk_size=CHUNK_SIZE,
        dependency_kinds=dict(kinds), gnss_rows=gnss_rows,
        valid_a1_endpoint_rows=endpoint_rows, valid_a1_endpoints=len(endpoint_rows),
        rounding="numpy.float64 np.rint(t*1000)/1000",
        maximum_gap_s=1.2, ready_rule="supported ? max(HV_time,latest_original_endpoint_time) : EMPTY",
        metadata_only=True, velocity_recomputed=False, source_values_or_flags_changed=False,
        actual_arrival_qualified=False, raw_receiver_time_qualified=False,
        native_calls=0, evaluator_calls=0, file_io_performed=False,
        provenance_pin_qualification="SUPPLIED_BY_RUNNER_NOT_FILE_VERIFIED_HERE",
    )
    return derived, manifest
