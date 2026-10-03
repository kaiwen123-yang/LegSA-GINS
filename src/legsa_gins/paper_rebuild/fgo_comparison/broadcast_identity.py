"""FGO-only, pre-RTKLIB clock-identity gate for existing RINEX-3 navigation.

The physical key is (satellite, absolute GPST toc/toe, IODE/AODE, IODC/AODC,
all 15 orbital parameters). Transmission time, file order and receiver are
not identity or quality criteria. Conflicting af0/af1/af2 values cannot be
resolved by RTKLIB's closest-Toe/last-tie selection, residuals or majority.

No navigation file is changed. Before any satellite-state or coarse-SPP call,
reject observations whose nearest applicable original Toe includes a
conflicting key. Equal-Toe alternatives cannot rescue such an observation.
For any satellite with a conflict, also inspect the existing bridge's actual
post-uniqnav selection: uniqeph can discard a nearer legal record with the
same IODE. Its selected (satellite, toc, toe, IODE) must not project to any
ambiguous full key. A strictly closer legal key is usable only if this second
check passes. No records are deleted and no fallback selection is invented.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path


GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
ORBIT_INDICES = tuple(range(4, 11)) + tuple(range(12, 20))
ORBIT_NAMES = ("Crs", "delta_n", "M0", "Cuc", "e", "Cus", "sqrt_A",
               "Cic", "Omega0", "Cis", "i0", "Crc", "omega", "Omega_dot", "i_dot")
# RTKLIB 180043ee rcvraw.c decode GPS frame1 / BeiDou D1 and D2 clocks;
# rtklib.h MAXDTOE/MAXDTOE_CMP plus seleph's one-second margin.
CLOCK_LSB_POWERS = {"G": (-31, -43, -55), "C": (-33, -50, -66)}
MAX_TOE_AGE_S = {"G": 7201.0, "C": 21601.0}


@dataclass(frozen=True)
class NavigationRecord:
    satellite: str
    toc_gpst_s: float
    toe_gpst_s: float
    iode: int
    iodc: int
    orbit: tuple
    clock: tuple
    clock_resolution: tuple
    source_name: str
    source_line_1based: int
    transmission_time_field_s: float
    record_sha256: str

    @property
    def key(self):
        return (self.satellite, self.toc_gpst_s, self.toe_gpst_s,
                self.iode, self.iodc, self.orbit)

    def physical_identity(self):
        return {"satellite": self.satellite, "toc_gpst_seconds_since_1980": self.toc_gpst_s,
                "toe_gpst_seconds_since_1980": self.toe_gpst_s, "iode_aode": self.iode,
                "iodc_aodc": self.iodc,
                "orbital_fields": dict(zip(ORBIT_NAMES, (str(value.normalize()) for value in self.orbit)))}


def _decimal(text):
    value = Decimal(text.strip().replace("D", "E").replace("d", "e") or "0")
    if not value.is_finite():
        raise ValueError("NONFINITE_RINEX_NAVIGATION_FIELD")
    return value


def read_navigation(path):
    """Read the GPS/BDS records before RTKLIB merges or de-duplicates them."""
    path = Path(path)
    lines = path.read_text(encoding="ascii").splitlines(keepends=True)
    if not lines or not 3.0 <= float(lines[0][:9]) < 4.0:
        raise ValueError("BROADCAST_GATE_REQUIRES_RINEX_3")
    headers = [i for i, line in enumerate(lines) if "END OF HEADER" in line]
    if len(headers) != 1:
        raise ValueError("INVALID_RINEX_NAVIGATION_HEADER")
    records, i = [], headers[0] + 1
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        satellite = lines[i][:3]
        if satellite[0] not in "GRECJSI" or not satellite[1:].isdigit():
            raise ValueError(f"INVALID_RINEX_NAVIGATION_RECORD:{path.name}:{i + 1}")
        count = 4 if satellite[0] in "RS" else 8
        block = lines[i:i + count]
        if len(block) != count:
            raise ValueError("TRUNCATED_RINEX_NAVIGATION_RECORD")
        if satellite[0] in CLOCK_LSB_POWERS:
            text = [block[0][23 + j * 19:42 + j * 19] for j in range(3)]
            text += [line[4 + j * 19:23 + j * 19] for line in block[1:] for j in range(4)]
            data = tuple(_decimal(value) for value in text)
            calendar = block[0][3:23].split()
            if len(calendar) != 6:
                raise ValueError("INVALID_RINEX_TOC")
            date = datetime(*map(int, calendar[:5]), tzinfo=timezone.utc) + timedelta(seconds=float(calendar[5]))
            bds = satellite[0] == "C"
            shift = 14 if bds else 0
            toc = (date - GPS_EPOCH).total_seconds() + shift
            toe = (int(data[21]) + (1356 if bds else 0)) * 604800.0 + float(data[11]) + shift
            if toe - toc > 302400.0:
                toe -= 604800.0
            elif toe - toc < -302400.0:
                toe += 604800.0
            resolution = tuple(Decimal(10) ** value.as_tuple().exponent for value in data[:3])
            # An exactly encoded zero has no rounding ambiguity. Treating
            # 0.000D+00's display precision as clock uncertainty would mask af2.
            resolution = tuple(Decimal(0) if value == 0 else unit
                               for value, unit in zip(data[:3], resolution))
            records.append(NavigationRecord(satellite, toc, toe, int(data[3]),
                int(data[28] if bds else data[26]), tuple(data[j] for j in ORBIT_INDICES),
                data[:3], resolution, path.name, i + 1, float(data[27]),
                hashlib.sha256("".join(block).encode("ascii")).hexdigest()))
        i += count
    return records


class BroadcastClockGate:
    """Immutable conflict decisions derived only from source navigation."""
    def __init__(self, records):
        self.records = tuple(records)
        groups, self.by_satellite = defaultdict(list), defaultdict(list)
        for record in self.records:
            groups[record.key].append(record)
            self.by_satellite[record.satellite].append(record)
        self.conflict_ids, conflicts = {}, []
        for key, group in groups.items():
            representative = group[0]
            tolerances = tuple(Decimal(2) ** power + max(r.clock_resolution[j] for r in group)
                               for j, power in enumerate(CLOCK_LSB_POWERS[representative.satellite[0]]))
            spreads = tuple(max(r.clock[j] for r in group) - min(r.clock[j] for r in group) for j in range(3))
            differing = [f"af{j}" for j in range(3) if spreads[j] > tolerances[j]]
            if not differing:
                continue
            identity = representative.physical_identity()
            key_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            self.conflict_ids[key] = key_id
            conflicts.append({"physical_key_sha256": key_id, "physical_identity": identity,
                "conflicting_clock_fields": differing,
                "clock_spread": dict(zip(("af0_s", "af1_sps", "af2_sps2"), map(float, spreads))),
                "clock_tolerance": dict(zip(("af0_s", "af1_sps", "af2_sps2"), map(float, tolerances))),
                "records": sorted([{"source_name": r.source_name, "source_line_1based": r.source_line_1based,
                    "clock_decimal": list(map(str, r.clock)), "record_sha256": r.record_sha256,
                    "transmission_time_field_s": r.transmission_time_field_s} for r in group],
                    key=lambda r: (r["source_name"], r["source_line_1based"], r["record_sha256"]))})
        self.conflicts_by_selection = defaultdict(set)
        for key, key_id in self.conflict_ids.items():
            self.conflicts_by_selection[key[:4]].add(key_id)
        self.conflicted_satellites = {key[0] for key in self.conflict_ids}
        self.report = {"policy": "REJECT_AMBIGUOUS_CLOCK_PHYSICAL_KEY_BEFORE_ANY_NATIVE_INPUT",
            "source_navigation_record_count": len(self.records), "physical_key_count": len(groups),
            "conflicting_physical_key_count": len(conflicts),
            "conflicts": sorted(conflicts, key=lambda row: row["physical_key_sha256"]),
            "clock_tolerance_definition": "one public broadcast LSB plus one maximum RINEX decimal resolution per coefficient",
            "clock_lsb_powers_of_two": {key: list(value) for key, value in CLOCK_LSB_POWERS.items()},
            "maximum_toe_age_s": MAX_TOE_AGE_S,
            "dependency_rule": "reject any conflicting nearest original Toe candidate or actual post-uniqnav selected projection; equal-Toe alternatives cannot rescue",
            "actual_selection_api": "RtklibBroadcastProvider.ephemeris_audit at receiver GPST; no state or solver call",
            "actual_selection_projection": "satellite, absolute GPST toc/toe, IODE; reject if any matching full physical key conflicts because ABI omits IODC/orbit",
            "navigation_records_removed": 0, "fallback_after_conflict": False,
            "reference_or_residual_used": False, "receiver_or_repetition_priority_used": False}

    @classmethod
    def from_paths(cls, paths):
        return cls(record for path in paths for record in read_navigation(path))

    def has_conflicts(self, satellite):
        return satellite in self.conflicted_satellites

    @staticmethod
    def selected_identity(satellite, audit):
        """Expose only the source-selection metadata returned by the bridge."""
        return {"satellite": satellite,
                "toc_gpst_seconds_since_1980": int(audit.toc_gps_week) * 604800.0 + audit.toc_tow_seconds,
                "toe_gpst_seconds_since_1980": int(audit.toe_gps_week) * 604800.0 + audit.toe_tow_seconds,
                "iode_aode": int(audit.iode)}

    def selected_decision(self, satellite, audit):
        """Reject ambiguous actual selection after RTKLIB duplicate removal.

        This metadata query uses the same receiver-time selection as satposs.
        The bridge does not expose IODC or orbit here, so a matching ambiguous
        projection is rejected conservatively rather than guessed from source
        order. In particular a nearer pre-uniqnav legal key is not sufficient.
        """
        identity = self.selected_identity(satellite, audit)
        key = (satellite, identity["toc_gpst_seconds_since_1980"],
               identity["toe_gpst_seconds_since_1980"], identity["iode_aode"])
        keys = sorted(self.conflicts_by_selection.get(key, ()))
        return ({"reason": "BROADCAST_CLOCK_CONFLICT", "satellite": satellite,
                 "conflicting_physical_keys": keys,
                 "dependency_stage": "POST_UNIQNAV_SELECTED_EPHEMERIS",
                 "selected_ephemeris": identity} if keys else None)

    def decision(self, satellite, gps_week, gps_tow_seconds):
        """Return reason/physical keys, or None when navigation is unambiguous.

        No available record is reported separately, not replaced by an older
        out-of-age ephemeris. The clock gate does not rank healthy clock values.
        """
        if satellite[0] not in MAX_TOE_AGE_S:
            return None
        now = int(gps_week) * 604800.0 + float(gps_tow_seconds)
        candidates = [(abs(r.toe_gpst_s - now), r) for r in self.by_satellite.get(satellite, ())]
        candidates = [(age, r) for age, r in candidates if age <= MAX_TOE_AGE_S[satellite[0]]]
        if not candidates:
            return {"reason": "NO_APPLICABLE_BROADCAST_NAVIGATION", "satellite": satellite,
                    "conflicting_physical_keys": [],
                    "dependency_stage": "PRE_UNIQNAV_NEAREST_APPLICABLE"}
        nearest = min(age for age, _ in candidates)
        keys = sorted({self.conflict_ids[r.key] for age, r in candidates
                       if age == nearest and r.key in self.conflict_ids})
        return ({"reason": "BROADCAST_CLOCK_CONFLICT", "satellite": satellite,
                 "conflicting_physical_keys": keys, "nearest_toe_age_s": nearest,
                 "dependency_stage": "PRE_UNIQNAV_NEAREST_APPLICABLE"} if keys else None)
