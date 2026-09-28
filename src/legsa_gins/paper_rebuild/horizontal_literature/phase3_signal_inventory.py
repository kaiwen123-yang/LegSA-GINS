"""Real RAWX signal inventory and independent EXT03 system-mode support gate.

The audit consumes only exact paired :class:`RawxEpoch` objects.  It does not
decode NAV-HPPOSECEF, read trace, or infer a nominal frequency from a column
label.  Every count is tied to the u-blox ``gnssId/svId/sigId/freqId`` tuple
and the wavelength accepted by the shared raw backend.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .shared_raw_backend import (
    RawxEpoch,
    RawxMeasurement,
    SatelliteStateProvider,
    SignalIdentity,
    identity_text,
    rinex_satellite_id,
    signal_frequency_hz,
    integer_compatible_carrier_cycles,
    wavelength_m,
)


SIGNAL_GROUPS: Mapping[str, tuple[tuple[int, int, int], ...]] = {
    "GPS_L1": ((0, 0, 0),),
    "GPS_L2": ((0, 3, 0), (0, 4, 0)),
    "BDS_B1": ((3, 0, 0), (3, 1, 0)),
    "BDS_B2": ((3, 2, 0), (3, 3, 0)),
}

SIGNAL_LABELS: Mapping[tuple[int, int, int], tuple[str, str]] = {
    (0, 0, 0): ("GPS_L1", "1C"),
    (0, 3, 0): ("GPS_L2", "2L"),
    (0, 4, 0): ("GPS_L2", "2S_UNUSABLE_ON_BY2"),
    (3, 0, 0): ("BDS_B1", "2I"),
    (3, 1, 0): ("BDS_B1", "2I"),
    (3, 2, 0): ("BDS_B2", "7I"),
    (3, 3, 0): ("BDS_B2", "7I"),
}

MODE_FREQUENCIES: Mapping[str, tuple[str, ...]] = {
    "GPS_DUAL_FREQUENCY": ("GPS_L1", "GPS_L2"),
    "BDS_DUAL_FREQUENCY": ("BDS_B1", "BDS_B2"),
    "GPS_BDS_DUAL_FREQUENCY": ("GPS_L1", "GPS_L2", "BDS_B1", "BDS_B2"),
}


class SignalInventoryError(ValueError):
    """An exact-pair or signal-identity audit invariant failed."""


@dataclass(frozen=True)
class SignalAvailabilityRow:
    row_scope: str
    receiver: str
    signal_group: str
    signal_name: str
    gnss_id: int
    sig_id: int
    freq_id: int
    frequency_hz: float
    wavelength_m: float
    rinex_rtklib_mapping: str
    paired_epoch_count: int
    raw_count: int
    PR_valid_count: int
    CP_valid_count: int
    half_cycle_valid_count: int
    integer_compatible_count: int
    satellite_state_available_count: int
    common_two_receiver_count: int
    common_integer_compatible_count: int
    common_state_available_count: int
    epochs_with_common_integer_compatible: int
    epochs_with_two_common_integer_state_satellites: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModeSupport:
    system_mode: str
    supported: bool
    terminal_reason: str
    required_frequency_groups: tuple[str, ...]
    eligible_epoch_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_frequency_groups"] = list(self.required_frequency_groups)
        return payload


@dataclass(frozen=True)
class SignalInventoryResult:
    rows: tuple[SignalAvailabilityRow, ...]
    epoch_rows: tuple[Mapping[str, Any], ...]
    mode_support: tuple[ModeSupport, ...]
    exact_paired_epoch_count: int
    satellite_state_provider_status: str

    def supported_modes(self) -> tuple[str, ...]:
        return tuple(item.system_mode for item in self.mode_support if item.supported)


def _signal_key(measurement: RawxMeasurement) -> tuple[int, int, int]:
    identity = measurement.identity
    return identity.gnss_id, identity.sig_id, identity.freq_id


def signal_group(identity: SignalIdentity) -> str | None:
    label = SIGNAL_LABELS.get((identity.gnss_id, identity.sig_id, identity.freq_id))
    return None if label is None else label[0]


def _finite_phase(measurement: RawxMeasurement) -> bool:
    return measurement.carrier_valid and math.isfinite(measurement.cp_mes_cycles)


def _finite_code(measurement: RawxMeasurement) -> bool:
    return (
        measurement.pseudorange_valid
        and math.isfinite(measurement.pr_mes_m)
        and 1.0e6 < measurement.pr_mes_m < 1.0e8
    )


def integer_compatible(measurement: RawxMeasurement) -> bool:
    """Carrier is usable without applying an invented second half-cycle shift."""
    if not _finite_code(measurement):
        return False
    try:
        integer_compatible_carrier_cycles(measurement)
    except Exception:
        return False
    return True


def _measurement_map(epoch: RawxEpoch) -> dict[SignalIdentity, RawxMeasurement]:
    result: dict[SignalIdentity, RawxMeasurement] = {}
    for measurement in epoch.measurements:
        if _signal_key(measurement) not in SIGNAL_LABELS:
            continue
        if measurement.identity in result:
            raise SignalInventoryError(
                f"duplicate RAWX identity in one epoch: {identity_text(measurement.identity)}"
            )
        result[measurement.identity] = measurement
    return result


def _state_available(
    provider: SatelliteStateProvider | None,
    epoch: RawxEpoch,
    measurement: RawxMeasurement,
) -> bool:
    if provider is None or not _finite_code(measurement):
        return False
    try:
        state = provider.state(
            measurement.identity, epoch.gps_week, epoch.gps_tow_seconds,
            measurement.pr_mes_m,
        )
        position = tuple(float(value) for value in state.position_ecef_m)
        # "Usable ephemeris" means a finite broadcast state explicitly marked
        # healthy.  Elevation masking belongs to the production DD builder and
        # is deliberately not folded into this inventory count.
        return state.health == 0 and len(position) == 3 and all(math.isfinite(value) for value in position)
    except Exception:
        # Availability is evidence, not a reason to abort the other systems.
        return False


def audit_signal_availability(
    pairs: Sequence[tuple[RawxEpoch, RawxEpoch]],
    provider: SatelliteStateProvider | None,
) -> SignalInventoryResult:
    """Count the actual GPS/BDS dual-frequency chain on exact paired epochs."""
    if not pairs:
        raise SignalInventoryError("signal inventory requires at least one paired epoch")
    counters: dict[tuple[str, tuple[int, int, int]], dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    common_integer_by_epoch: list[dict[str, set[int]]] = []
    common_state_by_epoch: list[dict[str, set[int]]] = []
    signal_integer_by_epoch: list[dict[tuple[int, int, int], set[int]]] = []
    signal_state_by_epoch: list[dict[tuple[int, int, int], set[int]]] = []
    epoch_rows: list[dict[str, Any]] = []
    prior_key: tuple[int, float] | None = None
    for left, right in pairs:
        key1 = (left.gps_week, left.gps_tow_seconds)
        key2 = (right.gps_week, right.gps_tow_seconds)
        if key1 != key2:
            raise SignalInventoryError(f"non-exact RAWX pair: {key1!r} != {key2!r}")
        if prior_key is not None and key1 <= prior_key:
            raise SignalInventoryError("paired RAWX epochs are not strictly chronological")
        prior_key = key1
        maps = (_measurement_map(left), _measurement_map(right))
        state_maps: list[dict[SignalIdentity, bool]] = []
        for receiver, epoch, measurements in zip(("GNSS1", "GNSS2"), (left, right), maps):
            state_map: dict[SignalIdentity, bool] = {}
            for identity, measurement in measurements.items():
                signal_key = (identity.gnss_id, identity.sig_id, identity.freq_id)
                count = counters[(receiver, signal_key)]
                count["raw"] += 1
                count["pr"] += int(_finite_code(measurement))
                count["cp"] += int(_finite_phase(measurement))
                count["half"] += int(_finite_phase(measurement) and measurement.half_cycle_valid)
                count["integer"] += int(integer_compatible(measurement))
                available = _state_available(provider, epoch, measurement)
                state_map[identity] = available
                count["state"] += int(available)
            state_maps.append(state_map)
        epoch_integer: dict[str, set[int]] = {name: set() for name in SIGNAL_GROUPS}
        epoch_state: dict[str, set[int]] = {name: set() for name in SIGNAL_GROUPS}
        epoch_signal_integer: dict[tuple[int, int, int], set[int]] = {
            key: set() for key in SIGNAL_LABELS
        }
        epoch_signal_state: dict[tuple[int, int, int], set[int]] = {
            key: set() for key in SIGNAL_LABELS
        }
        for identity in sorted(set(maps[0]) & set(maps[1])):
            signal_key = (identity.gnss_id, identity.sig_id, identity.freq_id)
            receiver_measurements = (maps[0][identity], maps[1][identity])
            common_integer = all(integer_compatible(item) for item in receiver_measurements)
            common_state = common_integer and state_maps[0][identity] and state_maps[1][identity]
            for receiver in ("GNSS1", "GNSS2"):
                count = counters[(receiver, signal_key)]
                count["common"] += 1
                count["common_integer"] += int(common_integer)
                count["common_state"] += int(common_state)
            group = SIGNAL_LABELS[signal_key][0]
            if common_integer:
                epoch_integer[group].add(identity.sv_id)
                epoch_signal_integer[signal_key].add(identity.sv_id)
            if common_state:
                epoch_state[group].add(identity.sv_id)
                epoch_signal_state[signal_key].add(identity.sv_id)
        common_integer_by_epoch.append(epoch_integer)
        common_state_by_epoch.append(epoch_state)
        signal_integer_by_epoch.append(epoch_signal_integer)
        signal_state_by_epoch.append(epoch_signal_state)
        for receiver, measurements, state_map in zip(("GNSS1", "GNSS2"), maps, state_maps):
            for signal_key, (group, name) in SIGNAL_LABELS.items():
                selected = [m for identity, m in measurements.items() if (identity.gnss_id, identity.sig_id, identity.freq_id) == signal_key]
                common_ids = [identity for identity in set(maps[0]) & set(maps[1]) if (identity.gnss_id, identity.sig_id, identity.freq_id) == signal_key]
                epoch_rows.append({
                    "row_scope": "EPOCH", "epoch_index": len(common_integer_by_epoch)-1,
                    "gps_week": left.gps_week, "gps_tow_seconds": left.gps_tow_seconds,
                    "receiver": receiver, "signal_group": group, "signal_name": name,
                    "gnss_id": signal_key[0], "sig_id": signal_key[1], "freq_id": signal_key[2],
                    "raw_count": len(selected),
                    "PR_valid_count": sum(_finite_code(item) for item in selected),
                    "CP_valid_count": sum(_finite_phase(item) for item in selected),
                    "half_cycle_valid_count": sum(_finite_phase(item) and item.half_cycle_valid for item in selected),
                    "integer_compatible_count": sum(integer_compatible(item) for item in selected),
                    "satellite_state_available_count": sum(state_map.get(item.identity, False) for item in selected),
                    "common_two_receiver_count": len(common_ids),
                    "common_integer_compatible_count": len(epoch_signal_integer[signal_key]),
                    "common_state_available_count": len(epoch_signal_state[signal_key]),
                })

    rows: list[SignalAvailabilityRow] = []
    for receiver in ("GNSS1", "GNSS2"):
        for signal_key, (group, name) in SIGNAL_LABELS.items():
            identity = SignalIdentity(signal_key[0], 1, signal_key[1], signal_key[2])
            count = counters[(receiver, signal_key)]
            rows.append(SignalAvailabilityRow(
                row_scope="AGGREGATE",
                receiver=receiver,
                signal_group=group,
                signal_name=name,
                gnss_id=signal_key[0],
                sig_id=signal_key[1],
                freq_id=signal_key[2],
                frequency_hz=signal_frequency_hz(identity),
                wavelength_m=wavelength_m(identity),
                rinex_rtklib_mapping=f"{rinex_satellite_id(identity)[0]}:{name}",
                paired_epoch_count=len(pairs),
                raw_count=count["raw"],
                PR_valid_count=count["pr"],
                CP_valid_count=count["cp"],
                half_cycle_valid_count=count["half"],
                integer_compatible_count=count["integer"],
                satellite_state_available_count=count["state"],
                common_two_receiver_count=count["common"],
                common_integer_compatible_count=count["common_integer"],
                common_state_available_count=count["common_state"],
                epochs_with_common_integer_compatible=sum(
                    bool(item[signal_key]) for item in signal_integer_by_epoch
                ),
                epochs_with_two_common_integer_state_satellites=sum(
                    len(item[signal_key]) >= 2 for item in signal_state_by_epoch
                ),
            ))

    supports: list[ModeSupport] = []
    for mode, required in MODE_FREQUENCIES.items():
        constellation_groups = (("GPS_L1", "GPS_L2"),) if mode.startswith("GPS_") else (("BDS_B1", "BDS_B2"),)
        if mode == "GPS_BDS_DUAL_FREQUENCY":
            constellation_groups = (("GPS_L1", "GPS_L2"), ("BDS_B1", "BDS_B2"))
        eligible_count = sum(
            all(len(set.intersection(*(epoch[group] for group in groups))) >= 2
                for groups in constellation_groups)
            for epoch in common_state_by_epoch
        )
        if provider is None:
            reason = "UNSUPPORTED_SUBMODE_SATELLITE_STATE_AUDIT_NOT_RUN"
        elif eligible_count == 0:
            absent = [
                group for group in required
                if not any(len(epoch[group]) >= 2 for epoch in common_state_by_epoch)
            ]
            detail = "_AND_".join(absent or required)
            reason = f"UNSUPPORTED_SUBMODE_NO_COMMON_INTEGER_COMPATIBLE_EPHEMERIS_{detail}"
        else:
            reason = "SUPPORTED"
        supports.append(ModeSupport(
            system_mode=mode,
            supported=reason == "SUPPORTED",
            terminal_reason=reason,
            required_frequency_groups=required,
            eligible_epoch_count=eligible_count,
        ))
    return SignalInventoryResult(
        rows=tuple(rows),
        epoch_rows=tuple(epoch_rows),
        mode_support=tuple(supports),
        exact_paired_epoch_count=len(pairs),
        satellite_state_provider_status=(
            "NOT_RUN" if provider is None else str(getattr(provider, "status", "UNKNOWN"))
        ),
    )
