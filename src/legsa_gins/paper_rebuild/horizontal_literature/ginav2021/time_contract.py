"""GPS/UTC conversion and the no-search noninteger-epoch contract."""

from __future__ import annotations

import calendar
import dataclasses
import datetime as dt
import decimal
import math
import re
import struct
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..shared_raw_backend import decode_rawx, iter_ubx_frames


class TimeContractError(ValueError):
    pass


GPS_EPOCH_UNIX_SECONDS = 315964800
WEEK_SECONDS = 604800
NANOSECONDS = 1_000_000_000

# UTC effective instants at which GPST-UTC increased, after the GPS epoch.
_LEAP_EFFECTIVE_UNIX = tuple(
    calendar.timegm(value)
    for value in (
        (1981, 7, 1, 0, 0, 0), (1982, 7, 1, 0, 0, 0),
        (1983, 7, 1, 0, 0, 0), (1985, 7, 1, 0, 0, 0),
        (1988, 1, 1, 0, 0, 0), (1990, 1, 1, 0, 0, 0),
        (1991, 1, 1, 0, 0, 0), (1992, 7, 1, 0, 0, 0),
        (1993, 7, 1, 0, 0, 0), (1994, 7, 1, 0, 0, 0),
        (1996, 1, 1, 0, 0, 0), (1997, 7, 1, 0, 0, 0),
        (1999, 1, 1, 0, 0, 0), (2006, 1, 1, 0, 0, 0),
        (2009, 1, 1, 0, 0, 0), (2012, 7, 1, 0, 0, 0),
        (2015, 7, 1, 0, 0, 0), (2017, 1, 1, 0, 0, 0),
    )
)


def gps_utc_leap_seconds(unix_seconds: int) -> int:
    return sum(unix_seconds >= threshold for threshold in _LEAP_EFFECTIVE_UNIX)


@dataclasses.dataclass(frozen=True)
class GpsTime:
    week: int
    sow_nanoseconds: int

    @property
    def sow_seconds(self) -> float:
        return self.sow_nanoseconds / NANOSECONDS


def utc_unix_ns_to_gps(unix_nanoseconds: int) -> GpsTime:
    unix_seconds = unix_nanoseconds // NANOSECONDS
    leap = gps_utc_leap_seconds(unix_seconds)
    gps_nanoseconds = (
        unix_nanoseconds
        - GPS_EPOCH_UNIX_SECONDS * NANOSECONDS
        + leap * NANOSECONDS
    )
    if gps_nanoseconds < 0:
        raise TimeContractError("timestamp predates the GPS epoch")
    week_ns = WEEK_SECONDS * NANOSECONDS
    week, sow_ns = divmod(gps_nanoseconds, week_ns)
    return GpsTime(int(week), int(sow_ns))


