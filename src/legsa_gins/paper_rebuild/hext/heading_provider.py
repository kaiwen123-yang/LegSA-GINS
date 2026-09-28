"""H-EXT-04 heading-only transforms and identity gates, with no runtime writes.

NOT_AUTHORIZED_FOR_EXECUTION: D4 library only; T5 requires preregistration.
Callers own input/output provenance, raw checkpoints and process-access audits.
These helpers never open a reference trace, launch a process or alter a provider.
"""
from __future__ import annotations

import csv
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
from typing import Mapping

import numpy as np
import yaml

from ...raw_gnss.ubx_raw_binary_rebuilder import iter_ubx_frames, parse_bytes_cell
from ..manifest import sha256_file

EXECUTION_STATUS = "NOT_AUTHORIZED_FOR_EXECUTION"

YAW_COLUMN, YAW_STD_COLUMN, YAW_VALID_COLUMN = 13, 14, 17
YAW_STD_TOKEN = b"2.933193"
LEAP_SECONDS = 18
GPS_EPOCH_UNIX = 315964800
WEEK_SECONDS = 604800
TIME_ROUNDTRIP_TOLERANCE_S = Decimal("0.000001")


class HeadingProviderError(ValueError):
    """An H-EXT-04 identity or byte-preservation gate failed."""


def _check_sha(payload: bytes, expected_sha256: str, role: str) -> str:
    actual = hashlib.sha256(payload).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha256)) or actual != expected_sha256:
        raise HeadingProviderError(role+" SHA-256 mismatch")
    return actual


def verify_frozen_inputs(specifications: Mapping[str, Mapping]) -> dict:
    """Stream-hash frozen binary/evaluator/config/provider inputs without changing them."""
    result = {}
    for role, spec in specifications.items():
        path = Path(spec["path"])
        if "trace" in role.lower() or path.name.startswith("trace_"):
            raise HeadingProviderError("Reference trace is outside heading-provider input scope")
        if path.is_symlink() or not path.is_file():
            raise HeadingProviderError("Frozen input is not an ordinary file: "+role)
        expected = str(spec["sha256"])
        actual = sha256_file(path)
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
            raise HeadingProviderError("Frozen input SHA-256 mismatch: "+role)
        result[role] = {"path": str(path), "sha256": actual, "size_bytes": path.stat().st_size}
    return result


def time_to_itow_ms(time_token, *, gps_week: int, base_time: float) -> int:
    """Invert V2's GPS-UTC formula; no receipt/header-time matching or fitting."""
    if int(gps_week) != gps_week or gps_week < 0 or not math.isfinite(float(base_time)):
        raise HeadingProviderError("Invalid GPS week or base time")
    relative = Decimal(time_token.decode() if isinstance(time_token, bytes) else str(time_token))
    if not relative.is_finite():
        raise HeadingProviderError("Nonfinite GNSS time")
    origin = Decimal(GPS_EPOCH_UNIX + int(gps_week)*WEEK_SECONDS - LEAP_SECONDS) - Decimal(str(base_time))
    raw_ms = (relative-origin)*1000
    key = int(raw_ms.to_integral_value(rounding=ROUND_HALF_EVEN))
    if not 0 <= key < WEEK_SECONDS*1000 or abs(relative-(origin+Decimal(key)/1000)) > TIME_ROUNDTRIP_TOLERANCE_S:
        raise HeadingProviderError("GNSS time does not invert to the frozen V2 iTOW identity")
    return key


def _rows(payload: bytes):
    records, width = [], None
    for line_index, line in enumerate(payload.splitlines(keepends=True)):
        if not line.strip() or line.lstrip().startswith(b"#"):
            continue
        matches = list(re.finditer(rb"\S+", line))
        tokens = [match.group() for match in matches]
        if len(tokens) not in (15, 18) or width not in (None, len(tokens)):
            raise HeadingProviderError("GNSS table must use one frozen 15/18-column format")
        width = len(tokens)
        try:
            finite = all(math.isfinite(float(token)) for token in tokens)
        except ValueError:
            finite = False
        if not finite:
            raise HeadingProviderError("GNSS table has a nonfinite or nonnumeric token")
        if width == 18 and any(float(tokens[index]) not in (0., 1.) for index in (15, 16, 17)):
            raise HeadingProviderError("GNSS validity flags must be binary")
        records.append({"line_index": line_index, "tokens": tokens, "matches": matches, "line": line})
    if not records:
        raise HeadingProviderError("Empty frozen GNSS table")
    return records, width


