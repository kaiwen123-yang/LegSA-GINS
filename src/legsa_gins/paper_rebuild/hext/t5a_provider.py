"""T5a heading-source/rate tables outside the frozen v2.1 chain.

Only the caller authorizes real input access and output creation.  This library
does not read a trace or launch a solver/evaluator.  The raw observation adapter
calls the frozen A1 implementation directly; it does not reimplement its yaw
formula.  Synthetic test fixtures must never be labelled real-data evidence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path
from typing import Mapping

import numpy as np

from ...input_generation import status_yaw_builder
from . import heading_provider as hp

YAW_STD_TOKEN = b"2.933193"
VARIANTS = ("R1", "R5", "R1F", "R5F")
BY2O_SEGMENTS = {"primary": (3369.94, 3411.95), "secondary": (3495.94, 3508.94)}


class T5AProviderError(hp.HeadingProviderError):
    """Fail-closed provider gate, retaining its diagnostic record."""

    def __init__(self, message: str, *, audit=None):
        super().__init__(message)
        self.audit = audit or {}


def _integer_itows(values):
    keys = list(values)
    if (not keys or any(not isinstance(key, (int, float, np.integer, np.floating))
                        or not math.isfinite(float(key)) or int(key) != key
                        or not 0 <= int(key) < hp.WEEK_SECONDS * 1000 for key in keys)
            or any(right <= left for left, right in zip(keys, keys[1:]))):
        raise T5AProviderError("Raw iTOW must be unique, chronological integer milliseconds")
    return [int(key) for key in keys]


def raw_yaw_from_ned(p1_ned_m, p2_ned_m, *, itow_ms, gps_week: int,
                     base_time: float, adapter_root: Path, data_mode="real_raw"):
    """Apply unchanged frozen A1 transforms to simultaneous raw NED positions.

    The caller supplies HPPOSECEF positions transformed with EXT05's fixed NED
    origin/rotation. Both CSVs contain the *same exact iTOW-derived timestamps*;
    hence the frozen builder takes its exact-time branch, without interpolation.
    rel_acc fields are zero placeholders unused by either yaw transform. They
    cannot be used as measured accuracy or as a provider noise estimate.

    ``adapter_root`` must not already exist. Serialized observations remain for
    provenance; no temporary-file cleanup or source-file mutation is performed.
    """
    keys = _integer_itows(itow_ms)
    if (not isinstance(gps_week, (int, np.integer)) or gps_week < 0
            or not math.isfinite(float(base_time))):
        raise T5AProviderError("Invalid GPS week/base time")
    if data_mode not in ("real_raw", "synthetic"):
        raise T5AProviderError("Adapter data_mode must be real_raw or synthetic")
    positions = (np.asarray(p1_ned_m, dtype=float), np.asarray(p2_ned_m, dtype=float))
    if any(p.shape != (len(keys), 3) or not np.isfinite(p).all() for p in positions):
        raise T5AProviderError("Expected finite matching raw receiver NED position arrays")
    fields = ["header.stamp.secs", "header.stamp.nsecs", "rel_pos_n", "rel_pos_e",
              "rel_pos_d", "rel_acc_n", "rel_acc_e", "rel_acc_d"]
    origin = hp.GPS_EPOCH_UNIX + int(gps_week) * hp.WEEK_SECONDS - hp.LEAP_SECONDS
    payloads = []
    for receiver_positions in positions:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        for key, point in zip(keys, receiver_positions):
            seconds, remainder_ms = divmod(key, 1000)
            writer.writerow([origin + seconds, remainder_ms * 1_000_000,
                             *(format(float(value), ".17g") for value in point), 0, 0, 0])
        payloads.append(stream.getvalue().encode("ascii"))
    adapter_root = Path(adapter_root)
    adapter_root.mkdir(parents=True, exist_ok=False)
    paths = [adapter_root / "gnss1_raw_ned_adapter.csv", adapter_root / "gnss2_raw_ned_adapter.csv"]
    for path, payload in zip(paths, payloads):
        with path.open("xb") as handle:
            handle.write(payload)
    a1_rows, frozen_audit = status_yaw_builder.build_a1_dual_diff_yaw_rows(
        paths[0], paths[1], base_time=float(base_time))
    converted = status_yaw_builder.apply_yaw_install_and_ned(a1_rows, sign=1.0, offset_deg=0.0)
    if len(converted) != len(keys) or frozen_audit["interpolation_outside_range_count"] != 0:
        raise T5AProviderError("Frozen A1 builder did not retain all exact raw iTOW pairs")
    result = []
    for key, row in zip(keys, converted):
        seconds, remainder_ms = divmod(key, 1000)
        exact_timestamp = float(origin + seconds) + remainder_ms * 0.001
        if float(row["timestamp"]) != exact_timestamp:
            raise T5AProviderError("Frozen builder timestamp no longer equals exact paired iTOW")
        result.append({**row, "itow_ms": key,
                       "frozen_builder_yaw_source": row["yaw_source"],
                       "yaw_source": "RAW_HPPOSECEF_EXACT_ITOW_FROZEN_A1_TRANSFORM"})
    audit = {
        "status": "PASS_FROZEN_A1_DIRECT_CALLS", "data_mode": data_mode,
        "synthetic_data_used": data_mode == "synthetic", "semisynthetic_data_used": False,
        "observation_format_conversion_only": True,
        "input_role": "RAW_HPPOSECEF_POSITIONS_IN_EXT05_FIXED_NED_FRAME",
        "baseline_definition": "GNSS2_MINUS_GNSS1_AT_IDENTICAL_RAW_ITOW",
        "accuracy_fields_role": "ZERO_ADAPTER_PLACEHOLDERS_UNUSED_BY_YAW_NOT_OBSERVATIONS",
        "frozen_functions": ["status_yaw_builder.build_a1_dual_diff_yaw_rows",
                             "status_yaw_builder.apply_yaw_install_and_ned"],
        "yaw_sign": 1.0, "install_offset_deg": 0.0,
        "paired_epoch_count": len(keys), "exact_time_pair_count": len(keys),
        "receiver_interpolation_required_count": 0,
        "adapter_members": [{"name": path.name, "sha256": hashlib.sha256(payload).hexdigest(),
                             "size_bytes": len(payload)} for path, payload in zip(paths, payloads)],
        "frozen_builder_audit": frozen_audit, "trace_payload_reads": 0,
    }
    return result, audit


def carr_soln(flags: int) -> int:
    if not isinstance(flags, (int, np.integer)) or not 0 <= int(flags) <= 255:
        raise T5AProviderError("NAV-PVT flags must be unsigned integer bytes")
    return (int(flags) >> 6) & 3


def validate_t5a_byte_gate(frozen_bytes: bytes, candidate_bytes: bytes, *, variant: str,
                          r1_not_both_fixed_line_indices=None):
    """Require heading-only bytes and the revised D3 per-variant validity gate.

    R1 is a subset of E, with exclusions exactly equal to independently decoded
    known PVT not-both-fixed epochs. Missing raw/PVT evidence cannot be included
    in that exclusion set. R1F retains the frozen validity tokens exactly.
    """
    if variant not in VARIANTS:
        raise T5AProviderError("Unknown T5a variant")
    before, width = hp._rows(frozen_bytes)
    after, candidate_width = hp._rows(candidate_bytes)
    if width != 18 or candidate_width != 18:
        raise T5AProviderError("D3 requires frozen and candidate 18-column GNSS tables")
    gate = hp.validate_heading_byte_gate(frozen_bytes, candidate_bytes)
    if any(row["tokens"][hp.YAW_STD_COLUMN] != YAW_STD_TOKEN for row in after):
        raise T5AProviderError("D3 yaw_std token must remain exactly 2.933193")
    validity_gate = {}
    if variant == "R1":
        selected = {row["line_index"] for row in before if float(row["tokens"][hp.YAW_VALID_COLUMN]) == 1.}
        candidate_selected = {row["line_index"] for row in after if float(row["tokens"][hp.YAW_VALID_COLUMN]) == 1.}
        if not candidate_selected <= selected:
            raise T5AProviderError("D3 R1 valid set must be a subset of frozen E")
        if r1_not_both_fixed_line_indices is None:
            raise T5AProviderError("D3 R1 requires independent PVT not-both-fixed exclusion evidence")
        expected_excluded = set(r1_not_both_fixed_line_indices)
        if not expected_excluded <= selected or selected - candidate_selected != expected_excluded:
            raise T5AProviderError("D3 R1 E-minus-valid differs from PVT not-both-fixed set",
                                  audit={"variant": variant,
                                         "actual_excluded_line_indices": sorted(selected - candidate_selected),
                                         "expected_excluded_line_indices": sorted(expected_excluded)})
        validity_gate = {"R1_valid_subset_of_E": True,
                         "R1_excluded_exactly_PVT_not_both_fixed": True,
                         "R1_excluded_line_indices": sorted(expected_excluded)}
    if variant == "R1F":
        mismatches = [left["line_index"] for left, right in zip(before, after)
                      if left["tokens"][hp.YAW_VALID_COLUMN] != right["tokens"][hp.YAW_VALID_COLUMN]]
        if mismatches:
            raise T5AProviderError("D3 R1F valid pattern differs from frozen table",
                                  audit={"variant": variant, "mismatched_line_indices": mismatches})
    exact_valid_tokens = all(left["tokens"][hp.YAW_VALID_COLUMN] == right["tokens"][hp.YAW_VALID_COLUMN]
                             for left, right in zip(before, after))
    return {**gate, "variant": variant, "yaw_std_token": YAW_STD_TOKEN.decode(),
            "frozen_valid_tokens_byte_equal": exact_valid_tokens, **validity_gate}


def _carrier_label(states):
    if None in states:
        return "MISSING_PVT"
    if any(state == 3 for state in states):
        return "RESERVED_CARRIER_STATE"
    if any(state == 0 for state in states):
        return "NO_CARRIER_SOLUTION"
    return {(2, 2): "BOTH_FIXED", (2, 1): "FIXED_FLOAT",
            (1, 2): "FLOAT_FIXED", (1, 1): "BOTH_FLOAT"}[tuple(states)]


def _scope_counts(rows, names):
    return {
        "provider_row_count": len(rows),
        "a1_epoch_count": sum(row["a1_valid"] for row in rows),
        "a1_not_both_fixed_count": sum(row["a1_valid"] and row["pvt_known_not_both_fixed"] for row in rows),
        "a1_missing_raw_count": sum(row["a1_valid"] and not row["raw_epoch_matched"] for row in rows),
        "a1_missing_pvt_count": sum(row["a1_valid"] and row["raw_fixed_float_label"] == "MISSING_PVT" for row in rows),
        "missing_raw_count": sum(not row["raw_epoch_matched"] for row in rows),
        "missing_pvt_count": sum(row["raw_fixed_float_label"] == "MISSING_PVT" for row in rows),
        "no_carrier_solution_count": sum(row["raw_fixed_float_label"] == "NO_CARRIER_SOLUTION" for row in rows),
        "reserved_carrier_state_count": sum(row["raw_fixed_float_label"] == "RESERVED_CARRIER_STATE" for row in rows),
        "variant_valid_counts": {name: sum(row[name + "_valid"] for row in rows) for name in names},
        "variant_invalid_counts": {name: sum(not row[name + "_valid"] for row in rows) for name in names},
        "E_excluded_counts": {name: sum(row["a1_valid"] and not row[name + "_valid"] for row in rows)
                              for name in names if name.startswith("R1")},
    }


def build_t5a_variants(frozen_bytes: bytes, *, expected_sha256: str, gps_week: int,
                       base_time: float, raw_yaw_rows, pvt_flags1: Mapping[int, int],
                       pvt_flags2: Mapping[int, int], sequence: str, window=None,
                       variants=None):
    """Return table bytes/audit/diagnostics without writing provider tables.

    Revised D3: R1 is E intersected with both-fixed PVT, with exact set-difference
    verification. R1F permits each receiver to be float or fixed and must retain
    all E. Missing raw/PVT rows remain invalid and are separately listed, never
    reconstructed, interpolated, or relabelled as PVT not-both-fixed evidence.
    Tables always cover the complete provider; window only affects audit counts.
    """
    if sequence not in ("BY2", "BY2H", "BY2O"):
        raise T5AProviderError("Unknown T5a sequence")
    if window is not None and (len(window) != 2 or not all(math.isfinite(float(value)) for value in window)
                               or window[1] < window[0]):
        raise T5AProviderError("Window must be finite and ordered")
    names = tuple(variants) if variants is not None else (VARIANTS if sequence == "BY2O" else VARIANTS[:2])
    if (not names or len(set(names)) != len(names) or any(name not in VARIANTS for name in names)
            or sequence != "BY2O" and any(name.endswith("F") for name in names)):
        raise T5AProviderError("Variant is outside the T5a sequence matrix")
    epochs = hp.extract_epoch_set(frozen_bytes, expected_sha256=expected_sha256,
                                  gps_week=gps_week, base_time=base_time, window=window)
    original, width = hp._rows(frozen_bytes)
    if width != 18:
        raise T5AProviderError("D3 requires frozen 18-column GNSS tables")
    raw_map = {}
    for row in raw_yaw_rows:
        key = _integer_itows([row["itow_ms"]])[0]
        if key in raw_map or not math.isfinite(float(row["yaw_ned_deg"])):
            raise T5AProviderError("Duplicate raw yaw iTOW or nonfinite raw yaw")
        raw_map[key] = row
    selected = set(epochs["itow_ms"])
    lines = {name: frozen_bytes.splitlines(keepends=True) for name in names}
    diagnostics = []
    invalid_on_e = {name: [] for name in names if name in ("R1", "R1F")}
    for record in original:
        tokens, index = record["tokens"], record["line_index"]
        key = hp.time_to_itow_ms(tokens[0], gps_week=gps_week, base_time=base_time)
        raw = raw_map.get(key)
        states = [carr_soln(flags[key]) if key in flags else None for flags in (pvt_flags1, pvt_flags2)]
        pvt_both_fixed = all(state == 2 for state in states)
        pvt_known_not_both_fixed = None not in states and not pvt_both_fixed
        fixed_valid = raw is not None and pvt_both_fixed
        float_valid = raw is not None and all(state in (1, 2) for state in states)
        yaw = float(raw["yaw_ned_deg"]) if raw is not None else None
        yaw_token = f"{yaw % 360.0:.6f}".encode() if yaw is not None else None
        if yaw_token == b"360.000000":
            yaw_token = b"0.000000"
        eligibility = {}
        for name in names:
            valid = (float_valid if name.endswith("F") else fixed_valid) and (key in selected if name.startswith("R1") else True)
            eligibility[name] = valid
            replacements = {hp.YAW_STD_COLUMN: YAW_STD_TOKEN,
                            hp.YAW_VALID_COLUMN: b"1" if valid else b"0"}
            if name.startswith("R1") and valid == (key in selected):
                replacements[hp.YAW_VALID_COLUMN] = tokens[hp.YAW_VALID_COLUMN]
            if valid:
                replacements[hp.YAW_COLUMN] = yaw_token
            elif name.startswith("R1") and key in selected:
                invalid_on_e[name].append(key)
            lines[name][index] = hp._replace_tokens(record, replacements)
        time_s = float(tokens[0])
        segment = next((name for name, (start, end) in BY2O_SEGMENTS.items() if start <= time_s <= end), "outside") if sequence == "BY2O" else "NOT_APPLICABLE"
        diagnostics.append({"line_index": index, "itow_ms": key, "time_s": time_s,
                            "a1_valid": key in selected, "raw_epoch_matched": raw is not None,
                            "receiver1_carrSoln": states[0], "receiver2_carrSoln": states[1],
                            "pvt_both_fixed": pvt_both_fixed,
                            "pvt_known_not_both_fixed": pvt_known_not_both_fixed,
                            "raw_fixed_float_label": _carrier_label(states),
                            "segment": segment,
                            "in_closed_window": window[0] <= time_s <= window[1] if window is not None else None,
                            "both_fixed_valid": fixed_valid, "float_or_fixed_valid": float_valid,
                            "yaw_raw_unrounded_deg": yaw,
                            "yaw_raw_serialized_deg": float(yaw_token) if yaw_token else None,
                            "yaw_a1_deg": float(tokens[hp.YAW_COLUMN]) if key in selected else None,
                            "yaw_a1_token": tokens[hp.YAW_COLUMN].decode("ascii"),
                            "delta_raw_minus_a1_deg": hp._wrap180(yaw - float(tokens[hp.YAW_COLUMN]))
                            if yaw is not None and key in selected else None,
                            **{name + "_valid": valid for name, valid in eligibility.items()}})
    epoch_audit = {**epochs,
                   "raw_grid_matched_count": len(selected & raw_map.keys()),
                   "raw_grid_unmatched_itow_ms": sorted(selected - raw_map.keys()),
                   "raw_grid_unmatched_count": len(selected - raw_map.keys())}
    payloads = {name: b"".join(content) for name, content in lines.items()}
    not_fixed_on_e = [row["itow_ms"] for row in diagnostics if row["a1_valid"] and row["pvt_known_not_both_fixed"]]
    counts = {"all_provider": _scope_counts(diagnostics, names),
              "closed_window": _scope_counts([row for row in diagnostics if row["in_closed_window"]], names)
              if window is not None else "NOT_REQUESTED"}
    audit = {"status": "PENDING_D3_GATES", "sequence": sequence, "epoch_set": epoch_audit,
             "yaw_std_token": YAW_STD_TOKEN.decode(), "yaw_sign": 1.0, "install_offset_deg": 0.0,
             "raw_validity": "BOTH_NAV_PVT_carrSoln_EQUALS_2",
             "float_variant_validity": "EACH_NAV_PVT_carrSoln_IN_1_2",
             "R1_missing_valid_itow_ms": invalid_on_e,
             "R1_missing_valid_counts": {name: len(keys) for name, keys in invalid_on_e.items()},
             "A1_epochs_not_both_fixed_itow_ms": not_fixed_on_e,
             "A1_epochs_not_both_fixed_count": len(not_fixed_on_e),
             "counts": counts, "closed_window": list(window) if window is not None else "NOT_REQUESTED",
             "BY2O_segments": {name: list(bounds) for name, bounds in BY2O_SEGMENTS.items()} if sequence == "BY2O" else "NOT_APPLICABLE",
             "variant_valid_counts": {name: sum(row[name + "_valid"] for row in diagnostics) for name in names},
             "variant_sha256": {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
             "missing_raw_itow_ms": [row["itow_ms"] for row in diagnostics if not row["raw_epoch_matched"]],
             "missing_pvt_itow_ms": [row["itow_ms"] for row in diagnostics if None in (row["receiver1_carrSoln"], row["receiver2_carrSoln"])],
             "trace_payload_reads": 0, "HV_RP_RD_IMU_modified": False}
    not_fixed_lines = [row["line_index"] for row in diagnostics if row["a1_valid"] and row["pvt_known_not_both_fixed"]]
    audit["byte_gates"] = {}
    for name, payload in payloads.items():
        try:
            audit["byte_gates"][name] = validate_t5a_byte_gate(
                frozen_bytes, payload, variant=name, r1_not_both_fixed_line_indices=not_fixed_lines)
        except hp.HeadingProviderError as error:
            audit["status"] = "HARD_STOP_D3_" + name + "_VALIDITY_OR_BYTE_GATE"
            audit["failed_gate"] = {"variant": name, "message": str(error),
                                    "detail": getattr(error, "audit", {})}
            raise T5AProviderError(str(error), audit=audit) from error
    audit["status"] = "PASS_D3_BYTE_AND_VALID_GATES"
    return payloads, audit, diagnostics
