"""GNSS1 RAWX/SFRBX to source-audited RINEX 3.04."""

from __future__ import annotations

import csv
import decimal
import json
import math
import os
import re
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..shared_raw_backend import reconstruct_ubx_stream
from .constants import (
    CONVBIN_SHA256,
    GINAV_MAX_FREQUENCIES,
    GINAV_SUPPORTED_SYSTEMS,
    RINEX_VERSION,
    RTKLIB_COMMIT,
    RTKLIB_LICENSE_SHA256,
    RTKLIB_TREE,
)
from .source import (
    AccessLedger,
    ForbiddenInputError,
    SourceIdentityError,
    assert_gnss1_only_path,
    sha256_file,
)
from .time_contract import (
    GPS_EPOCH_UNIX_SECONDS,
    NANOSECONDS,
    WEEK_SECONDS,
    gpst_calendar_to_gps,
    parse_rinex_epochs,
    utc_unix_ns_to_gps,
)


class RinexAdapterError(RuntimeError):
    pass


SYSTEM_NAMES = {
    "G": "GPS", "R": "GLONASS", "E": "GALILEO", "C": "BDS",
    "J": "QZSS", "S": "SBAS", "I": "IRNSS",
}

# Pinned global_variable.m obs-frequency tables and getcodepri.m priorities.
# ``set_index`` selects one exact tracking-code family for each raw decoder
# slot; ``decode_data`` writes only that family into P/L; ``adjobs`` then
# remaps BDS raw slots.  The SPP/TDCP route consumes post-adjobs P(1)/L(1).
OFFICIAL_RAW_SLOT_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "G": (("1", "CWPYMNSL"), ("2", "CWPYMNDSLX"), ("5", "IQX")),
    "R": (("1", "CP"), ("2", "CP"), ("3", "IQX"),
          ("4", "ABX"), ("6", "ABXP")),
    "E": (("1", "CABXZ"), ("5", "IQX"), ("7", "IQX"),
          ("8", "IQX"), ("6", "CABXZ")),
    "C": (("2", "IQX"), ("7", "IQXA"), ("6", "IQX"),
          ("1", "DPXA"), ("5", "DPX"), ("7", "DPZ")),
    "J": (("1", "CSLXZ"), ("2", "SLX"), ("5", "IQXDPZ"),
          ("6", "SLXEZ")),
}
BDS2_OUTPUT_TO_RAW_SLOTS = (1, 3, 2)
BDS3_OUTPUT_TO_RAW_SLOTS = (1, 3, 4)

UBX_MESSAGE_ROLES = {
    "02-15": (
        "INCLUDED_RINEX_OBSERVATION_AND_RAWX_TIME",
        "UBX_RXM_RAWX supplies the only GINav observation measurements",
    ),
    "02-13": (
        "INCLUDED_RINEX_BROADCAST_NAVIGATION",
        "UBX_RXM_SFRBX supplies broadcast navigation words to convbin",
    ),
    "01-07": (
        "TIME_NORMALIZATION_PROOF_ONLY_NOT_GINAV_MEASUREMENT",
        "fully-resolved NAV-PVT iTOW is decoded only for the no-search timestamp proof",
    ),
}