def extract_epoch_set(frozen_bytes: bytes, *, expected_sha256: str, gps_week: int,
                      base_time: float, window=None) -> dict:
    """D1 uses all frozen valid rows, including epochs outside the evaluation window."""
    _check_sha(frozen_bytes, expected_sha256, "Frozen GNSS")
    rows, width = _rows(frozen_bytes)
    all_keys, selected = [], []
    for record in rows:
        tokens = record["tokens"]
        key = time_to_itow_ms(tokens[0], gps_week=gps_week, base_time=base_time)
        all_keys.append(key)
        if width == 15 or float(tokens[YAW_VALID_COLUMN]) == 1.:
            selected.append({"line_index": record["line_index"], "itow_ms": key,
                             "time_s": float(tokens[0]), "yaw_ned_deg": float(tokens[YAW_COLUMN])})
    if any(b <= a for a, b in zip(all_keys, all_keys[1:])):
        raise HeadingProviderError("Frozen GNSS iTOW identities must be unique and chronological")
    return {"status": "AVAILABLE" if selected else "UNAVAILABLE", "reason": "" if selected else "EMPTY_A1_EPOCH_SET",
            "frozen_gnss_sha256": expected_sha256, "columns": width, "row_count": len(rows),
            "epoch_set_size": len(selected), "itow_ms": [row["itow_ms"] for row in selected], "a1_rows": selected,
            "closed_window_epoch_set_size": sum(window[0] <= row["time_s"] <= window[1] for row in selected)
                if window is not None else "NOT_REQUESTED",
            "scope": "ALL_FROZEN_YAW_VALID_ROWS_NOT_CLIPPED_TO_EVALUATION_WINDOW",
            "time_formula": "315964800 + gps_week*604800 + iTOW_ms/1000 - 18 - base_time",
            "fifteen_column_validity": "IMPLICIT_ALL_VALID" if width == 15 else "EXPLICIT_COLUMN_17"}


def pvt_flags_from_csv_bytes(payload: bytes, *, expected_sha256: str) -> dict[int, int]:
    """Decode NAV-PVT flags (byte 21) by exact iTOW; no status fix-type substitution."""
    _check_sha(payload, expected_sha256, "Receiver raw CSV")
    flags = {}
    for row in csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))):
        if row.get("name") != "UBX-NAV-PVT":
            continue
        frames = list(iter_ubx_frames(parse_bytes_cell(row["data"])))
        if len(frames) != 1:
            raise HeadingProviderError("NAV-PVT CSV row must contain one UBX frame")
        frame = frames[0]
        data = frame[6:-2]
        if frame[2:4] != b"\x01\x07" or len(data) != 92:
            raise HeadingProviderError("NAV-PVT class/length mismatch")
        key = struct.unpack_from("<I", data)[0]
        if key in flags:
            raise HeadingProviderError("Duplicate NAV-PVT iTOW")
        flags[key] = int(data[21])
    if not flags:
        raise HeadingProviderError("No NAV-PVT flags in receiver CSV")
    return flags


def both_receivers_fixed(flags1: int, flags2: int) -> bool:
    values = (flags1, flags2)
    if any(int(flag) != flag or not 0 <= int(flag) <= 255 for flag in values):
        raise HeadingProviderError("NAV-PVT flags must be unsigned bytes")
    return all((int(flag) >> 6) & 3 == 2 for flag in values)


def _wrap180(value):
    return (float(value)+180.) % 360. - 180.


def baseline_heading(b21_ned_m) -> tuple[float, float]:
    baseline = np.asarray(b21_ned_m, dtype=float)
    if baseline.shape != (3,) or not np.isfinite(baseline).all():
        raise HeadingProviderError("Expected finite EXT05 fixed-frame b21 NED vector")
    body_candidate = (-math.degrees(math.atan2(float(baseline[1]), float(baseline[0])))) % 360.
    return body_candidate, (90.-body_candidate) % 360.


def _replace_tokens(record, replacements):
    line, parts, end = record["line"], [], 0
    for column, match in enumerate(record["matches"]):
        parts.extend((line[end:match.start()], replacements.get(column, match.group())))
        end = match.end()
    parts.append(line[end:])
    return b"".join(parts)