def gps_to_utc_unix_ns(week: int, sow_nanoseconds: int) -> int:
    if week < 0 or not 0 <= sow_nanoseconds < WEEK_SECONDS * NANOSECONDS:
        raise TimeContractError("invalid GPS week/SOW")
    gps_ns = (week * WEEK_SECONDS * NANOSECONDS) + sow_nanoseconds
    for leap in range(len(_LEAP_EFFECTIVE_UNIX), -1, -1):
        candidate = gps_ns + GPS_EPOCH_UNIX_SECONDS * NANOSECONDS - leap * NANOSECONDS
        if gps_utc_leap_seconds(candidate // NANOSECONDS) == leap:
            return candidate
    raise TimeContractError("GPS/UTC leap-second inversion failed")


def gpst_calendar_to_gps(
    year: int, month: int, day: int, hour: int, minute: int,
    second: decimal.Decimal,
) -> GpsTime:
    whole = int(second // 1)
    fraction = second - decimal.Decimal(whole)
    base = dt.datetime(year, month, day, hour, minute, whole, tzinfo=dt.timezone.utc)
    seconds = calendar.timegm(base.utctimetuple()) - GPS_EPOCH_UNIX_SECONDS
    nanos = seconds * NANOSECONDS + int(
        (fraction * NANOSECONDS).to_integral_value(rounding=decimal.ROUND_HALF_EVEN)
    )
    week, sow_ns = divmod(nanos, WEEK_SECONDS * NANOSECONDS)
    return GpsTime(int(week), int(sow_ns))


def gps_to_gpst_calendar(value: GpsTime) -> tuple[int, int, int, int, int, decimal.Decimal]:
    total_ns = value.week * WEEK_SECONDS * NANOSECONDS + value.sow_nanoseconds
    whole, fraction_ns = divmod(total_ns, NANOSECONDS)
    instant = dt.datetime.fromtimestamp(
        GPS_EPOCH_UNIX_SECONDS + whole, tz=dt.timezone.utc
    )
    second = decimal.Decimal(instant.second) + decimal.Decimal(fraction_ns) / NANOSECONDS
    return instant.year, instant.month, instant.day, instant.hour, instant.minute, second


RINEX_EPOCH_RE = re.compile(
    r"^(?P<lead>>\s+)(?P<year>\d{4})\s+(?P<month>\d{1,2})\s+"
    r"(?P<day>\d{1,2})\s+(?P<hour>\d{1,2})\s+(?P<minute>\d{1,2})\s+"
    r"(?P<second>\d{1,2}(?:\.\d+)?)(?P<suffix>.*)$"
)


@dataclasses.dataclass(frozen=True)
class RinexEpoch:
    index: int
    line_number: int
    raw_line: str
    gps_time: GpsTime
    second_text: str
    fractional_nanoseconds: int
    event_flag: int | None
    satellite_count: int | None

    @property
    def accepted_by_official_processor(self) -> bool:
        return self.fractional_nanoseconds == 0


def parse_rinex_epochs(path: str | Path) -> tuple[RinexEpoch, ...]:
    epochs: list[RinexEpoch] = []
    with Path(path).open("r", encoding="ascii", errors="strict", newline="") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.startswith(">"):
                continue
            line = raw.rstrip("\r\n")
            match = RINEX_EPOCH_RE.match(line)
            if match is None:
                raise TimeContractError(f"malformed RINEX 3 epoch line {line_number}")
            second = decimal.Decimal(match.group("second"))
            gps = gpst_calendar_to_gps(
                int(match.group("year")), int(match.group("month")),
                int(match.group("day")), int(match.group("hour")),
                int(match.group("minute")), second,
            )
            fractional_ns = gps.sow_nanoseconds % NANOSECONDS
            suffix_tokens = match.group("suffix").split()
            event_flag = int(suffix_tokens[0]) if suffix_tokens else None
            satellite_count = int(suffix_tokens[1]) if len(suffix_tokens) > 1 else None
            epochs.append(
                RinexEpoch(
                    index=len(epochs), line_number=line_number, raw_line=line,
                    gps_time=gps, second_text=match.group("second"),
                    fractional_nanoseconds=fractional_ns,
                    event_flag=event_flag, satellite_count=satellite_count,
                )
            )
    if not epochs:
        raise TimeContractError("RINEX observation file has no version-3 epochs")
    return tuple(epochs)


def official_epoch_acceptance_audit(epochs: Sequence[RinexEpoch]) -> dict[str, Any]:
    accepted = sum(epoch.accepted_by_official_processor for epoch in epochs)
    fractions: dict[str, int] = {}
    for epoch in epochs:
        key = f"{epoch.fractional_nanoseconds / NANOSECONDS:.9f}"
        fractions[key] = fractions.get(key, 0) + 1
    return {
        "schema_version": "ginav2021.official_epoch_acceptance_audit.v1",
        "official_source_predicate": "obsr_(1).time.sec~=0_is_rejected",
        "input_epoch_count": len(epochs),
        "literal_accepted_epoch_count": accepted,
        "literal_rejected_noninteger_epoch_count": len(epochs) - accepted,
        "deleted_epoch_count": 0,
        "accepted_plus_rejected_equals_input": (
            accepted + (len(epochs) - accepted) == len(epochs)
        ),
        "accepted_rejected_deleted_row_conservation_pass": (
            accepted + (len(epochs) - accepted) + 0 == len(epochs)
        ),
        "fractional_second_histogram": dict(sorted(fractions.items())),
        "full_navigation_run_used_for_inventory": False,
    }


@dataclasses.dataclass(frozen=True)
class RawxTime:
    sequence: int
    week: int
    tow_nanoseconds: int


@dataclasses.dataclass(frozen=True)
class NavPvtTime:
    sequence: int
    itow_milliseconds: int
    fully_resolved: bool
    valid_date: bool = True
    valid_time: bool = True

    @property
    def authoritative(self) -> bool:
        return self.valid_date and self.valid_time and self.fully_resolved

    @property
    def semantic_signature(self) -> tuple[int, bool, bool, bool]:
        return (
            self.itow_milliseconds,
            self.valid_date,
            self.valid_time,
            self.fully_resolved,
        )


def extract_same_receiver_time_events(stream: bytes) -> tuple[tuple[RawxTime, ...], tuple[NavPvtTime, ...]]:
    """Decode RAWX time and NAV-PVT iTOW only; no PVT state is materialized."""

    rawx: list[RawxTime] = []
    pvt: list[NavPvtTime] = []
    for sequence, (msg_class, msg_id, payload) in enumerate(iter_ubx_frames(stream)):
        if (msg_class, msg_id) == (0x02, 0x15):
            epoch = decode_rawx(payload)
            tow_ns = int(round(epoch.gps_tow_seconds * NANOSECONDS))
            rawx.append(RawxTime(sequence, epoch.gps_week, tow_ns))
        elif (msg_class, msg_id) == (0x01, 0x07):
            if len(payload) < 12:
                raise TimeContractError("NAV-PVT time header is truncated")
            itow_ms = struct.unpack_from("<I", payload, 0)[0]
            valid = payload[11]
            # UBX-NAV-PVT validDate, validTime, and fullyResolved must all be
            # asserted before its iTOW can serve as the authoritative
            # same-receiver integer GNSS epoch.
            pvt.append(
                NavPvtTime(
                    sequence=sequence,
                    itow_milliseconds=itow_ms,
                    fully_resolved=bool(valid & 0x04),
                    valid_date=bool(valid & 0x01),
                    valid_time=bool(valid & 0x02),
                )
            )
    return tuple(rawx), tuple(pvt)


def associate_nav_pvt_by_stream_order(
    rawx_times: Sequence[RawxTime],
    nav_pvt_times: Sequence[NavPvtTime],
) -> dict[str, Any]:
    """Associate authoritative NAV-PVT messages by causal receiver-stream order.

    The window for RAWX ``i`` is strictly after its message sequence and strictly
    before the next RAWX sequence.  The final RAWX window ends at EOF.  Messages
    at or before the first RAWX are intentionally ignored.  Within a window,
    semantic duplicates are canonicalized to the minimum message sequence;
    distinct semantic signatures are a conflict, not a selection opportunity.
    """

    if any(
        later.sequence <= earlier.sequence
        for earlier, later in zip(rawx_times, rawx_times[1:])
    ):
        raise TimeContractError("RAWX message sequences are not strictly increasing")
    ordered_pvt = tuple(sorted(nav_pvt_times, key=lambda item: item.sequence))
    if tuple(item.sequence for item in ordered_pvt) != tuple(
        item.sequence for item in nav_pvt_times
    ):
        raise TimeContractError("NAV-PVT message sequences are not ordered")

    rows: list[dict[str, Any]] = []
    selected: list[NavPvtTime | None] = []
    counts = {
        "unique_association_count": 0,
        "semantic_duplicate_association_count": 0,
        "conflicting_association_count": 0,
        "missing_association_count": 0,
    }
    first_sequence = rawx_times[0].sequence if rawx_times else None
    pre_first = sum(
        first_sequence is not None and item.sequence <= first_sequence
        for item in ordered_pvt
    )
    for index, rawx in enumerate(rawx_times):
        upper = rawx_times[index + 1].sequence if index + 1 < len(rawx_times) else None
        candidates = tuple(
            item for item in ordered_pvt
            if item.authoritative
            and item.sequence > rawx.sequence
            and (upper is None or item.sequence < upper)
        )
        signatures: dict[tuple[int, bool, bool, bool], list[NavPvtTime]] = {}
        for item in candidates:
            signatures.setdefault(item.semantic_signature, []).append(item)
        canonical: NavPvtTime | None = None
        if not signatures:
            classification = "MISSING"
            counts["missing_association_count"] += 1
        elif len(signatures) > 1:
            classification = "CONFLICT"
            counts["conflicting_association_count"] += 1
        else:
            synonymous = next(iter(signatures.values()))
            canonical = min(synonymous, key=lambda item: item.sequence)
            if len(synonymous) == 1:
                classification = "UNIQUE"
                counts["unique_association_count"] += 1
            else:
                classification = "SEMANTIC_DUPLICATE"
                counts["semantic_duplicate_association_count"] += 1
        selected.append(canonical)
        rows.append(
            {
                "rawx_index": index,
                "rawx_message_sequence": rawx.sequence,
                "window_upper_rawx_message_sequence_exclusive": upper,
                "window_ends_at_eof": upper is None,
                "authoritative_candidate_count": len(candidates),
                "semantic_signature_count": len(signatures),
                "classification": classification,
                "candidate_message_sequences": [item.sequence for item in candidates],
                "candidate_semantic_signatures": [
                    {
                        "itow_milliseconds": signature[0],
                        "valid_date": signature[1],
                        "valid_time": signature[2],
                        "fully_resolved": signature[3],
                    }
                    for signature in sorted(signatures)
                ],
                "canonical_message_sequence": (
                    canonical.sequence if canonical is not None else None
                ),
                "canonicalization_rule": (
                    "minimum_message_sequence_within_single_semantic_signature"
                    if canonical is not None else None
                ),
            }
        )
    return {
        "schema_version": "ginav2021.nav_pvt_stream_order_association.v1",
        "association_rule": "RAWX_seq_i_lt_NAV_PVT_seq_lt_next_RAWX_seq_or_EOF",
        "candidate_validity_rule": "validDate_and_validTime_and_fullyResolved",
        "semantic_signature_fields": [
            "iTOW", "validDate", "validTime", "fullyResolved"
        ],
        "canonicalization_rule": (
            "minimum_message_sequence_within_single_semantic_signature"
        ),
        "pre_first_nav_pvt_ignored_count": pre_first,
        **counts,
        "rawx_epoch_count": len(rawx_times),
        "classified_epoch_count": sum(counts.values()),
        "classification_conservation_pass": sum(counts.values()) == len(rawx_times),
        "rows": rows,
        "selected": tuple(selected),
    }


def _signed_modulo_week_nanoseconds(delta_nanoseconds: int) -> int:
    week_ns = WEEK_SECONDS * NANOSECONDS
    half_week_ns = week_ns // 2
    return int((delta_nanoseconds + half_week_ns) % week_ns - half_week_ns)


def prove_single_constant_normalization(
    rawx_times: Sequence[RawxTime],
    nav_pvt_times: Sequence[NavPvtTime],
    rinex_epochs: Sequence[RinexEpoch],
) -> dict[str, Any]:
    """Prove one constant RAWX→same-receiver integer-grid relation.

    Pairing is preregistered by causal same-stream order.  A RAWX owns valid
    NAV-PVT messages after it and before the next RAWX (or EOF for the last
    epoch).  Synonymous duplicates are canonicalized by minimum sequence.
    Distinct semantic signatures and missing windows fail closed.  No candidate
    offsets are enumerated or scored.
    """

    if len(rawx_times) != len(rinex_epochs):
        raise TimeContractError(
            f"RAWX/RINEX epoch conservation failed: {len(rawx_times)} != {len(rinex_epochs)}"
        )
    if not any(item.authoritative for item in nav_pvt_times):
        raise TimeContractError("no fully-resolved same-receiver NAV-PVT iTOW epochs")
    association = associate_nav_pvt_by_stream_order(rawx_times, nav_pvt_times)
    if association["missing_association_count"]:
        first = next(
            row["rawx_index"] for row in association["rows"]
            if row["classification"] == "MISSING"
        )
        raise TimeContractError(
            f"authoritative row-level NAV-PVT association is missing for RAWX index {first}"
        )
    if association["conflicting_association_count"]:
        first = next(
            row["rawx_index"] for row in association["rows"]
            if row["classification"] == "CONFLICT"
        )
        raise TimeContractError(
            "authoritative row-level NAV-PVT association has conflicting semantic "
            f"signatures for RAWX index {first}"
        )
    ledger: list[dict[str, Any]] = []
    offsets: set[int] = set()
    for rawx, rinex in zip(rawx_times, rinex_epochs, strict=True):
        nav_pvt = association["selected"][rinex.index]
        assert nav_pvt is not None
        normalized_ns = nav_pvt.itow_milliseconds * 1_000_000
        if rawx.week != rinex.gps_time.week or abs(
            rawx.tow_nanoseconds - rinex.gps_time.sow_nanoseconds
        ) > 100:
            raise TimeContractError(
                f"RAWX/RINEX timestamp mismatch at epoch {rinex.index}"
            )
        offset_ns = _signed_modulo_week_nanoseconds(
            normalized_ns - rawx.tow_nanoseconds
        )
        offsets.add(offset_ns)
        ledger.append(
            {
                "epoch_index": rinex.index,
                "gps_week": rawx.week,
                "rawx_sow_seconds": f"{rawx.tow_nanoseconds / NANOSECONDS:.9f}",
                "rinex_original_sow_seconds": f"{rinex.gps_time.sow_seconds:.9f}",
                "authoritative_message": "UBX_NAV_PVT_iTOW_fullyResolved",
                "rawx_message_sequence": rawx.sequence,
                "authoritative_message_sequence": nav_pvt.sequence,
                "message_sequence_delta": nav_pvt.sequence - rawx.sequence,
                "association_classification": association["rows"][rinex.index][
                    "classification"
                ],
                "authoritative_candidate_count": association["rows"][rinex.index][
                    "authoritative_candidate_count"
                ],
                "semantic_signature_count": association["rows"][rinex.index][
                    "semantic_signature_count"
                ],
                "authoritative_nav_pvt_sow_seconds": f"{normalized_ns / NANOSECONDS:.9f}",
                "normalization_offset_nanoseconds": offset_ns,
                "normalized_sow_seconds": f"{normalized_ns / NANOSECONDS:.9f}",
            }
        )
    if len(offsets) != 1:
        raise TimeContractError(
            "RAWX-to-authoritative normalization is not one exact constant"
        )
    constant = next(iter(offsets))
    return {
        "schema_version": "ginav2021.time_normalization_contract.v2",
        "relation_proven_for_every_selected_epoch": True,
        "pairing_rule": (
            "causal_RAWX_to_next_RAWX_or_EOF_window_single_semantic_signature_"
            "canonical_minimum_NAV_PVT_message_sequence"
        ),
        "association_audit": {
            key: value for key, value in association.items() if key != "selected"
        },
        "candidate_offset_search_performed": False,
        "constant_offset_nanoseconds": constant,
        "constant_offset_seconds": constant / NANOSECONDS,
        "selected_epoch_count": len(ledger),
        "original_timestamps_retained": True,
        "normalized_timestamps_retained": True,
        "ledger": ledger,
    }


def five_phase_row_conservation_audit(
    *,
    rawx_epoch_count: int,
    original_rinex_epochs: Sequence[RinexEpoch],
    proof: Mapping[str, Any],
    normalized_rows: Sequence[Mapping[str, Any]],
    selected_rinex_epochs: Sequence[RinexEpoch],
) -> dict[str, Any]:
    counts = {
        "phase_1_rawx_epoch_count": rawx_epoch_count,
        "phase_2_original_rinex_epoch_count": len(original_rinex_epochs),
        "phase_3_association_ledger_row_count": len(proof.get("ledger", ())),
        "phase_4_normalized_rinex_row_count": len(normalized_rows),
        "phase_5_selected_rinex_retained_epoch_count": len(selected_rinex_epochs),
    }
    expected = rawx_epoch_count
    order_preserved = all(
        int(row.get("epoch_index", -1)) == index
        for index, row in enumerate(normalized_rows)
    )
    accepted = sum(
        epoch.accepted_by_official_processor for epoch in selected_rinex_epochs
    )
    return {
        "schema_version": "ginav2021.five_phase_row_conservation.v1",
        **counts,
        "all_five_phase_counts_equal": all(value == expected for value in counts.values()),
        "normalized_epoch_order_preserved": order_preserved,
        "selected_rinex_official_accepted_count": accepted,
        "selected_rinex_official_rejected_count": len(selected_rinex_epochs) - accepted,
        "accepted_plus_rejected_equals_input": (
            accepted + (len(selected_rinex_epochs) - accepted) == expected
        ),
        "deleted_or_merged_epoch_count": 0,
        "pass": (
            all(value == expected for value in counts.values())
            and order_preserved
            and accepted + (len(selected_rinex_epochs) - accepted) == expected
        ),
    }


def normalize_rinex_epochs(
    source: str | Path,
    destination: str | Path,
    proof: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    if proof.get("candidate_offset_search_performed") is not False:
        raise TimeContractError("time proof permits offset search")
    constant_ns = proof.get("constant_offset_nanoseconds")
    ledger = proof.get("ledger")
    if not isinstance(constant_ns, int) or not isinstance(ledger, Sequence):
        raise TimeContractError("time-normalization proof is incomplete")
    epochs = parse_rinex_epochs(source)
    if len(epochs) != len(ledger):
        raise TimeContractError("time-normalization ledger length mismatch")
    ledger_by_line = {epoch.line_number: (epoch, ledger[epoch.index]) for epoch in epochs}
    output_lines: list[str] = []
    normalized_rows: list[dict[str, Any]] = []
    with Path(source).open("r", encoding="ascii", newline="") as handle:
        for line_number, raw in enumerate(handle, start=1):
            item = ledger_by_line.get(line_number)
            if item is None:
                output_lines.append(raw)
                continue
            epoch, proof_row = item
            normalized = GpsTime(
                epoch.gps_time.week,
                epoch.gps_time.sow_nanoseconds + constant_ns,
            )
            if not 0 <= normalized.sow_nanoseconds < WEEK_SECONDS * NANOSECONDS:
                total = (
                    epoch.gps_time.week * WEEK_SECONDS * NANOSECONDS
                    + epoch.gps_time.sow_nanoseconds + constant_ns
                )
                week, sow_ns = divmod(total, WEEK_SECONDS * NANOSECONDS)
                normalized = GpsTime(int(week), int(sow_ns))
            year, month, day, hour, minute, second = gps_to_gpst_calendar(normalized)
            match = RINEX_EPOCH_RE.match(epoch.raw_line)
            assert match is not None
            newline = "\r\n" if raw.endswith("\r\n") else "\n" if raw.endswith("\n") else ""
            rewritten = (
                f"> {year:04d} {month:02d} {day:02d} {hour:02d} {minute:02d} "
                f"{float(second):10.7f}{match.group('suffix')}{newline}"
            )
            output_lines.append(rewritten)
            normalized_rows.append(
                {
                    **dict(proof_row),
                    "rinex_line_number": line_number,
                    "normalized_gps_week": normalized.week,
                    "normalized_rinex_sow_seconds": f"{normalized.sow_seconds:.9f}",
                    "official_fractional_nanoseconds_after": (
                        normalized.sow_nanoseconds % NANOSECONDS
                    ),
                    "accepted_by_official_processor_after": (
                        normalized.sow_nanoseconds % NANOSECONDS == 0
                    ),
                }
            )
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(output_lines), encoding="ascii", newline="")
    post = parse_rinex_epochs(target)
    if len(post) != len(epochs) or len(normalized_rows) != len(epochs):
        raise TimeContractError("normalization deleted or merged RINEX epochs")
    for index, (before, after, row) in enumerate(
        zip(epochs, post, normalized_rows, strict=True)
    ):
        if before.index != index or after.index != index or row["epoch_index"] != index:
            raise TimeContractError("normalization changed RINEX epoch order")
        before_total = (
            before.gps_time.week * WEEK_SECONDS * NANOSECONDS
            + before.gps_time.sow_nanoseconds
        )
        after_total = (
            after.gps_time.week * WEEK_SECONDS * NANOSECONDS
            + after.gps_time.sow_nanoseconds
        )
        if after_total - before_total != constant_ns:
            raise TimeContractError(
                f"normalization per-row shift mismatch at epoch {index}"
            )
        if row["official_fractional_nanoseconds_after"] != after.fractional_nanoseconds:
            raise TimeContractError(
                f"normalization fractional-second audit mismatch at epoch {index}"
            )
        if row["accepted_by_official_processor_after"] != after.accepted_by_official_processor:
            raise TimeContractError(
                f"normalization official-eligibility audit mismatch at epoch {index}"
            )
    for row in normalized_rows:
        row.update(
            {
                "normalization_retained_epoch_count": len(post),
                "normalization_deleted_or_merged_epoch_count": 0,
                "normalization_order_preserved": True,
                "normalization_per_row_shift_verified": True,
            }
        )
    return tuple(normalized_rows)