def _git_text(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True,
            text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RinexAdapterError(f"RTKLIB git identity failed: {exc}") from exc


def verify_converter_identity(rtklib_root: str | Path, convbin: str | Path) -> dict[str, Any]:
    root = Path(rtklib_root).resolve(strict=True)
    binary = Path(convbin).resolve(strict=True)
    if root not in binary.parents:
        raise RinexAdapterError("convbin is outside the pinned RTKLIB checkout")
    commit = _git_text(root, "rev-parse", "HEAD")
    tree = _git_text(root, "rev-parse", "HEAD^{tree}")
    tracked = _git_text(root, "status", "--porcelain=v1", "--untracked-files=no")
    license_hash = sha256_file(root / "LICENSE.txt")
    binary_hash = sha256_file(binary)
    issues = []
    if commit != RTKLIB_COMMIT:
        issues.append("commit")
    if tree != RTKLIB_TREE:
        issues.append("tree")
    if tracked:
        issues.append("tracked_dirty")
    if license_hash != RTKLIB_LICENSE_SHA256:
        issues.append("license")
    if binary_hash != CONVBIN_SHA256:
        issues.append("convbin")
    if issues:
        raise RinexAdapterError("RTKLIB/convbin identity mismatch: " + ",".join(issues))
    return {
        "backend": "RTKLIB_convbin",
        "repository": "https://github.com/tomojitakasu/RTKLIB",
        "commit": commit,
        "tree_oid": tree,
        "tracked_source_clean": True,
        "license": "BSD-2-Clause",
        "license_sha256": license_hash,
        "executable": str(binary),
        "executable_sha256": binary_hash,
    }


def build_convbin_command(
    convbin: str | Path,
    ubx_path: str | Path,
    observation_path: str | Path,
    navigation_path: str | Path,
) -> tuple[str, ...]:
    """Lossless-at-interface conversion: no interval, mask, or system filter."""

    return (
        str(Path(convbin)),
        "-r", "ubx",
        "-v", RINEX_VERSION,
        "-f", "5",
        "-od", "-os", "-oi", "-ot", "-ol",
        "-o", str(Path(observation_path)),
        "-n", str(Path(navigation_path)),
        str(Path(ubx_path)),
    )


def _header_version(path: Path) -> str:
    with path.open("r", encoding="ascii", errors="strict") as handle:
        first = handle.readline()
    if "RINEX VERSION / TYPE" not in first:
        raise RinexAdapterError(f"not a RINEX file: {path}")
    return first[:9].strip()


def _observation_types(path: Path) -> dict[str, tuple[str, ...]]:
    types: dict[str, list[str]] = defaultdict(list)
    current = ""
    expected: dict[str, int] = {}
    with path.open("r", encoding="ascii", errors="strict") as handle:
        for line in handle:
            label = line[60:80].strip() if len(line) >= 60 else ""
            if label == "END OF HEADER":
                break
            if label != "SYS / # / OBS TYPES":
                continue
            if line and line[0].strip():
                current = line[0]
                try:
                    expected[current] = int(line[3:6])
                except ValueError as exc:
                    raise RinexAdapterError("malformed RINEX observation-type count") from exc
            if not current:
                raise RinexAdapterError("orphan RINEX observation-type continuation")
            types[current].extend(line[7:60].split())
    for system, count in expected.items():
        if len(types[system]) != count:
            raise RinexAdapterError(
                f"RINEX observation-type conservation failed for {system}: "
                f"{len(types[system])} != {count}"
            )
    return {system: tuple(values) for system, values in sorted(types.items())}


NAV_RECORD_RE = re.compile(r"^(?P<system>[GRECJIS])(?P<prn>\d{2})\s")
OBS_RECORD_RE = re.compile(r"^(?P<system>[GRECJIS])(?P<prn>\d{2})(?:\s|$)")
NAV_TIME_RE = re.compile(
    r"^(?P<sat>[GRECJIS]\d{2})\s+(?P<year>\d{4})\s+(?P<month>\d{1,2})\s+"
    r"(?P<day>\d{1,2})\s+(?P<hour>\d{1,2})\s+(?P<minute>\d{1,2})\s+"
    r"(?P<second>\d{1,2}(?:\.\d+)?)"
)

# Exact source constants in src/common/global_variable.m, used here only for
# a pre-navigation availability audit. The named-file source lock protects
# their identity.
GINAV_MAX_EPHEMERIS_AGE_SECONDS = {
    "G": 7201.0,
    "R": 1800.0,
    "E": 14400.0,
    "C": 21601.0,
    "J": 7201.0,
}


def _navigation_records(path: Path) -> tuple[dict[str, int], dict[str, tuple[str, ...]]]:
    in_header = True
    counts: Counter[str] = Counter()
    satellites: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="ascii", errors="strict") as handle:
        for line in handle:
            if in_header:
                if "END OF HEADER" in line[60:80]:
                    in_header = False
                continue
            match = NAV_RECORD_RE.match(line)
            if match:
                system = match.group("system")
                counts[system] += 1
                satellites[system].add(system + match.group("prn"))
    return dict(sorted(counts.items())), {
        system: tuple(sorted(values)) for system, values in sorted(satellites.items())
    }


def _observation_satellites(path: Path) -> tuple[dict[str, int], dict[str, tuple[str, ...]]]:
    in_header = True
    line_counts: Counter[str] = Counter()
    satellites: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="ascii", errors="strict") as handle:
        for line in handle:
            if in_header:
                if "END OF HEADER" in line[60:80]:
                    in_header = False
                continue
            match = OBS_RECORD_RE.match(line)
            if match:
                system = match.group("system")
                line_counts[system] += 1
                satellites[system].add(system + match.group("prn"))
    return dict(sorted(line_counts.items())), {
        system: tuple(sorted(values)) for system, values in sorted(satellites.items())
    }