def validate_heading_byte_gate(frozen_bytes: bytes, candidate_bytes: bytes, *,
                              preserved_line_indices=()) -> dict:
    """Require unchanged non-heading tokens, every whitespace byte and preserved E lines."""
    original, width = _rows(frozen_bytes)
    candidate, candidate_width = _rows(candidate_bytes)
    old_lines, new_lines = frozen_bytes.splitlines(keepends=True), candidate_bytes.splitlines(keepends=True)
    if len(old_lines) != len(new_lines) or width != candidate_width or len(original) != len(candidate):
        raise HeadingProviderError("D4 row/column byte gate failed")
    allowed = {YAW_COLUMN, YAW_STD_COLUMN} | ({YAW_VALID_COLUMN} if width == 18 else set())
    data_lines = {row["line_index"] for row in original}
    preserve = set(preserved_line_indices)
    if not preserve <= data_lines:
        raise HeadingProviderError("S5M preserve mask names nondata lines")
    for before, after in zip(original, candidate):
        index = before["line_index"]
        if after["line_index"] != index:
            raise HeadingProviderError("D4 row order changed")
        if index in preserve and before["line"] != after["line"]:
            raise HeadingProviderError("S5M A1 full-line byte gate failed")
        for column, (left, right) in enumerate(zip(before["tokens"], after["tokens"])):
            if column not in allowed and left != right:
                raise HeadingProviderError(f"D4 non-heading token byte gate failed line {index} column {column}")
        old_gaps = re.split(rb"\S+", before["line"])
        new_gaps = re.split(rb"\S+", after["line"])
        if old_gaps != new_gaps:
            raise HeadingProviderError("D4 whitespace byte gate failed")
    if any(left != right for index, (left, right) in enumerate(zip(old_lines, new_lines)) if index not in data_lines):
        raise HeadingProviderError("D4 header/blank-line byte gate failed")
    return {"passed": True, "rows_checked": len(original), "columns": width,
            "non_heading_tokens_byte_equal": True, "all_whitespace_byte_equal": True,
            "preserved_A1_full_lines": len(preserve)}


def angular_difference_statistics(values):
    """One shared D4 diagnostic definition: wrap to [-180,180), population std, |error| P95."""
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"status": "UNAVAILABLE", "reason": "EMPTY_A1_EPOCH_SET", "count": 0}
    if values.ndim != 1 or not np.isfinite(values).all():
        raise HeadingProviderError("Angular differences must be a finite one-dimensional sequence")
    values = (values+180.) % 360.-180.
    return {"status": "AVAILABLE", "count": len(values), "mean_deg": float(values.mean()),
            "std_population_deg": float(values.std(ddof=0)),
            "p95_absolute_deg": float(np.percentile(np.abs(values), 95)),
            "p95_signed_deg": float(np.percentile(values, 95)), "stop_condition": False}