def _observation_value_inventory(
    path: Path,
    observation_types: Mapping[str, Sequence[str]],
) -> tuple[
    dict[str, dict[str, int]],
    dict[str, dict[str, tuple[str, ...]]],
    dict[str, dict[str, dict[str, tuple[int, ...]]]],
]:
    """Count finite nonzero serialized observations by system/type/satellite."""

    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if "END OF HEADER" in line[60:80]) + 1
    except StopIteration as exc:
        raise RinexAdapterError("RINEX observation header is unterminated") from exc
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    satellites: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    epochs: dict[str, dict[str, dict[str, set[int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    index = start
    epoch_index = -1
    while index < len(lines):
        line = lines[index]
        if line.startswith(">"):
            epoch_index += 1
            index += 1
            continue
        match = OBS_RECORD_RE.match(line)
        if match is None:
            index += 1
            continue
        system = match.group("system")
        sat = system + match.group("prn")
        types = tuple(observation_types.get(system, ()))
        payload = line[3:]
        next_index = index + 1
        while len(payload) < 16 * len(types) and next_index < len(lines):
            continuation = lines[next_index]
            if continuation.startswith(">") or OBS_RECORD_RE.match(continuation):
                break
            if not continuation.startswith("   "):
                break
            payload += continuation[3:]
            next_index += 1
        for field_index, observation_type in enumerate(types):
            token = payload[field_index * 16: field_index * 16 + 14].strip()
            if not token:
                continue
            try:
                value = float(token.replace("D", "E"))
            except ValueError as exc:
                raise RinexAdapterError(
                    f"malformed RINEX observation value for {sat} {observation_type}"
                ) from exc
            if math.isfinite(value) and value != 0.0:
                counts[system][observation_type] += 1
                satellites[system][observation_type].add(sat)
                if epoch_index < 0:
                    raise RinexAdapterError("observation row precedes its epoch header")
                epochs[system][sat][observation_type].add(epoch_index)
        index = next_index
    return (
        {system: dict(sorted(values.items())) for system, values in sorted(counts.items())},
        {
            system: {
                key: tuple(sorted(value)) for key, value in sorted(values.items())
            }
            for system, values in sorted(satellites.items())
        },
        {
            system: {
                sat: {
                    obs_type: tuple(sorted(epoch_indexes))
                    for obs_type, epoch_indexes in sorted(by_type.items())
                }
                for sat, by_type in sorted(by_satellite.items())
            }
            for system, by_satellite in sorted(epochs.items())
        },
    )


def _nav_decimal(field: str, *, role: str) -> decimal.Decimal:
    token = field.strip()
    if not token:
        return decimal.Decimal(0)
    try:
        value = decimal.Decimal(token.replace("D", "E").replace("d", "E"))
    except decimal.InvalidOperation as exc:
        raise RinexAdapterError(f"malformed RINEX navigation {role}") from exc
    if not value.is_finite():
        raise RinexAdapterError(f"nonfinite RINEX navigation {role}")
    return value


def _decimal_seconds_to_nanoseconds(value: decimal.Decimal, *, role: str) -> int:
    nanoseconds = value * NANOSECONDS
    rounded = nanoseconds.to_integral_value(rounding=decimal.ROUND_HALF_EVEN)
    if abs(nanoseconds - rounded) > decimal.Decimal("0.001"):
        raise RinexAdapterError(f"RINEX navigation {role} exceeds nanosecond precision")
    return int(rounded)


def _adjust_week(toe_total_ns: int, toc_total_ns: int) -> int:
    half_week_ns = (WEEK_SECONDS // 2) * NANOSECONDS
    week_ns = WEEK_SECONDS * NANOSECONDS
    difference = toe_total_ns - toc_total_ns
    if difference < -half_week_ns:
        return toe_total_ns + week_ns
    if difference > half_week_ns:
        return toe_total_ns - week_ns
    return toe_total_ns


def _record_toc_total_ns(match: re.Match[str]) -> int:
    toc = gpst_calendar_to_gps(
        int(match.group("year")), int(match.group("month")),
        int(match.group("day")), int(match.group("hour")),
        int(match.group("minute")), decimal.Decimal(match.group("second")),
    )
    return toc.week * WEEK_SECONDS * NANOSECONDS + toc.sow_nanoseconds


def _glonass_toe_total_ns(match: re.Match[str]) -> int:
    # decode_geph rounds the UTC Toc to the nearest 15 minutes first, then
    # applies UTC->GPST.  Reproduce that literal ordering.
    naive_total_ns = _record_toc_total_ns(match)
    naive_seconds = decimal.Decimal(naive_total_ns) / NANOSECONDS
    rounded_seconds = int(
        ((naive_seconds + decimal.Decimal(450)) / decimal.Decimal(900))
        .to_integral_value(rounding=decimal.ROUND_FLOOR)
    ) * 900
    utc_unix_ns = (
        GPS_EPOCH_UNIX_SECONDS + rounded_seconds
    ) * NANOSECONDS
    toe = utc_unix_ns_to_gps(utc_unix_ns)
    return toe.week * WEEK_SECONDS * NANOSECONDS + toe.sow_nanoseconds


def _navigation_time_inventory(path: Path) -> dict[str, tuple[int, ...]]:
    """Decode the exact Toe quantity used by GINav ephemeris search."""

    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    try:
        index = next(
            i for i, line in enumerate(lines) if "END OF HEADER" in line[60:80]
        ) + 1
    except StopIteration as exc:
        raise RinexAdapterError("RINEX navigation header is unterminated") from exc
    times: dict[str, list[int]] = defaultdict(list)
    bdt_epoch_gps_week = 1356
    while index < len(lines):
        first = lines[index]
        match = NAV_TIME_RE.match(first)
        if match is None:
            if first.strip():
                raise RinexAdapterError(
                    f"malformed RINEX navigation record at line {index + 1}"
                )
            index += 1
            continue
        satellite = match.group("sat")
        system = satellite[0]
        # RINEX 3 GLONASS and SBAS records both have one clock line plus
        # three continuation lines. SBAS is unsupported by GINav here, but
        # convbin is intentionally unfiltered, so its record must still be
        # consumed without overlapping the next supported record.
        record_line_count = 4 if system in {"R", "S"} else 8
        if index + record_line_count > len(lines):
            raise RinexAdapterError(f"truncated RINEX navigation record for {satellite}")
        record = lines[index:index + record_line_count]
        if any(NAV_TIME_RE.match(line) for line in record[1:]):
            raise RinexAdapterError(f"truncated RINEX navigation record for {satellite}")
        data = [
            _nav_decimal(first[23 + 19 * field:23 + 19 * (field + 1)],
                         role=f"{satellite} clock field {field + 1}")
            for field in range(3)
        ]
        for continuation_index, line in enumerate(record[1:], start=1):
            for field in range(4):
                data.append(
                    _nav_decimal(
                        line[4 + 19 * field:4 + 19 * (field + 1)],
                        role=(
                            f"{satellite} continuation {continuation_index} "
                            f"field {field + 1}"
                        ),
                    )
                )
        if system == "R":
            times[satellite].append(_glonass_toe_total_ns(match))
        elif system in {"G", "E", "C", "J"}:
            if len(data) < 22:
                raise RinexAdapterError(f"incomplete Toe/week fields for {satellite}")
            # GINav's fixed Galileo ephemeris selection requires the I/NAV
            # E1B/E5b code bit (bit 9) before searcheph considers a record.
            if system == "E" and not (int(data[20]) & (1 << 9)):
                index += record_line_count
                continue
            toe_ns = _decimal_seconds_to_nanoseconds(
                data[11], role=f"{satellite} Toe"
            )
            week = int(data[21])
            toc_total_ns = _record_toc_total_ns(match)
            if system == "C":
                toe_total_ns = (
                    (bdt_epoch_gps_week + week) * WEEK_SECONDS * NANOSECONDS
                    + toe_ns + 14 * NANOSECONDS
                )
                # decode_eph compares its GPST-converted BDS Toe with the
                # unconverted local Toc when applying adjweek.
                toe_total_ns = _adjust_week(toe_total_ns, toc_total_ns)
            else:
                toe_total_ns = week * WEEK_SECONDS * NANOSECONDS + toe_ns
                toe_total_ns = _adjust_week(toe_total_ns, toc_total_ns)
            times[satellite].append(toe_total_ns)
        index += record_line_count
    return {sat: tuple(sorted(values)) for sat, values in sorted(times.items())}


def _decoder_selected_signals(
    system: str, observation_types: Sequence[str]
) -> dict[int, str | None]:
    """Return the exact signal family selected by official ``set_index``."""

    families = {
        item[1:3] for item in observation_types
        if len(item) >= 3 and item[0] in {"C", "L", "D", "S"}
    }
    selected: dict[int, str | None] = {}
    for raw_slot, (digit, priorities) in enumerate(
        OFFICIAL_RAW_SLOT_RULES.get(system, ()), start=1
    ):
        candidates = [
            family for family in families
            if family[0] == digit and family[1] in priorities
        ]
        selected[raw_slot] = min(
            candidates, key=lambda family: priorities.index(family[1])
        ) if candidates else None
    return selected


def _output_to_raw_slots(system: str, satellite: str) -> tuple[int, ...]:
    if system != "C":
        return tuple(range(1, min(3, len(OFFICIAL_RAW_SLOT_RULES.get(system, ()))) + 1))
    try:
        prn = int(satellite[1:])
    except ValueError as exc:
        raise RinexAdapterError(f"malformed BDS satellite identifier: {satellite}") from exc
    return BDS2_OUTPUT_TO_RAW_SLOTS if prn < 19 else BDS3_OUTPUT_TO_RAW_SLOTS


def _official_used_slot_inventory(
    system: str,
    observation_types: Sequence[str],
    satellites: Sequence[str],
    nonzero_satellites: Mapping[str, Sequence[str]],
    nonzero_epochs: Mapping[str, Mapping[str, Sequence[int]]],
    ephemeris_coverage: Mapping[str, bool],
) -> dict[str, Any]:
    selected_by_raw = _decoder_selected_signals(system, observation_types)
    slot_satellites: dict[int, list[str]] = defaultdict(list)
    per_satellite: dict[str, dict[str, Any]] = {}
    contiguous_by_satellite: dict[str, int] = {}
    for satellite in sorted(satellites):
        output_slots: dict[str, Any] = {}
        contiguous = 0
        for output_slot, raw_slot in enumerate(
            _output_to_raw_slots(system, satellite), start=1
        ):
            signal = selected_by_raw.get(raw_slot)
            code_type = "C" + signal if signal else None
            phase_type = "L" + signal if signal else None
            code_nonzero = bool(
                code_type and satellite in nonzero_satellites.get(code_type, ())
            )
            phase_nonzero = bool(
                phase_type and satellite in nonzero_satellites.get(phase_type, ())
            )
            code_epochs = set(
                nonzero_epochs.get(satellite, {}).get(code_type or "", ())
            )
            phase_epochs = set(
                nonzero_epochs.get(satellite, {}).get(phase_type or "", ())
            )
            same_epoch_code_phase = code_epochs & phase_epochs
            phase_pair_current_epochs = {
                epoch for epoch in phase_epochs if epoch - 1 in phase_epochs
            }
            source_route_epochs = same_epoch_code_phase & phase_pair_current_epochs
            usable = bool(
                signal and code_nonzero and phase_nonzero and source_route_epochs
                and ephemeris_coverage.get(satellite, False)
            )
            output_slots[str(output_slot)] = {
                "raw_decoder_slot": raw_slot,
                "selected_signal_family": signal,
                "code_observation_type": code_type,
                "phase_observation_type": phase_type,
                "finite_nonzero_code_available": code_nonzero,
                "finite_nonzero_phase_available": phase_nonzero,
                "same_epoch_finite_nonzero_code_phase_count": len(
                    same_epoch_code_phase
                ),
                "consecutive_phase_pair_current_epoch_count": len(
                    phase_pair_current_epochs
                ),
                "same_epoch_p1_l1_plus_prior_l1_current_epoch_count": len(
                    source_route_epochs
                ),
                "matching_toe_coverage_all_experiment_epochs": bool(
                    ephemeris_coverage.get(satellite, False)
                ),
                "official_slot_usable": usable,
            }
            if usable:
                slot_satellites[output_slot].append(satellite)
                if output_slot == contiguous + 1:
                    contiguous += 1
        contiguous_by_satellite[satellite] = contiguous
        per_satellite[satellite] = output_slots
    maximum = max(contiguous_by_satellite.values(), default=0)
    return {
        "decoder_selected_signal_by_raw_slot": {
            str(key): value for key, value in selected_by_raw.items()
        },
        "bds_output_remapping": (
            {"BDS2_PRN_lt_19": list(BDS2_OUTPUT_TO_RAW_SLOTS),
             "BDS3_PRN_ge_19": list(BDS3_OUTPUT_TO_RAW_SLOTS)}
            if system == "C" else None
        ),
        "per_satellite_post_adjobs_output_slots": per_satellite,
        "usable_output_slot_satellites": {
            str(key): sorted(value) for key, value in sorted(slot_satellites.items())
        },
        "contiguous_usable_output_slot_count_by_satellite": contiguous_by_satellite,
        "maximum_contiguous_usable_output_slot_count": maximum,
        "official_spp_used_slot": 1,
        "official_spp_required_value": "P(1)",
        "official_tdcp_used_slot": 1,
        "official_tdcp_required_value": "L(1)_at_current_and_previous_epochs",
        "p1_l1_usable_satellites": sorted(slot_satellites.get(1, ())),
    }


def inventory_ubx_message_roles(
    message_counts: Mapping[str, int],
    *,
    discarded_byte_count: int,
    checksum_failure_count: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for message, count in sorted(message_counts.items()):
        role, reason = UBX_MESSAGE_ROLES.get(
            message,
            (
                "EXCLUDED_FROM_SELECTED_GINAV_INTERFACE",
                "retained byte-for-byte for lossless convbin input but not decoded "
                "as GINav observation/navigation or timestamp-proof material",
            ),
        )
        rows.append(
            {
                "ubx_class_id": message,
                "checksum_valid_message_count": int(count),
                "selected_role": role,
                "excluded_from_ginav_measurement_interface": role not in {
                    "INCLUDED_RINEX_OBSERVATION_AND_RAWX_TIME",
                    "INCLUDED_RINEX_BROADCAST_NAVIGATION",
                },
                "reason": reason,
            }
        )
    excluded = [
        row for row in rows if row["excluded_from_ginav_measurement_interface"]
    ]
    return {
        "message_classes": rows,
        "message_class_count": len(rows),
        "excluded_message_class_count": len(excluded),
        "excluded_checksum_valid_message_count": sum(
            row["checksum_valid_message_count"] for row in excluded
        ),
        "discarded_nonmessage_byte_count": int(discarded_byte_count),
        "discarded_nonmessage_reason": "not part of a checksum-valid UBX frame",
        "checksum_failure_count": int(checksum_failure_count),
        "checksum_failure_reason": "failed UBX checksum and excluded before convbin",
        "every_observed_message_class_has_explicit_role_and_reason": all(
            row["selected_role"] and row["reason"] for row in rows
        ),
    }


def audit_rinex_pair(observation_path: str | Path, navigation_path: str | Path) -> dict[str, Any]:
    obs_path = Path(observation_path)
    nav_path = Path(navigation_path)
    if _header_version(obs_path) != RINEX_VERSION or _header_version(nav_path) != RINEX_VERSION:
        raise RinexAdapterError("convbin output is not exact RINEX 3.04")
    types = _observation_types(obs_path)
    obs_line_counts, obs_satellites = _observation_satellites(obs_path)
    nonzero_counts, nonzero_satellites, nonzero_epochs = (
        _observation_value_inventory(obs_path, types)
    )
    nav_counts, nav_satellites = _navigation_records(nav_path)
    nav_times = _navigation_time_inventory(nav_path)
    epochs = parse_rinex_epochs(obs_path)
    experiment_epoch_ns = tuple(
        epoch.gps_time.week * WEEK_SECONDS * NANOSECONDS
        + epoch.gps_time.sow_nanoseconds
        for epoch in epochs
    )

    per_system: dict[str, dict[str, Any]] = {}
    selected: list[str] = []
    diagnostic_contiguous_slot_counts: list[int] = []
    for system in sorted(set(types) | set(nav_counts), key=lambda item: (
        GINAV_SUPPORTED_SYSTEMS.index(item) if item in GINAV_SUPPORTED_SYSTEMS else 99,
        item,
    )):
        supported = system in GINAV_SUPPORTED_SYSTEMS
        has_obs = bool(obs_satellites.get(system))
        has_nav = nav_counts.get(system, 0) > 0
        matching_satellites = set(obs_satellites.get(system, ())) & set(
            nav_satellites.get(system, ())
        )
        maximum_age = GINAV_MAX_EPHEMERIS_AGE_SECONDS.get(system)
        coverage_by_satellite: dict[str, bool] = {}
        for sat in sorted(matching_satellites):
            source_times = nav_times.get(sat, ())
            coverage_by_satellite[sat] = (
                bool(source_times) and maximum_age is not None
                and all(
                    min(abs(epoch_ns - source_time) for source_time in source_times)
                    <= maximum_age * NANOSECONDS
                    for epoch_ns in experiment_epoch_ns
                )
            )
        slot_inventory = _official_used_slot_inventory(
            system, types.get(system, ()), sorted(matching_satellites),
            nonzero_satellites.get(system, {}), nonzero_epochs.get(system, {}),
            coverage_by_satellite,
        )
        usable_slot_count = int(
            slot_inventory["maximum_contiguous_usable_output_slot_count"]
        )
        nav_epoch_ns = [
            value for sat in matching_satellites for value in nav_times.get(sat, ())
        ]
        source_coverage = bool(slot_inventory["p1_l1_usable_satellites"])
        eligible = (
            supported and has_obs and has_nav and bool(matching_satellites)
            and usable_slot_count >= 1 and source_coverage
        )
        if eligible:
            selected.append(system)
            diagnostic_contiguous_slot_counts.append(usable_slot_count)
        per_system[system] = {
            "name": SYSTEM_NAMES.get(system, "UNKNOWN"),
            "ginav_supported": supported,
            "observation_types": list(types.get(system, ())),
            "official_used_slot_inventory": slot_inventory,
            "code_and_phase_frequency_bands": sorted(
                slot_inventory["usable_output_slot_satellites"]
            ),
            "valid_band_satellites": slot_inventory[
                "usable_output_slot_satellites"
            ],
            "nonzero_observation_counts": nonzero_counts.get(system, {}),
            "observation_record_lines": obs_line_counts.get(system, 0),
            "observed_satellites": list(obs_satellites.get(system, ())),
            "navigation_records": nav_counts.get(system, 0),
            "navigation_satellites": list(nav_satellites.get(system, ())),
            "observation_navigation_satellite_intersection": sorted(matching_satellites),
            "broadcast_toe_record_count_for_matching_satellites": len(nav_epoch_ns),
            "source_ephemeris_time_basis": (
                "GINav_geph.toe_rounded_UTC_Toc_then_UTC_to_GPST"
                if system == "R" else
                "GINav_eph.toe_from_RINEX_broadcast_Toe_and_week"
            ),
            "toc_used_as_ephemeris_age_quantity": False,
            "source_ephemeris_max_age_seconds": maximum_age,
            "source_ephemeris_coverage_by_matching_satellite_all_epochs": (
                coverage_by_satellite
            ),
            "source_ephemeris_coverage_at_every_experiment_epoch": source_coverage,
            "selected_before_navigation": eligible,
            "exclusion_reason": None if eligible else (
                "GINAV_UNSUPPORTED" if not supported else
                "NO_OBSERVATIONS" if not has_obs else
                "NO_BROADCAST_EPHEMERIS" if not has_nav else
                "NO_MATCHING_OBSERVATION_NAVIGATION_SATELLITE" if not matching_satellites else
                "NO_OFFICIAL_POST_ADJOBS_P1_L1_SLOT" if usable_slot_count < 1 else
                "NO_SOURCE_EPHEMERIS_COVERAGE_OVER_EXPERIMENT"
            ),
        }
    if not selected:
        raise RinexAdapterError(
            "no GINav-supported constellation has observations, phase, and broadcast ephemeris"
        )
    diagnostic_maximum_contiguous_slots = min(
        GINAV_MAX_FREQUENCIES, min(diagnostic_contiguous_slot_counts)
    )
    if diagnostic_maximum_contiguous_slots < 1:
        raise RinexAdapterError("selected SPP/TDCP route has no usable slot 1")
    # nfreq is fixed directly by the pinned official config and literal
    # consumers: SPP prange uses P(1), while TDCP uses current/previous L(1).
    # The audited maximum is retained only as a diagnostic and never selects
    # or widens the route.
    nfreq = 1
    selected_navsys = "".join(
        system for system in GINAV_SUPPORTED_SYSTEMS if system in selected
    )
    return {
        "schema_version": "ginav2021.rinex_audit.v1",
        "rinex_version": RINEX_VERSION,
        "epoch_count": len(epochs),
        "epoch_satellite_count_sum": sum(epoch.satellite_count or 0 for epoch in epochs),
        "unique_satellite_count": len({sat for values in obs_satellites.values() for sat in values}),
        "per_system": per_system,
        "selected_navsys": selected_navsys,
        "selected_nfreq": nfreq,
        "selection_rule": (
            "all_GINav_supported_systems_with_source-decoder-selected_post-adjobs_"
            "P(1)_and_L(1)_on_the_same_epoch_plus_previous_L(1)_and_matching_"
            "satellite_Toe_coverage;_"
            "nfreq=1_from_pinned_official_P1_L1_slot_route"
        ),
        "diagnostic_maximum_contiguous_usable_output_slots": (
            diagnostic_maximum_contiguous_slots
        ),
        "diagnostic_maximum_used_for_nfreq_selection": False,
        "diagnostic_maximum_role": "DIAGNOSTIC_ONLY_NOT_NFREQ_SELECTION",
        "selected_nfreq_source": (
            "pinned_official_config_nfreq_1_with_prange_P_1_and_"
            "tdcp_current_previous_L_1_consumers"
        ),
        "official_measurement_slot_semantics": {
            "decoder": "decode_obsh_set_index_decode_data",
            "bds_remap": "adjobs_bd2frq_1_3_2_bd3frq_1_3_4",
            "spp": "prange_P(1)_with_broadcast_ionosphere_config",
            "tdcp": "tdcp2vel_current_and_previous_L(1)",
            "arbitrary_same_band_pairing_used": False,
        },
        "ephemeris_coverage_source": (
            "pinned_GINav_searcheph_searchgeph_decode_eph_decode_geph_"
            "MAXDTOE_and_RINEX_broadcast_Toe"
        ),
        "accuracy_based_constellation_or_frequency_selection": False,
        "observation_sha256": sha256_file(obs_path),
        "navigation_sha256": sha256_file(nav_path),
    }


def convert_gnss1_raw_to_rinex(
    gnss1_raw_csv: str | Path,
    *,
    rtklib_root: str | Path,
    convbin: str | Path,
    output_root: str | Path,
    ledger: AccessLedger | None = None,
) -> dict[str, Any]:
    source = Path(gnss1_raw_csv).resolve(strict=True)
    assert_gnss1_only_path(source)
    destination = Path(output_root).resolve(strict=False)
    if destination.exists():
        raise RinexAdapterError(f"GNSS adapter output root already exists: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    converter = verify_converter_identity(rtklib_root, convbin)
    if ledger is not None:
        ledger.record(source, role="GNSS1_RAWX_SFRBX_SOURCE")
        ledger.record(convbin, role="PINNED_CONVBIN_EXECUTABLE", operation="execute")

    ubx_path = destination / "BY2_GNSS1.ubx"
    obs_path = destination / "BY2_GNSS1.rnx"
    nav_path = destination / "BY2_GNSS1.nav"
    reconstructed = reconstruct_ubx_stream(
        source, ubx_path, decode_nav_hpposecef_semantics=False
    )
    command = build_convbin_command(convbin, ubx_path, obs_path, nav_path)
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    runtime = time.monotonic() - started
    if result.returncode != 0:
        raise RinexAdapterError(
            f"convbin failed ({result.returncode}): {result.stderr.strip()}"
        )
    if not obs_path.is_file() or not nav_path.is_file():
        raise RinexAdapterError("convbin did not produce both observation and navigation RINEX")
    audit = audit_rinex_pair(obs_path, nav_path)
    if len(reconstructed.rawx_epochs) != audit["epoch_count"]:
        raise RinexAdapterError(
            "RAWX-to-RINEX epoch conservation failed: "
            f"{len(reconstructed.rawx_epochs)} != {audit['epoch_count']}"
        )
    rawx_measurements = sum(len(epoch.measurements) for epoch in reconstructed.rawx_epochs)
    ubx_inventory = inventory_ubx_message_roles(
        reconstructed.message_counts,
        discarded_byte_count=reconstructed.discarded_byte_count,
        checksum_failure_count=reconstructed.checksum_failure_count,
    )
    return {
        "schema_version": "ginav2021.gnss1_rinex_adapter.v1",
        "source_role": "GNSS1_RAWX_SFRBX_ONLY",
        "source_path": str(source),
        "source_sha256": sha256_file(source),
        "source_bytes": source.stat().st_size,
        "input_cell_count": reconstructed.input_cell_count,
        "checksum_valid_message_counts": reconstructed.message_counts,
        "discarded_byte_count": reconstructed.discarded_byte_count,
        "checksum_failure_count": reconstructed.checksum_failure_count,
        "ubx_message_class_inventory": ubx_inventory,
        "rawx_epoch_count": len(reconstructed.rawx_epochs),
        "rawx_measurement_count": rawx_measurements,
        "sfrbx_message_count": len(reconstructed.sfrbx_messages),
        "nav_hpposecef_semantic_decode_enabled": (
            reconstructed.nav_hpposecef_semantic_decode_enabled
        ),
        "external_pvt_measurement_interface_used": False,
        "converter": converter,
        "command": list(command),
        "command_has_interval_filter": "-ti" in command,
        "command_has_system_exclusion": "-y" in command,
        "command_has_signal_mask": "-mask" in command or "-nomask" in command,
        "runtime_seconds": runtime,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ubx_path": str(ubx_path),
        "ubx_sha256": sha256_file(ubx_path),
        "observation_path": str(obs_path),
        "navigation_path": str(nav_path),
        "rinex": audit,
        "gnss2_open_count": 0,
        "trace_open_count": 0,
        "reference_open_count": 0,
        "old_runtime_input_count": 0,
        "pass": True,
    }


def epoch_signal_rows(audit: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = []
    per_system = audit.get("per_system")
    if not isinstance(per_system, Mapping):
        raise RinexAdapterError("RINEX audit has no per-system mapping")
    for system, item in per_system.items():
        if not isinstance(item, Mapping):
            raise RinexAdapterError("invalid per-system RINEX audit row")
        rows.append(
            {
                "system": system,
                "system_name": item.get("name"),
                "ginav_supported": item.get("ginav_supported"),
                "selected": item.get("selected_before_navigation"),
                "observation_types": ";".join(item.get("observation_types", [])),
                "common_code_phase_bands": ";".join(
                    item.get("code_and_phase_frequency_bands", [])
                ),
                "observation_record_lines": item.get("observation_record_lines"),
                "observed_satellite_count": len(item.get("observed_satellites", [])),
                "navigation_record_count": item.get("navigation_records"),
                "navigation_satellite_count": len(item.get("navigation_satellites", [])),
                "exclusion_reason": item.get("exclusion_reason"),
            }
        )
    return tuple(rows)