def build_heading_variants(frozen_bytes: bytes, *, expected_sha256: str, gps_week: int,
                           base_time: float, solution_itow_ms, b21_ned_m,
                           pvt_flags1: Mapping[int, int], pvt_flags2: Mapping[int, int], window=None):
    """Return S5U/S5M bytes, D1/D4 audit and trace-free per-row diagnostic inputs."""
    epochs = extract_epoch_set(frozen_bytes, expected_sha256=expected_sha256, gps_week=gps_week,
                               base_time=base_time, window=window)
    original, width = _rows(frozen_bytes)
    keys = list(solution_itow_ms)
    baselines = np.asarray(b21_ned_m, dtype=float)
    if (baselines.shape != (len(keys), 3) or not np.isfinite(baselines).all()
            or any(int(key) != key for key in keys) or len(set(keys)) != len(keys)):
        raise HeadingProviderError("EXT05 baseline epoch identity/shape mismatch")
    baseline_map = {int(key): value for key, value in zip(keys, baselines)}
    selected = set(epochs["itow_ms"])
    lines = {name: frozen_bytes.splitlines(keepends=True) for name in ("S5U", "S5M")}
    diagnostics, differences = [], []
    invalid_on_a1 = 0
    for record in original:
        tokens, index = record["tokens"], record["line_index"]
        key = time_to_itow_ms(tokens[0], gps_week=gps_week, base_time=base_time)
        if key not in baseline_map or key not in pvt_flags1 or key not in pvt_flags2:
            raise HeadingProviderError("Missing exact-iTOW baseline or NAV-PVT flags")
        body, yaw = baseline_heading(baseline_map[key])
        valid = both_receivers_fixed(pvt_flags1[key], pvt_flags2[key])
        if width == 15 and not valid:
            raise HeadingProviderError("15-column format cannot represent an invalid D4 yaw; no implicit valid update allowed")
        # Match the existing six-decimal heading serialization. 360 rounds to the same 0-degree representation.
        yaw_token = f"{yaw:.6f}".encode()
        if yaw_token == b"360.000000":
            yaw_token = b"0.000000"
        replacements = {YAW_COLUMN: yaw_token, YAW_STD_COLUMN: YAW_STD_TOKEN}
        if width == 18:
            replacements[YAW_VALID_COLUMN] = b"1" if valid else b"0"
        changed = _replace_tokens(record, replacements)
        lines["S5U"][index] = changed
        if key not in selected:
            lines["S5M"][index] = changed
        difference = _wrap180(float(yaw_token)-float(tokens[YAW_COLUMN])) if key in selected else None
        if key in selected:
            differences.append(difference)
            invalid_on_a1 += int(not valid)
        diagnostics.append({"line_index": index, "itow_ms": key, "time_s": float(tokens[0]),
            "body_candidate_deg": body, "yaw_5hz_unrounded_deg": yaw, "yaw_5hz_deg": float(yaw_token),
            "yaw_5hz_valid": valid, "yaw_a1_deg": float(tokens[YAW_COLUMN]) if key in selected else None,
            "a1_valid": key in selected, "yaw_5hz_minus_a1_deg": difference,
            "receiver1_carrSoln": (int(pvt_flags1[key])>>6)&3,
            "receiver2_carrSoln": (int(pvt_flags2[key])>>6)&3})
    payloads = {name: b"".join(content) for name, content in lines.items()}
    gates = {name: validate_heading_byte_gate(frozen_bytes, payload,
             preserved_line_indices=[row["line_index"] for row in epochs["a1_rows"]] if name == "S5M" else ())
             for name, payload in payloads.items()}
    audit = {"status": "PASS_D4_BYTE_GATES", "epoch_set": epochs, "byte_gates": gates,
        "yaw_std_token": YAW_STD_TOKEN.decode(), "yaw_sign": 1.0, "install_offset_deg": 0.0,
        "body_candidate_formula": "wrap360(-degrees(atan2(b_e,b_n)))",
        "yaw_ned_formula": "wrap360(90-body_candidate)", "baseline_definition": "EXT05_FIXED_NED_p2_minus_p1",
        "validity": "BOTH_NAV_PVT_carrSoln_EQUALS_2", "A1_epochs_not_both_fixed_count": invalid_on_a1,
        "consistency_on_E": angular_difference_statistics(differences),
        "all_rows_5hz_valid_count": sum(row["yaw_5hz_valid"] for row in diagnostics),
        "variant_sha256": {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
        "trace_payload_reads": 0, "HV_RP_RD_IMU_modified": False}
    return payloads, audit, diagnostics


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise HeadingProviderError("Duplicate runtime config key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _runtime_mapping(payload):
    mapping = yaml.load(payload.decode("utf-8-sig"), Loader=_UniqueLoader)
    if not isinstance(mapping, dict) or "gnsspath" not in mapping:
        raise HeadingProviderError("Runtime config requires a root gnsspath key")
    return mapping


def config_without_gnsspath_hash(config_bytes: bytes) -> str:
    mapping = _runtime_mapping(config_bytes)
    del mapping["gnsspath"]
    return hashlib.sha256(json.dumps(mapping, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_config_gnsspath_only(frozen_bytes: bytes, candidate_bytes: bytes) -> dict:
    original, candidate = _runtime_mapping(frozen_bytes), _runtime_mapping(candidate_bytes)
    before = config_without_gnsspath_hash(frozen_bytes)
    after = config_without_gnsspath_hash(candidate_bytes)
    if before != after:
        raise HeadingProviderError("Runtime config non-gnsspath field hash mismatch")
    return {"passed": True, "non_gnsspath_sha256_before": before, "non_gnsspath_sha256_after": after,
            "changed_fields": [] if original["gnsspath"] == candidate["gnsspath"] else ["gnsspath"],
            "gnsspath_before": original["gnsspath"], "gnsspath_after": candidate["gnsspath"]}


def clone_runtime_config(frozen_bytes: bytes, *, expected_sha256: str, gnsspath: str):
    """Clone fields exactly except gnsspath; outputpath and every auxiliary path stay frozen."""
    _check_sha(frozen_bytes, expected_sha256, "Frozen runtime config")
    if not isinstance(gnsspath, str) or not gnsspath or "\n" in gnsspath or "\r" in gnsspath:
        raise HeadingProviderError("Invalid replacement gnsspath")
    config = _runtime_mapping(frozen_bytes)
    config["gnsspath"] = gnsspath
    payload = yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode()
    audit = validate_config_gnsspath_only(frozen_bytes, payload)
    audit.update(frozen_config_sha256=expected_sha256, config_sha256=hashlib.sha256(payload).hexdigest())
    return payload, audit
