"""Shared, method-independent UBX observation and broadcast-state backend.

Raw CSV bytes are the sole observation source.  Navigation files and the
RTKLIB bridge are explicit runtime dependencies; no machine-local path is
discovered by this module.
"""

from __future__ import annotations

import csv
import ast
import ctypes
import math
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Protocol, Sequence

import numpy as np


class RawBackendError(ValueError):
    pass


class DoubleDifferenceStageError(RawBackendError):
    """A fail-closed DD construction error with its first failed stage.

    ``accounting`` is deliberately attached to failures as well as successful
    models.  In particular, a satellite-state failure must never erase the
    provider-independent raw/common-satellite evidence collected first.
    """

    def __init__(self, code: str, message: str, accounting: object | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.accounting = accounting


@dataclass(frozen=True, order=True)
class SignalIdentity:
    gnss_id: int
    sv_id: int
    sig_id: int
    freq_id: int


def identity_text(identity: SignalIdentity) -> str:
    """Stable serialization used by row-level ambiguity and tracking audits."""
    return f"{identity.gnss_id}:{identity.sv_id}:{identity.sig_id}:{identity.freq_id}"


@dataclass(frozen=True)
class RawxMeasurement:
    identity: SignalIdentity
    pr_mes_m: float
    cp_mes_cycles: float
    do_mes_hz: float
    locktime_ms: int
    cno_dbhz: int
    pr_std_code: int
    cp_std_code: int
    do_std_code: int
    tracking_status: int

    @property
    def pseudorange_valid(self) -> bool:
        return bool(self.tracking_status & 0x01)

    @property
    def carrier_valid(self) -> bool:
        return bool(self.tracking_status & 0x02)

    @property
    def half_cycle_valid(self) -> bool:
        return bool(self.tracking_status & 0x04)

    @property
    def half_cycle_subtracted(self) -> bool:
        return bool(self.tracking_status & 0x08)

    # Official UBX field-name aliases.  Keeping both spellings prevents an
    # audit writer from accidentally translating the four independent trkStat
    # bits into one misleading aggregate flag.
    @property
    def pr_valid(self) -> bool:
        return self.pseudorange_valid

    @property
    def cp_valid(self) -> bool:
        return self.carrier_valid

    @property
    def half_cyc(self) -> bool:
        return self.half_cycle_valid

    @property
    def sub_half_cyc(self) -> bool:
        return self.half_cycle_subtracted

    def tracking_audit(self) -> dict[str, int | bool | float | str]:
        """Return the unaggregated receiver measurement fields for audit."""
        return {
            "identity": identity_text(self.identity),
            "prValid": self.pr_valid,
            "cpValid": self.cp_valid,
            "halfCyc": self.half_cyc,
            "subHalfCyc": self.sub_half_cyc,
            "locktime_ms": self.locktime_ms,
            "prStdev": self.pr_std_code,
            "cpStdev": self.cp_std_code,
            "doStdev": self.do_std_code,
            "trkStat": self.tracking_status,
        }


@dataclass(frozen=True)
class RawxEpoch:
    gps_tow_seconds: float
    gps_week: int
    leap_seconds: int
    receiver_status: int
    version: int
    measurements: tuple[RawxMeasurement, ...]


@dataclass(frozen=True)
class SfrbxWords:
    gnss_id: int
    sv_id: int
    reserved1: int
    freq_id: int
    channel: int
    version: int
    reserved2: int
    words: tuple[int, ...]


@dataclass(frozen=True)
class NavSatEntry:
    identity: SignalIdentity
    cno_dbhz: int
    elevation_deg: int
    azimuth_deg: int
    pseudorange_residual_m: float
    flags: int


@dataclass(frozen=True)
class NavSatEpoch:
    itow_ms: int
    version: int
    satellites: tuple[NavSatEntry, ...]


@dataclass(frozen=True)
class NavHpPosEcefEpoch:
    """UBX-NAV-HPPOSECEF v0 with the exact documented integer components."""

    itow_ms: int
    version: int
    ecef_cm: tuple[int, int, int]
    ecef_hp_0p1mm: tuple[int, int, int]
    position_accuracy_0p1mm: int
    reserved1: bytes = b"\x00\x00\x00"
    reserved2: int = 0

    @property
    def position_ecef_m(self) -> np.ndarray:
        # UBX-18053584 R02 section 5.14.6: precise coordinate in cm is
        # ecef + ecefHp*1e-2, hence metres are cm*1e-2 + hp*1e-4.
        return np.asarray(self.ecef_cm, dtype=float) * 1.0e-2 + np.asarray(
            self.ecef_hp_0p1mm, dtype=float
        ) * 1.0e-4

    @property
    def position_accuracy_m(self) -> float:
        return self.position_accuracy_0p1mm * 1.0e-4


@dataclass(frozen=True)
class SatelliteState:
    position_ecef_m: np.ndarray
    velocity_ecef_mps: np.ndarray
    clock_bias_s: float = 0.0
    clock_drift_sps: float = 0.0
    variance_m2: float = math.nan
    health: int = 0


@dataclass(frozen=True)
class EphemerisAudit:
    signed_age_seconds: float
    toe_gps_week: int
    toe_tow_seconds: float
    toc_gps_week: int
    toc_tow_seconds: float
    health: int
    iode: int


class SatelliteStateProvider(Protocol):
    status: str

    def state(self, identity: SignalIdentity, gps_week: int,
              gps_tow_seconds: float,
              pseudorange_m: float | None = None) -> SatelliteState: ...


class UnavailableSatelliteStateProvider:
    status = "BLOCKED_SFRBX_BROADCAST_EPHEMERIS_PROVIDER_NOT_IMPLEMENTED"

    def state(self, identity: SignalIdentity, gps_week: int,
              gps_tow_seconds: float,
              pseudorange_m: float | None = None) -> SatelliteState:
        raise RawBackendError(self.status)


@dataclass(frozen=True)
class UbxReconstruction:
    stream: bytes
    message_counts: dict[str, int]
    rawx_epochs: tuple[RawxEpoch, ...]
    sfrbx_messages: tuple[SfrbxWords, ...]
    nav_sat_epochs: tuple[NavSatEpoch, ...]
    input_cell_count: int
    discarded_byte_count: int
    checksum_failure_count: int
    nav_hpposecef_epochs: tuple[NavHpPosEcefEpoch, ...] = ()


def parse_csv_data_cell(cell: str) -> bytes:
    """Parse a CSV data cell containing hex octets, contiguous hex, or integers."""
    lexical = cell.strip()
    if not lexical:
        raise RawBackendError("empty data cell")
    # Fixposition records the actual wire frame as a Python bytes literal.
    # ast.literal_eval is deliberately used instead of eval: only literal
    # syntax is accepted and the result must be bytes.
    if lexical.startswith(("b'", 'b"')):
        try:
            value = ast.literal_eval(lexical)
        except (SyntaxError, ValueError) as exc:
            raise RawBackendError("invalid Python bytes literal") from exc
        if not isinstance(value, bytes):
            raise RawBackendError("data-cell literal is not bytes")
        return value
    lexical = lexical.strip('"').strip()
    for ch in "[](){}":
        lexical = lexical.replace(ch, " ")
    tokens = lexical.replace(",", " ").replace(";", " ").split()
    if len(tokens) == 1:
        token = tokens[0]
        stripped = token[2:] if token.lower().startswith("0x") else token
        if len(stripped) > 2 and len(stripped) % 2 == 0:
            try:
                return bytes.fromhex(stripped)
            except ValueError:
                pass
    values = []
    for token in tokens:
        try:
            value = int(token, 16) if token.lower().startswith("0x") else int(token, 10)
        except ValueError as exc:
            raise RawBackendError(f"invalid data-cell octet: {token}") from exc
        if not 0 <= value <= 255:
            raise RawBackendError(f"data-cell octet out of range: {value}")
        values.append(value)
    return bytes(values)


def read_csv_data_cells(path: Path, column: str = "data") -> Iterable[bytes]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise RawBackendError(f"missing CSV column {column}")
        for row_number, row in enumerate(reader, start=2):
            if column not in row:
                raise RawBackendError(f"missing CSV column {column}")
            try:
                yield parse_csv_data_cell(row[column])
            except RawBackendError as exc:
                raise RawBackendError(f"row {row_number}: {exc}") from exc


def ubx_checksum(data: bytes) -> tuple[int, int]:
    a = b = 0
    for value in data:
        a = (a + value) & 0xFF
        b = (b + a) & 0xFF
    return a, b


def iter_ubx_frames(data: bytes) -> Iterable[tuple[int, int, bytes]]:
    cursor = 0
    while cursor < len(data):
        if cursor + 8 > len(data) or data[cursor:cursor + 2] != b"\xb5\x62":
            raise RawBackendError(f"invalid UBX framing at byte {cursor}")
        msg_class, msg_id, length = struct.unpack_from("<BBH", data, cursor + 2)
        end = cursor + 6 + length
        if end + 2 > len(data):
            raise RawBackendError("truncated UBX payload")
        body = data[cursor + 2:end]
        if ubx_checksum(body) != tuple(data[end:end + 2]):
            raise RawBackendError("UBX checksum mismatch")
        yield msg_class, msg_id, data[cursor + 6:end]
        cursor = end + 2


def _scan_valid_ubx_frames(data: bytes) -> tuple[list[bytes], int, int]:
    """Find checksum-valid frames in a byte cell while accounting for noise.

    Fixposition rows normally hold one Python-bytes UBX frame, but recorders
    may prepend logging bytes, concatenate frames, or split framing at a bad
    packet.  A bad sync candidate advances by one byte so a subsequent valid
    message remains recoverable.  Truncated/bad candidates are never emitted.
    """
    frames: list[bytes] = []
    discarded = checksum_failures = 0
    cursor = 0
    while cursor < len(data):
        sync = data.find(b"\xb5\x62", cursor)
        if sync < 0:
            discarded += len(data) - cursor
            break
        discarded += sync - cursor
        if sync + 8 > len(data):
            discarded += len(data) - sync
            break
        length = struct.unpack_from("<H", data, sync + 4)[0]
        end = sync + 8 + length
        if end > len(data):
            discarded += 1
            cursor = sync + 1
            continue
        frame = data[sync:end]
        if ubx_checksum(frame[2:-2]) != tuple(frame[-2:]):
            checksum_failures += 1
            discarded += 1
            cursor = sync + 1
            continue
        frames.append(frame)
        cursor = end
    return frames, discarded, checksum_failures


def reconstruct_ubx_stream(csv_path: Path, output_path: Path | None = None,
                           column: str = "data") -> UbxReconstruction:
    """Reconstruct checksum-valid UBX frames in original CSV/cell order."""
    frames: list[bytes] = []
    counts: Counter[str] = Counter()
    rawx_epochs: list[RawxEpoch] = []
    sfrbx_messages: list[SfrbxWords] = []
    nav_sat_epochs: list[NavSatEpoch] = []
    nav_hpposecef_epochs: list[NavHpPosEcefEpoch] = []
    source = Path(csv_path)
    cells = tuple(read_csv_data_cells(source, column))
    cell_frames, discarded, checksum_failures = _scan_valid_ubx_frames(b"".join(cells))
    for frame in cell_frames:
        msg_class, msg_id, payload = next(iter(iter_ubx_frames(frame)))
        counts[f"{msg_class:02X}-{msg_id:02X}"] += 1
        if (msg_class, msg_id) == (0x02, 0x15):
            rawx_epochs.append(decode_rawx(payload))
        elif (msg_class, msg_id) == (0x02, 0x13):
            sfrbx_messages.append(decode_sfrbx(payload))
        elif (msg_class, msg_id) == (0x01, 0x35):
            nav_sat_epochs.append(decode_nav_sat(payload))
        elif (msg_class, msg_id) == (0x01, 0x13):
            nav_hpposecef_epochs.append(decode_nav_hpposecef(payload))
        frames.append(frame)
    stream = b"".join(frames)
    if output_path is not None:
        destination = Path(output_path)
        if destination.resolve() == source.resolve():
            raise RawBackendError("reconstructed UBX output must not overwrite source CSV")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(stream)
    return UbxReconstruction(
        stream=stream,
        message_counts=dict(sorted(counts.items())),
        rawx_epochs=tuple(rawx_epochs),
        sfrbx_messages=tuple(sfrbx_messages),
        nav_sat_epochs=tuple(nav_sat_epochs),
        input_cell_count=len(cells),
        discarded_byte_count=discarded,
        checksum_failure_count=checksum_failures,
        nav_hpposecef_epochs=tuple(nav_hpposecef_epochs),
    )


def decode_rawx(payload: bytes) -> RawxEpoch:
    if len(payload) < 16:
        raise RawBackendError("RAWX header truncated")
    tow, week, leap, count, status, version, _reserved = struct.unpack_from("<dHbBBB2s", payload)
    # The two trailing header octets are receiver-reserved and are nonzero in
    # the hash-locked F9T recording.  They carry no measurement semantics and
    # the interface specification does not assign them a value contract.
    if version != 1:
        raise RawBackendError("unsupported or malformed RAWX v1 header")
    if len(payload) != 16 + 32 * count:
        raise RawBackendError("RAWX record boundary mismatch")
    measurements = []
    fmt = "<ddfBBBBHBBBBBB"
    for index in range(count):
        fields = struct.unpack_from(fmt, payload, 16 + 32 * index)
        pr, cp, dop, gnss, sv, sig, freq, lock, cno, prs, cps, dos, trk, reserved3 = fields
        if reserved3 != 0 or not all(math.isfinite(x) for x in (pr, cp, dop)):
            raise RawBackendError("malformed RAWX measurement")
        ident = SignalIdentity(gnss, sv, sig, freq)
        signal_frequency_hz(ident)
        measurements.append(RawxMeasurement(ident, pr, cp, dop, lock, cno,
                                            prs & 0x0F, cps & 0x0F, dos & 0x0F, trk))
    return RawxEpoch(tow, week, leap, status, version, tuple(measurements))


def decode_sfrbx(payload: bytes) -> SfrbxWords:
    if len(payload) < 8:
        raise RawBackendError("SFRBX header truncated")
    gnss, sv, reserved1, freq, count, channel, version, reserved2 = struct.unpack_from(
        "<BBBBBBBB", payload
    )
    if version != 2 or len(payload) != 8 + 4 * count:
        raise RawBackendError("unsupported or malformed SFRBX boundary")
    words = struct.unpack_from(f"<{count}I", payload, 8) if count else ()
    # UBX-18053584 R02, UBX-RXM-SFRBX v2: byte 2 and byte 7 are
    # reserved1/reserved2.  Preserve their observed values for audit, but do
    # not fabricate a signal identity from either reserved byte.
    return SfrbxWords(gnss, sv, reserved1, freq, channel, version, reserved2,
                      tuple(words))


def decode_nav_sat(payload: bytes) -> NavSatEpoch:
    if len(payload) < 8:
        raise RawBackendError("NAV-SAT header truncated")
    itow, version, count, reserved = struct.unpack_from("<IBBH", payload)
    if version != 1 or reserved != 0 or len(payload) != 8 + 12 * count:
        raise RawBackendError("unsupported or malformed NAV-SAT boundary")
    satellites: list[NavSatEntry] = []
    for index in range(count):
        gnss, sv, cno, elevation, azimuth, pr_res, flags = struct.unpack_from(
            "<BBBbhhI", payload, 8 + 12 * index
        )
        satellites.append(NavSatEntry(
            identity=SignalIdentity(gnss, sv, 0, 0),
            cno_dbhz=cno,
            elevation_deg=elevation,
            azimuth_deg=azimuth,
            pseudorange_residual_m=pr_res * 0.1,
            flags=flags,
        ))
    return NavSatEpoch(itow, version, tuple(satellites))


def decode_nav_hpposecef(payload: bytes) -> NavHpPosEcefEpoch:
    """Decode UBX-NAV-HPPOSECEF (0x01 0x13), protocol-29 version 0.

    Units and high-precision bounds follow UBX-18053584 R02 section 5.14.6.
    The receiver position remains diagnostic-only; this function merely
    preserves the source fields and applies their documented unit conversion.
    """
    if len(payload) != 28:
        raise RawBackendError("NAV-HPPOSECEF record boundary mismatch")
    version = payload[0]
    if version != 0:
        raise RawBackendError("unsupported NAV-HPPOSECEF version")
    reserved1 = payload[1:4]
    itow_ms, x_cm, y_cm, z_cm, x_hp, y_hp, z_hp, reserved2, p_acc = struct.unpack_from(
        "<IiiibbbBI", payload, 4
    )
    high_precision = (x_hp, y_hp, z_hp)
    if any(value < -99 or value > 99 for value in high_precision):
        raise RawBackendError("NAV-HPPOSECEF high-precision component outside -99..99")
    epoch = NavHpPosEcefEpoch(
        itow_ms=itow_ms,
        version=version,
        ecef_cm=(x_cm, y_cm, z_cm),
        ecef_hp_0p1mm=high_precision,
        position_accuracy_0p1mm=p_acc,
        reserved1=reserved1,
        reserved2=reserved2,
    )
    position = epoch.position_ecef_m
    radius = float(np.linalg.norm(position))
    if np.any(~np.isfinite(position)) or not 1.0e6 <= radius <= 1.0e8:
        raise RawBackendError("NAV-HPPOSECEF ECEF position outside physical bounds")
    return epoch


# u-blox gnssId/sigId registry.  Only explicitly verified Phase-1 signals pass.
_FIXED_FREQUENCIES = {
    (0, 0): 1575.42e6,  # GPS L1 C/A
    (0, 3): 1227.60e6,  # GPS L2 CL
    (0, 4): 1227.60e6,  # GPS L2 CM
    (1, 0): 1575.42e6,  # SBAS L1 C/A
    (2, 0): 1575.42e6,  # Galileo E1 C
    (2, 1): 1575.42e6,  # Galileo E1 B
    (2, 5): 1207.14e6,  # Galileo E5b I
    (2, 6): 1207.14e6,  # Galileo E5b Q
    (3, 0): 1561.098e6, # BeiDou B1I D1
    (3, 1): 1561.098e6, # BeiDou B1I D2
    (3, 2): 1207.14e6,  # BeiDou B2I D1
    (3, 3): 1207.14e6,  # BeiDou B2I D2
    (5, 0): 1575.42e6,  # QZSS L1 C/A
    (5, 4): 1227.60e6,  # QZSS L2 CM
    (5, 5): 1227.60e6,  # QZSS L2 CL
}


def signal_frequency_hz(identity: SignalIdentity) -> float:
    if identity.gnss_id == 6:  # GLONASS FDMA: freqId is channel + 7.
        channel = identity.freq_id - 7
        if channel < -7 or channel > 6:
            raise RawBackendError("invalid GLONASS FDMA freqId")
        if identity.sig_id == 0:
            return 1602.0e6 + channel * 0.5625e6
        if identity.sig_id == 2:
            return 1246.0e6 + channel * 0.4375e6
        raise RawBackendError("unsupported GLONASS signal")
    if identity.freq_id != 0:
        raise RawBackendError("non-GLONASS freqId must be zero")
    try:
        return _FIXED_FREQUENCIES[(identity.gnss_id, identity.sig_id)]
    except KeyError as exc:
        raise RawBackendError(f"unsupported signal identity: {identity}") from exc


def wavelength_m(identity: SignalIdentity) -> float:
    return 299_792_458.0 / signal_frequency_hz(identity)


_GNSS_RINEX_PREFIX = {0: "G", 1: "S", 2: "E", 3: "C", 5: "J", 6: "R"}


def rinex_satellite_id(identity: SignalIdentity) -> str:
    """Map a u-blox signal identity to the RTKLIB/RINEX satellite ID."""
    try:
        prefix = _GNSS_RINEX_PREFIX[identity.gnss_id]
    except KeyError as exc:
        raise RawBackendError(f"unsupported GNSS satellite mapping: {identity.gnss_id}") from exc
    prn = identity.sv_id
    if identity.gnss_id == 1 and prn >= 100:
        prn -= 100  # RTKLIB's textual SBAS convention is S20..S58.
    if prn <= 0 or prn > 99:
        raise RawBackendError(f"invalid satellite id: {identity}")
    return f"{prefix}{prn:02d}"


class RtklibBroadcastProvider:
    """Thin ctypes owner for an explicitly supplied external RTKLIB bridge."""

    status = "RTKLIB_BROADCAST_EPHEMERIS"

    def __init__(self, bridge_path: Path, navigation_paths: Sequence[Path]):
        bridge = Path(bridge_path)
        paths = tuple(Path(path) for path in navigation_paths)
        if not bridge.is_file():
            raise RawBackendError(f"RTKLIB bridge does not exist: {bridge}")
        if not paths or any(not path.is_file() for path in paths):
            raise RawBackendError("all navigation paths must be existing files")
        try:
            self._library = ctypes.CDLL(str(bridge))
        except OSError as exc:
            raise RawBackendError(f"cannot load RTKLIB bridge: {exc}") from exc
        self._configure_abi()
        encoded = tuple(str(path).encode("utf-8") for path in paths)
        path_array = (ctypes.c_char_p * len(encoded))(*encoded)
        self._handle = self._library.legsa_nav_load_rinex_paths(path_array, len(encoded))
        if not self._handle:
            raise RawBackendError("RTKLIB failed to load navigation files")
        self.navigation_paths = paths
        gps_like = ctypes.c_int()
        glonass = ctypes.c_int()
        sbas = ctypes.c_int()
        if not self._library.legsa_nav_counts(
            self._handle, ctypes.byref(gps_like), ctypes.byref(glonass), ctypes.byref(sbas)
        ):
            self.close()
            raise RawBackendError("RTKLIB navigation count query failed")
        self.ephemeris_counts = {
            "gps_gal_bds_qzs": gps_like.value,
            "glonass": glonass.value,
            "sbas": sbas.value,
        }

    def _configure_abi(self) -> None:
        lib = self._library
        double_pointer = ctypes.POINTER(ctypes.c_double)
        lib.legsa_nav_load_rinex_paths.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
        lib.legsa_nav_load_rinex_paths.restype = ctypes.c_void_p
        lib.legsa_nav_free.argtypes = [ctypes.c_void_p]
        lib.legsa_nav_free.restype = None
        lib.legsa_nav_counts.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                         ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        lib.legsa_nav_counts.restype = ctypes.c_int
        lib.legsa_sat_id_to_no.argtypes = [ctypes.c_char_p]
        lib.legsa_sat_id_to_no.restype = ctypes.c_int
        common = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double, ctypes.c_int]
        lib.legsa_satpos_broadcast.argtypes = common + [double_pointer, double_pointer,
                                                        double_pointer, ctypes.POINTER(ctypes.c_int)]
        lib.legsa_satpos_broadcast.restype = ctypes.c_int
        lib.legsa_satpos_transmit_broadcast.argtypes = common + [ctypes.c_double, double_pointer,
                                                                 double_pointer, double_pointer,
                                                                 ctypes.POINTER(ctypes.c_int)]
        lib.legsa_satpos_transmit_broadcast.restype = ctypes.c_int
        lib.legsa_broadcast_ephemeris_audit.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_double, ctypes.c_int,
            double_pointer, ctypes.POINTER(ctypes.c_int), double_pointer,
            ctypes.POINTER(ctypes.c_int), double_pointer,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
        ]
        lib.legsa_broadcast_ephemeris_audit.restype = ctypes.c_int
        lib.legsa_sat_frequency_hz.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
        lib.legsa_sat_frequency_hz.restype = ctypes.c_double

    def close(self) -> None:
        handle = getattr(self, "_handle", None)
        if handle:
            self._library.legsa_nav_free(handle)
            self._handle = None

    def __enter__(self) -> "RtklibBroadcastProvider":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def satellite_number(self, identity: SignalIdentity) -> int:
        sat = self._library.legsa_sat_id_to_no(rinex_satellite_id(identity).encode("ascii"))
        if sat <= 0:
            raise RawBackendError(f"RTKLIB rejected satellite identity: {identity}")
        return sat

    def state(self, identity: SignalIdentity, gps_week: int,
              gps_tow_seconds: float,
              pseudorange_m: float | None = None) -> SatelliteState:
        if gps_week < 0 or not math.isfinite(gps_tow_seconds):
            raise RawBackendError("invalid GPS measurement time")
        sat = self.satellite_number(identity)
        rs = (ctypes.c_double * 6)()
        dts = (ctypes.c_double * 2)()
        variance = ctypes.c_double()
        health = ctypes.c_int()
        if pseudorange_m is None:
            ok = self._library.legsa_satpos_broadcast(
                self._handle, gps_week, gps_tow_seconds, sat,
                rs, dts, ctypes.byref(variance), ctypes.byref(health),
            )
        else:
            if not math.isfinite(pseudorange_m) or pseudorange_m <= 0:
                raise RawBackendError("invalid pseudorange for transmit-time state")
            ok = self._library.legsa_satpos_transmit_broadcast(
                self._handle, gps_week, gps_tow_seconds, sat, pseudorange_m,
                rs, dts, ctypes.byref(variance), ctypes.byref(health),
            )
        values = np.asarray(tuple(rs), dtype=float)
        clocks = np.asarray(tuple(dts), dtype=float)
        radius = float(np.linalg.norm(values[:3]))
        if (not ok or np.any(~np.isfinite(values)) or np.any(~np.isfinite(clocks))
                or not 2.0e7 < radius < 5.0e7 or not math.isfinite(variance.value)):
            raise RawBackendError(f"no finite broadcast state for {rinex_satellite_id(identity)}")
        return SatelliteState(values[:3], values[3:], clocks[0], clocks[1],
                              variance.value, health.value)

    def frequency_hz(self, identity: SignalIdentity, rinex_code: str = "1C") -> float:
        frequency = self._library.legsa_sat_frequency_hz(
            self._handle, self.satellite_number(identity), rinex_code.encode("ascii")
        )
        if not math.isfinite(frequency) or frequency <= 0:
            raise RawBackendError(f"RTKLIB has no frequency for {identity}/{rinex_code}")
        return frequency

    def ephemeris_audit(self, identity: SignalIdentity, gps_week: int,
                        gps_tow_seconds: float) -> EphemerisAudit:
        sat = self.satellite_number(identity)
        age = ctypes.c_double()
        toe_week = ctypes.c_int()
        toe_tow = ctypes.c_double()
        toc_week = ctypes.c_int()
        toc_tow = ctypes.c_double()
        health = ctypes.c_int()
        iode = ctypes.c_int()
        ok = self._library.legsa_broadcast_ephemeris_audit(
            self._handle, gps_week, gps_tow_seconds, sat,
            ctypes.byref(age), ctypes.byref(toe_week), ctypes.byref(toe_tow),
            ctypes.byref(toc_week), ctypes.byref(toc_tow),
            ctypes.byref(health), ctypes.byref(iode),
        )
        values = (age.value, toe_tow.value, toc_tow.value)
        if not ok or not all(math.isfinite(value) for value in values):
            raise RawBackendError(f"no broadcast ephemeris audit for {rinex_satellite_id(identity)}")
        return EphemerisAudit(age.value, toe_week.value, toe_tow.value,
                              toc_week.value, toc_tow.value, health.value,
                              iode.value)


def pair_epochs(left: Sequence[RawxEpoch], right: Sequence[RawxEpoch],
                tolerance_seconds: float = 0.0) -> tuple[list[tuple[RawxEpoch, RawxEpoch]], list[dict]]:
    if tolerance_seconds != 0.0:
        raise RawBackendError("Phase 1 pairing tolerance is frozen at 0.0")
    def key(epoch: RawxEpoch) -> tuple[int, float]:
        return epoch.gps_week, epoch.gps_tow_seconds

    left_counts = Counter(key(epoch) for epoch in left)
    right_groups: dict[tuple[int, float], list[tuple[int, RawxEpoch]]] = defaultdict(list)
    for index, epoch in enumerate(right):
        right_groups[key(epoch)].append((index, epoch))

    used: set[int] = set()
    pairs: list[tuple[RawxEpoch, RawxEpoch]] = []
    failures: list[dict] = []
    for first in left:
        epoch_key = key(first)
        candidates = right_groups.get(epoch_key, ())
        if left_counts[epoch_key] != 1 or len(candidates) != 1:
            failures.append({"receiver": 1, "week": first.gps_week,
                             "tow": first.gps_tow_seconds,
                             "code": "PAIR_MISSING" if not candidates else "PAIR_AMBIGUOUS"})
            continue
        index, second = candidates[0]
        used.add(index)
        pairs.append((first, second))
    for index, second in enumerate(right):
        if index not in used:
            epoch_key = key(second)
            ambiguous = left_counts[epoch_key] > 0 and (
                left_counts[epoch_key] != 1 or len(right_groups[epoch_key]) != 1
            )
            failures.append({"receiver": 2, "week": second.gps_week,
                             "tow": second.gps_tow_seconds,
                             "code": "PAIR_AMBIGUOUS" if ambiguous else "PAIR_UNMATCHED"})
    return pairs, failures


@dataclass(frozen=True)
class TrackingFlags:
    pseudorange_valid: bool
    carrier_valid: bool
    half_cycle_valid: bool
    half_cycle_subtracted: bool
    receiver_clock_reset: bool
    ambiguity_reinitialized_by_method: bool
    tracking_lock_reset_detected: bool
    cycle_slip_detected: bool
    half_cycle_state_changed: bool
    carrier_validity_changed: bool
    time_reversal_detected: bool
    first_observation: bool
    arc_reset_due_to_tracking: bool

    # Backward-compatible names retain *tracking-event* semantics.  They no
    # longer alias ordinary method-per-epoch ambiguity initialization.
    @property
    def lock_reset(self) -> bool:
        return self.tracking_lock_reset_detected

    @property
    def cycle_slip(self) -> bool:
        return self.cycle_slip_detected

    @property
    def arc_reset(self) -> bool:
        return self.arc_reset_due_to_tracking


class TrackingContinuity:
    def __init__(self) -> None:
        self._previous: dict[tuple[int, SignalIdentity], tuple[int, int, float, bool, bool, bool]] = {}

    def update(self, receiver: int, epoch: RawxEpoch, measurement: RawxMeasurement,
               *, ambiguity_reinitialized_by_method: bool = False) -> TrackingFlags:
        key = (receiver, measurement.identity)
        previous = self._previous.get(key)
        carrier_valid = measurement.carrier_valid
        half_valid = measurement.half_cycle_valid
        half_subtracted = measurement.half_cycle_subtracted
        clock_reset = bool(epoch.receiver_status & 0x02)
        first_observation = previous is None
        lock_reset = carrier_valid and (
            measurement.locktime_ms == 0
            or (previous is not None and measurement.locktime_ms < previous[0])
        )
        time_reversal = previous is not None and (
            epoch.gps_week, epoch.gps_tow_seconds
        ) <= (previous[1], previous[2])
        carrier_transition = previous is not None and carrier_valid != previous[3]
        half_transition = previous is not None and (
            half_valid != previous[4] or half_subtracted != previous[5]
        )
        # RTKLIB's RXM-RAWX decoder declares slip on a lock counter reset or a
        # subHalfCyc transition; rtkpos additionally treats half-valid parity
        # transitions as slips.  Merely observing an invalid carrier, seeing a
        # satellite for the first time, applying a receiver clock reset, or
        # independently initializing this method's ambiguity is not relabeled
        # as a detected receiver cycle slip.
        slip = lock_reset or carrier_transition or half_transition
        self._previous[key] = (measurement.locktime_ms, epoch.gps_week,
                               epoch.gps_tow_seconds, carrier_valid, half_valid,
                               half_subtracted)
        return TrackingFlags(
            pseudorange_valid=measurement.pseudorange_valid,
            carrier_valid=carrier_valid,
            half_cycle_valid=half_valid,
            half_cycle_subtracted=half_subtracted,
            receiver_clock_reset=clock_reset,
            ambiguity_reinitialized_by_method=ambiguity_reinitialized_by_method,
            tracking_lock_reset_detected=lock_reset,
            cycle_slip_detected=slip,
            half_cycle_state_changed=half_transition,
            carrier_validity_changed=carrier_transition,
            time_reversal_detected=time_reversal,
            first_observation=first_observation,
            # A receiver clock reset or a nonmonotonic receiver timestamp
            # invalidates the current phase arc even though neither event is
            # mislabeled as a detected carrier cycle slip.
            arc_reset_due_to_tracking=(slip or clock_reset or time_reversal),
        )


@dataclass(frozen=True)
class TrackingEpochSummary:
    receiver: int
    measurement_count: int
    used_carrier_count: int
    excluded_cp_invalid_count: int
    excluded_half_cycle_unknown_count: int
    sub_half_cycle_set_count: int
    actual_lock_reset_count: int
    actual_cycle_slip_count: int
    half_cycle_state_change_count: int
    ambiguity_reinitialized_by_method: bool
    pivot_changed: bool
    satellite_set_changed: bool


def tracking_epoch_summary(
    continuity: TrackingContinuity,
    receiver: int,
    epoch: RawxEpoch,
    used_identities: Iterable[SignalIdentity] = (),
    *,
    ambiguity_reinitialized_by_method: bool = False,
    pivot_changed: bool = False,
    satellite_set_changed: bool = False,
) -> TrackingEpochSummary:
    """Aggregate honest event *counts* without all/any validity booleans."""
    used = set(used_identities)
    gps_l1 = [
        measurement for measurement in epoch.measurements
        if (measurement.identity.gnss_id, measurement.identity.sig_id,
            measurement.identity.freq_id) == (0, 0, 0)
    ]
    flags = [
        continuity.update(
            receiver, epoch, measurement,
            ambiguity_reinitialized_by_method=ambiguity_reinitialized_by_method,
        )
        for measurement in gps_l1
    ]
    used_carrier_count = sum(
        measurement.identity in used and measurement.carrier_valid
        and measurement.half_cycle_valid
        for measurement in gps_l1
    )
    return TrackingEpochSummary(
        receiver=receiver,
        measurement_count=len(gps_l1),
        used_carrier_count=used_carrier_count,
        excluded_cp_invalid_count=sum(not item.carrier_valid for item in flags),
        excluded_half_cycle_unknown_count=sum(
            item.carrier_valid and not item.half_cycle_valid for item in flags
        ),
        sub_half_cycle_set_count=sum(item.half_cycle_subtracted for item in flags),
        actual_lock_reset_count=sum(item.tracking_lock_reset_detected for item in flags),
        actual_cycle_slip_count=sum(item.cycle_slip_detected for item in flags),
        half_cycle_state_change_count=sum(item.half_cycle_state_changed for item in flags),
        ambiguity_reinitialized_by_method=ambiguity_reinitialized_by_method,
        pivot_changed=pivot_changed,
        satellite_set_changed=satellite_set_changed,
    )


def select_reference(measurements: Sequence[RawxMeasurement], elevations_rad: dict[SignalIdentity, float],
                     previous: SignalIdentity | None = None) -> tuple[SignalIdentity, bool]:
    eligible = [
        m for m in measurements
        if (m.pseudorange_valid and m.carrier_valid and m.half_cycle_valid
            and m.identity in elevations_rad)
    ]
    if not eligible:
        raise RawBackendError("no valid reference satellite")
    groups = {(m.identity.gnss_id, m.identity.sig_id, m.identity.freq_id) for m in eligible}
    if len(groups) != 1:
        raise RawBackendError("reference selection requires one constellation/signal group")
    winner = min(eligible, key=lambda m: (-elevations_rad[m.identity], -m.locktime_ms,
                                          m.identity.sv_id, m.identity))
    return winner.identity, previous is not None and winner.identity != previous


def single_and_double_differences(receiver1: dict[SignalIdentity, float],
                                  receiver2: dict[SignalIdentity, float],
                                  pivot: SignalIdentity) -> dict[SignalIdentity, float]:
    common = set(receiver1) & set(receiver2)
    if pivot not in common:
        raise RawBackendError("pivot absent from receiver pair")
    sd = {identity: receiver2[identity] - receiver1[identity] for identity in common}
    return {identity: sd[identity] - sd[pivot] for identity in sorted(common) if identity != pivot}


def correlated_dd_covariance(sd_variances: Sequence[float], pivot_variance: float) -> np.ndarray:
    values = np.asarray(sd_variances, dtype=float)
    if values.ndim != 1 or values.size == 0 or np.any(~np.isfinite(values)) or np.any(values <= 0):
        raise RawBackendError("SD variances must be positive finite")
    if not math.isfinite(pivot_variance) or pivot_variance <= 0:
        raise RawBackendError("pivot variance must be positive finite")
    covariance = np.full((values.size, values.size), pivot_variance, dtype=float)
    covariance[np.diag_indices(values.size)] += values
    return covariance


def rawx_standard_deviations(measurement: RawxMeasurement) -> tuple[float, float, float]:
    if measurement.cp_std_code == 0x0F:
        raise RawBackendError("RAWX cpStdev=15 is invalid")
    # RAWX reports receiver-internal precision.  The preregistered real C00
    # policy adds a conservative 0.50 m raw-code floor for unmodelled antenna,
    # multipath and short-baseline code errors; it was frozen before any trace
    # evaluation and is never adjusted from heading performance.
    pr = max(0.50, 0.01 * 2.0 ** measurement.pr_std_code)
    cp = max(0.004, 0.004 * measurement.cp_std_code)
    dop = max(0.02, 0.002 * 2.0 ** measurement.do_std_code)
    if not all(math.isfinite(x) and x > 0 for x in (pr, cp, dop)):
        raise RawBackendError("non-positive stochastic model")
    return pr, cp, dop


def gps_l1_code_eligible(measurement: RawxMeasurement, min_cno_dbhz: int = 20) -> bool:
    return (
        measurement.identity.gnss_id == 0
        and measurement.identity.sig_id == 0
        and measurement.identity.freq_id == 0
        and measurement.pseudorange_valid
        and math.isfinite(measurement.pr_mes_m)
        and 1.0e6 < measurement.pr_mes_m < 1.0e8
        and measurement.cno_dbhz >= min_cno_dbhz
    )


@dataclass(frozen=True)
class HalfCycleContract:
    """Source-locked interpretation of UBX-RXM-RAWX carrier phase.

    The u-blox R02 specification defines ``cpMes`` as the carrier-phase
    measurement and ``subHalfCyc`` as "half cycle subtracted from phase".  At
    pinned RTKLIB commit 180043ee, ``decode_rxmrawx`` copies ``cpMes`` without
    adding or subtracting 0.5 (src/rcv/ublox.c:343-355, 392-419), emits
    ``LLI_HALFC`` when ``halfCyc`` is false, emits ``LLI_HALFS`` for audit when
    ``subHalfCyc`` is set, and declares a slip when that state changes.

    Consequently the direct DD backend uses a valid ``cpMes`` *as reported*;
    applying a second half-cycle correction would double-correct the receiver
    measurement.  A carrier is integer-compatible only while ``cpValid`` and
    ``halfCyc`` are both true and the phase/uncertainty fields are valid.
    ``subHalfCyc`` is preserved and its transition starts a new tracking arc,
    but its steady value is not itself an exclusion.
    """

    ubx_document: str = "UBX-18053584 R02 sections 5.15.3.1 and trkStat"
    ubx_document_sha256: str = (
        "3d6539cd5ab3efe1254c54e4dba25d17421bfe48ac96e633e602d8d214c13668"
    )
    rtklib_commit: str = "180043ee24b6d2b168f98b64be15f69d50046b1a"
    phase_value_policy: str = "CPMES_AS_REPORTED_NO_SECOND_HALF_CYCLE_SHIFT"
    unresolved_policy: str = "EXCLUDE_WHEN_HALFCYC_FALSE"
    sub_half_cycle_policy: str = "PRESERVE_STATE_AND_RESET_ARC_ON_TRANSITION"


HALF_CYCLE_CONTRACT = HalfCycleContract()


def integer_compatible_carrier_cycles(measurement: RawxMeasurement) -> float:
    """Return faithful integer-compatible phase cycles or fail closed."""
    if not measurement.carrier_valid:
        raise RawBackendError("carrier phase is not cpValid")
    if not measurement.half_cycle_valid:
        raise RawBackendError("carrier half-cycle ambiguity is unresolved")
    if measurement.cp_std_code == 0x0F:
        raise RawBackendError("RAWX cpStdev=15 is invalid")
    if not math.isfinite(measurement.cp_mes_cycles) or measurement.cp_mes_cycles == -0.5:
        raise RawBackendError("RAWX cpMes is invalid")
    # subHalfCyc describes a correction already present in cpMes.  RTKLIB's
    # RXM-RAWX decoder likewise copies L=cpMes and does not apply +/-0.5 here.
    return measurement.cp_mes_cycles


def strict_raw_tracking_eligible(measurement: RawxMeasurement,
                                 min_cno_dbhz: int = 20) -> bool:
    """Eligibility for real GPS-L1 code/carrier DD, before arc continuity."""
    if not gps_l1_code_eligible(measurement, min_cno_dbhz):
        return False
    try:
        integer_compatible_carrier_cycles(measurement)
    except RawBackendError:
        return False
    return measurement.locktime_ms > 0


@dataclass(frozen=True)
class GpsL1EpochAccounting:
    """Monotone GPS-L1 eligibility evidence for one exact receiver pair."""

    common_raw_identities: tuple[SignalIdentity, ...]
    common_pr_valid_identities: tuple[SignalIdentity, ...]
    common_cp_valid_identities: tuple[SignalIdentity, ...]
    common_pr_cp_valid_identities: tuple[SignalIdentity, ...]
    common_half_cycle_valid_identities: tuple[SignalIdentity, ...]
    common_integer_compatible_identities: tuple[SignalIdentity, ...]
    common_rtklib_phase_compatible_identities: tuple[SignalIdentity, ...] = ()
    satellite_state_available_identities: tuple[SignalIdentity, ...] = ()
    elevation_eligible_identities: tuple[SignalIdentity, ...] = ()
    dd_eligible_identities: tuple[SignalIdentity, ...] = ()
    duplicate_identities: tuple[SignalIdentity, ...] = ()

    @property
    def common_raw_satellite_count(self) -> int:
        return len(self.common_raw_identities)

    @property
    def common_pr_valid_satellite_count(self) -> int:
        return len(self.common_pr_valid_identities)

    @property
    def common_cp_valid_satellite_count(self) -> int:
        return len(self.common_cp_valid_identities)

    @property
    def common_pr_cp_valid_satellite_count(self) -> int:
        return len(self.common_pr_cp_valid_identities)

    @property
    def common_half_cycle_valid_satellite_count(self) -> int:
        return len(self.common_half_cycle_valid_identities)

    @property
    def common_integer_compatible_satellite_count(self) -> int:
        return len(self.common_integer_compatible_identities)

    @property
    def satellite_state_available_count(self) -> int:
        return len(self.satellite_state_available_identities)

    @property
    def common_rtklib_phase_compatible_satellite_count(self) -> int:
        return len(self.common_rtklib_phase_compatible_identities)

    @property
    def elevation_eligible_satellite_count(self) -> int:
        return len(self.elevation_eligible_identities)

    @property
    def dd_eligible_satellite_count(self) -> int:
        return len(self.dd_eligible_identities)

    def as_counts(self) -> dict[str, int]:
        return {
            name: int(getattr(self, name))
            for name in (
                "common_raw_satellite_count",
                "common_pr_valid_satellite_count",
                "common_cp_valid_satellite_count",
                "common_pr_cp_valid_satellite_count",
                "common_half_cycle_valid_satellite_count",
                "common_integer_compatible_satellite_count",
                "common_rtklib_phase_compatible_satellite_count",
                "satellite_state_available_count",
                "elevation_eligible_satellite_count",
                "dd_eligible_satellite_count",
            )
        }


def _gps_l1_measurement_groups(
    epoch: RawxEpoch,
) -> dict[SignalIdentity, tuple[RawxMeasurement, ...]]:
    grouped: dict[SignalIdentity, list[RawxMeasurement]] = defaultdict(list)
    for measurement in epoch.measurements:
        if (measurement.identity.gnss_id, measurement.identity.sig_id,
                measurement.identity.freq_id) == (0, 0, 0):
            grouped[measurement.identity].append(measurement)
    return {identity: tuple(values) for identity, values in grouped.items()}


def gps_l1_epoch_accounting(receiver1: RawxEpoch,
                            receiver2: RawxEpoch) -> GpsL1EpochAccounting:
    """Count common GPS L1 stages before any state-provider operation.

    This routine is intentionally independent of SPP, ephemeris, elevation,
    reference selection and the DD builder.  Its first six stages therefore
    remain truthful when every satellite-state request fails.
    """
    if (receiver1.gps_week, receiver1.gps_tow_seconds) != (
        receiver2.gps_week, receiver2.gps_tow_seconds
    ):
        raise RawBackendError("accounting epochs must have exact GPS week/TOW equality")
    first_groups = _gps_l1_measurement_groups(receiver1)
    second_groups = _gps_l1_measurement_groups(receiver2)
    raw = set(first_groups) & set(second_groups)
    duplicates = {
        identity for identity in raw
        if len(first_groups[identity]) != 1 or len(second_groups[identity]) != 1
    }
    unique = raw - duplicates
    first = {identity: first_groups[identity][0] for identity in unique}
    second = {identity: second_groups[identity][0] for identity in unique}
    pr_valid = {
        identity for identity in unique
        if first[identity].pseudorange_valid and second[identity].pseudorange_valid
    }
    cp_valid = {
        identity for identity in unique
        if first[identity].carrier_valid and second[identity].carrier_valid
    }
    pr_cp_valid = pr_valid & cp_valid
    half_cycle = {
        identity for identity in pr_cp_valid
        if first[identity].half_cycle_valid and second[identity].half_cycle_valid
    }
    integer_compatible: set[SignalIdentity] = set()
    for identity in half_cycle:
        try:
            integer_compatible_carrier_cycles(first[identity])
            integer_compatible_carrier_cycles(second[identity])
        except RawBackendError:
            continue
        integer_compatible.add(identity)
    # Pinned RTKLIB applies an additional receiver-quality filter in
    # decode_rxmrawx(): cpMes!=-0.5 and cpStdev<=5.  Preserve this population
    # separately; it is a diagnostic cross-check and is not silently conflated
    # with the official UBX cpStdev=15 invalidity semantics used by EXT01.
    rtklib_compatible = {
        identity for identity in integer_compatible
        if first[identity].cp_mes_cycles != -0.5
        and second[identity].cp_mes_cycles != -0.5
        and first[identity].cp_std_code <= 5
        and second[identity].cp_std_code <= 5
    }
    ordered = lambda values: tuple(sorted(values))
    return GpsL1EpochAccounting(
        common_raw_identities=ordered(raw),
        common_pr_valid_identities=ordered(pr_valid),
        common_cp_valid_identities=ordered(cp_valid),
        common_pr_cp_valid_identities=ordered(pr_cp_valid),
        common_half_cycle_valid_identities=ordered(half_cycle),
        common_integer_compatible_identities=ordered(integer_compatible),
        common_rtklib_phase_compatible_identities=ordered(rtklib_compatible),
        duplicate_identities=ordered(duplicates),
    )


_SPEED_OF_LIGHT_MPS = 299_792_458.0
_EARTH_ROTATION_RADPS = 7.2921151467e-5


def earth_rotation_correct_satellite(satellite_ecef_m: Sequence[float],
                                     flight_time_seconds: float) -> np.ndarray:
    satellite = np.asarray(satellite_ecef_m, dtype=float)
    if (satellite.shape != (3,) or np.any(~np.isfinite(satellite))
            or not math.isfinite(flight_time_seconds)
            or not 0.0 <= flight_time_seconds < 1.0):
        raise RawBackendError("invalid Earth-rotation correction inputs")
    angle = _EARTH_ROTATION_RADPS * flight_time_seconds
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.array([
        cosine * satellite[0] + sine * satellite[1],
        -sine * satellite[0] + cosine * satellite[1],
        satellite[2],
    ])


def line_of_sight(receiver_ecef_m: Sequence[float], satellite_ecef_m: Sequence[float]) -> np.ndarray:
    delta = np.asarray(satellite_ecef_m, dtype=float) - np.asarray(receiver_ecef_m, dtype=float)
    norm = np.linalg.norm(delta)
    if delta.shape != (3,) or not math.isfinite(float(norm)) or norm <= 0:
        raise RawBackendError("invalid receiver/satellite geometry")
    return delta / norm


def ecef_to_geodetic(receiver_ecef_m: Sequence[float]) -> tuple[float, float, float]:
    receiver = np.asarray(receiver_ecef_m, dtype=float)
    if receiver.shape != (3,) or np.any(~np.isfinite(receiver)):
        raise RawBackendError("invalid receiver ECEF")
    x, y, z = receiver
    longitude = math.atan2(y, x)
    semi_major = 6_378_137.0
    eccentricity_sq = 6.6943799901413165e-3
    horizontal = math.hypot(x, y)
    if horizontal < 1.0:
        raise RawBackendError("receiver ECEF is too close to polar axis/origin")
    latitude = math.atan2(z, horizontal * (1.0 - eccentricity_sq))
    height = 0.0
    for _ in range(12):
        sin_lat = math.sin(latitude)
        radius = semi_major / math.sqrt(1.0 - eccentricity_sq * sin_lat * sin_lat)
        height = horizontal / math.cos(latitude) - radius
        updated = math.atan2(z, horizontal * (1.0 - eccentricity_sq * radius / (radius + height)))
        if abs(updated - latitude) < 1e-13:
            latitude = updated
            break
        latitude = updated
    return latitude, longitude, height


def azimuth_elevation(receiver_ecef_m: Sequence[float],
                      satellite_ecef_m: Sequence[float]) -> tuple[float, float]:
    latitude, longitude, _height = ecef_to_geodetic(receiver_ecef_m)
    los = line_of_sight(receiver_ecef_m, satellite_ecef_m)
    sin_lat, cos_lat = math.sin(latitude), math.cos(latitude)
    sin_lon, cos_lon = math.sin(longitude), math.cos(longitude)
    east = -sin_lon * los[0] + cos_lon * los[1]
    north = (-sin_lat * cos_lon * los[0] - sin_lat * sin_lon * los[1]
             + cos_lat * los[2])
    up = (cos_lat * cos_lon * los[0] + cos_lat * sin_lon * los[1]
          + sin_lat * los[2])
    azimuth = math.atan2(east, north) % (2.0 * math.pi)
    elevation = math.asin(float(np.clip(up, -1.0, 1.0)))
    return azimuth, elevation


@dataclass(frozen=True)
class SppSolution:
    position_ecef_m: np.ndarray
    receiver_clock_bias_m: float
    residual_rms_m: float
    satellite_count: int
    iterations: int


def gps_l1_code_spp(epoch: RawxEpoch, provider: SatelliteStateProvider,
                    initial_position_ecef_m: Sequence[float] | None = None,
                    min_cno_dbhz: int = 20, max_iterations: int = 12) -> SppSolution:
    """Unweighted GPS L1 raw-code SPP used only to seed real DD geometry."""
    by_satellite: dict[SignalIdentity, RawxMeasurement] = {}
    for measurement in epoch.measurements:
        if gps_l1_code_eligible(measurement, min_cno_dbhz):
            previous = by_satellite.get(measurement.identity)
            if previous is None or measurement.cno_dbhz > previous.cno_dbhz:
                by_satellite[measurement.identity] = measurement
    if len(by_satellite) < 4:
        raise RawBackendError("GPS L1 SPP requires at least four eligible pseudoranges")
    position = (np.zeros(3, dtype=float) if initial_position_ecef_m is None
                else np.asarray(initial_position_ecef_m, dtype=float).copy())
    if position.shape != (3,) or np.any(~np.isfinite(position)):
        raise RawBackendError("invalid SPP initial position")
    clock_m = 0.0
    residual = np.empty(0)
    for iteration in range(1, max_iterations + 1):
        rows: list[list[float]] = []
        innovations: list[float] = []
        for identity, measurement in sorted(by_satellite.items()):
            try:
                state = provider.state(identity, epoch.gps_week, epoch.gps_tow_seconds,
                                       measurement.pr_mes_m)
            except RawBackendError:
                # Individual satellites without a source-backed broadcast
                # state are excluded and audited by the caller; they must not
                # suppress an otherwise full-rank raw-code SPP epoch.
                continue
            if state.health != 0:
                continue
            corrected = earth_rotation_correct_satellite(
                state.position_ecef_m, measurement.pr_mes_m / _SPEED_OF_LIGHT_MPS
            )
            delta = corrected - position
            geometric = float(np.linalg.norm(delta))
            if not math.isfinite(geometric) or geometric <= 0:
                continue
            los = delta / geometric
            predicted = geometric + clock_m - _SPEED_OF_LIGHT_MPS * state.clock_bias_s
            rows.append([-los[0], -los[1], -los[2], 1.0])
            innovations.append(measurement.pr_mes_m - predicted)
        design = np.asarray(rows, dtype=float)
        residual = np.asarray(innovations, dtype=float)
        if design.shape[0] < 4 or np.linalg.matrix_rank(design) < 4:
            raise RawBackendError("GPS L1 SPP geometry is rank deficient")
        correction, *_ = np.linalg.lstsq(design, residual, rcond=None)
        position += correction[:3]
        clock_m += correction[3]
        if float(np.linalg.norm(correction[:3])) < 1e-4 and abs(correction[3]) < 1e-4:
            break
    else:
        raise RawBackendError("GPS L1 SPP failed to converge")
    postfit = residual - design @ correction
    return SppSolution(position, float(clock_m), float(np.sqrt(np.mean(postfit ** 2))),
                       design.shape[0], iteration)


@dataclass(frozen=True)
class DoubleDifferenceModel:
    pivot: SignalIdentity
    satellites: tuple[SignalIdentity, ...]
    observation_m: np.ndarray
    ambiguity_design_m: np.ndarray
    baseline_design: np.ndarray
    covariance_m2: np.ndarray
    elevations_rad: dict[SignalIdentity, float]
    accounting: GpsL1EpochAccounting
    receiver_order: str = "GNSS2_MINUS_GNSS1"
    dd_sign_convention: str = "(GNSS2-GNSS1)_SATELLITE_MINUS_PIVOT"
    phase_convention: str = HALF_CYCLE_CONTRACT.phase_value_policy
    pivot_changed: bool = False

    @property
    def ambiguity_satellite_identities(self) -> tuple[SignalIdentity, ...]:
        """Identity order corresponding one-for-one with an ambiguity vector."""
        return self.satellites

    @property
    def ambiguity_signal_identities(self) -> tuple[str, ...]:
        return tuple(identity_text(identity) for identity in self.satellites)

    @property
    def pivot_identity(self) -> str:
        return identity_text(self.pivot)


@dataclass(frozen=True)
class MatrixConditionDiagnostics:
    observation_count: int
    unknown_count: int
    raw_design_rank: int
    raw_design_condition: float
    covariance_condition: float
    raw_normal_rank: int
    raw_normal_condition: float
    whitened_design_rank: int
    whitened_design_condition: float
    whitened_normal_rank: int
    whitened_normal_condition: float


def dd_matrix_condition_diagnostics(model: DoubleDifferenceModel) -> MatrixConditionDiagnostics:
    """Report raw and covariance-whitened scaling/rank without trace input."""
    design = np.column_stack((model.ambiguity_design_m, model.baseline_design))
    covariance = np.asarray(model.covariance_m2, dtype=float)
    try:
        cholesky = np.linalg.cholesky(covariance)
        whitened = np.linalg.solve(cholesky, design)
    except np.linalg.LinAlgError as exc:
        raise DoubleDifferenceStageError(
            "NORMAL_MATRIX_RANK_DEFICIENT",
            "DD covariance is not positive definite",
            model.accounting,
        ) from exc
    raw_normal = design.T @ design
    whitened_normal = whitened.T @ whitened
    return MatrixConditionDiagnostics(
        observation_count=int(design.shape[0]),
        unknown_count=int(design.shape[1]),
        raw_design_rank=int(np.linalg.matrix_rank(design)),
        raw_design_condition=float(np.linalg.cond(design)),
        covariance_condition=float(np.linalg.cond(covariance)),
        raw_normal_rank=int(np.linalg.matrix_rank(raw_normal)),
        raw_normal_condition=float(np.linalg.cond(raw_normal)),
        whitened_design_rank=int(np.linalg.matrix_rank(whitened)),
        whitened_design_condition=float(np.linalg.cond(whitened)),
        whitened_normal_rank=int(np.linalg.matrix_rank(whitened_normal)),
        whitened_normal_condition=float(np.linalg.cond(whitened_normal)),
    )


def _require_dd_stage(accounting: GpsL1EpochAccounting, attribute: str,
                      code: str, description: str, minimum: int = 4) -> None:
    count = len(getattr(accounting, attribute))
    if count < minimum:
        raise DoubleDifferenceStageError(
            code, f"{description}: {count} < {minimum}", accounting
        )


def build_gps_l1_double_difference_model(
    receiver1: RawxEpoch,
    receiver2: RawxEpoch,
    provider: SatelliteStateProvider,
    receiver_ecef_m: Sequence[float],
    min_cno_dbhz: int = 20,
    minimum_elevation_rad: float = math.radians(10.0),
    previous_pivot: SignalIdentity | None = None,
) -> DoubleDifferenceModel:
    """Build real GPS-L1 code/phase ``y = A a + B b + e`` in metres."""
    if (receiver1.gps_week, receiver1.gps_tow_seconds) != (
        receiver2.gps_week, receiver2.gps_tow_seconds
    ):
        raise RawBackendError("DD epochs must have exact GPS week/TOW equality")
    accounting = gps_l1_epoch_accounting(receiver1, receiver2)
    _require_dd_stage(accounting, "common_raw_identities", "INSUFFICIENT_COMMON_RAW",
                      "common GPS-L1 raw satellites")
    _require_dd_stage(accounting, "common_pr_valid_identities", "INSUFFICIENT_PR_VALID",
                      "common GPS-L1 prValid satellites")
    _require_dd_stage(accounting, "common_cp_valid_identities", "INSUFFICIENT_CP_VALID",
                      "common GPS-L1 cpValid satellites")
    _require_dd_stage(accounting, "common_pr_cp_valid_identities",
                      "INSUFFICIENT_PR_CP_VALID",
                      "common GPS-L1 prValid+cpValid satellites")
    _require_dd_stage(accounting, "common_half_cycle_valid_identities",
                      "INSUFFICIENT_HALF_CYCLE_VALID",
                      "common GPS-L1 resolved-half-cycle satellites")
    _require_dd_stage(accounting, "common_integer_compatible_identities",
                      "INSUFFICIENT_INTEGER_COMPATIBLE_PHASE",
                      "common GPS-L1 integer-compatible phases")
    position = np.asarray(receiver_ecef_m, dtype=float)
    if position.shape != (3,) or np.any(~np.isfinite(position)):
        raise RawBackendError("invalid DD receiver position")
    first_groups = _gps_l1_measurement_groups(receiver1)
    second_groups = _gps_l1_measurement_groups(receiver2)
    first = {
        identity: first_groups[identity][0]
        for identity in accounting.common_integer_compatible_identities
    }
    second = {
        identity: second_groups[identity][0]
        for identity in accounting.common_integer_compatible_identities
    }
    geometry: dict[SignalIdentity, np.ndarray] = {}
    elevations: dict[SignalIdentity, float] = {}
    states: dict[SignalIdentity, np.ndarray] = {}
    for identity in accounting.common_integer_compatible_identities:
        mean_range = 0.5 * (first[identity].pr_mes_m + second[identity].pr_mes_m)
        if not math.isfinite(mean_range) or not 1.0e6 < mean_range < 1.0e8:
            continue
        try:
            state = provider.state(
                identity, receiver1.gps_week, receiver1.gps_tow_seconds, mean_range
            )
        except RawBackendError:
            continue
        if state.health != 0:
            continue
        try:
            corrected = earth_rotation_correct_satellite(
                state.position_ecef_m, mean_range / _SPEED_OF_LIGHT_MPS
            )
            _azimuth, elevation = azimuth_elevation(position, corrected)
        except RawBackendError:
            continue
        states[identity] = corrected
        if elevation >= minimum_elevation_rad:
            elevations[identity] = elevation
    accounting = replace(
        accounting,
        satellite_state_available_identities=tuple(sorted(states)),
        elevation_eligible_identities=tuple(sorted(elevations)),
    )
    _require_dd_stage(accounting, "satellite_state_available_identities",
                      "INSUFFICIENT_SATELLITE_STATES",
                      "source-backed healthy satellite states")
    _require_dd_stage(accounting, "elevation_eligible_identities",
                      "INSUFFICIENT_ELEVATION_ELIGIBLE",
                      "satellites above the frozen elevation threshold")
    dd_eligible = tuple(
        identity for identity in sorted(elevations)
        if strict_raw_tracking_eligible(first[identity], min_cno_dbhz)
        and strict_raw_tracking_eligible(second[identity], min_cno_dbhz)
    )
    accounting = replace(accounting, dd_eligible_identities=dd_eligible)
    _require_dd_stage(accounting, "dd_eligible_identities", "INSUFFICIENT_DD_DIMENSION",
                      "final quality/state/elevation eligible satellites")
    for identity in dd_eligible:
        geometry[identity] = line_of_sight(position, states[identity])
    candidates = [first[identity] for identity in geometry]
    pivot, switched = select_reference(candidates, elevations, previous_pivot)
    satellites = tuple(identity for identity in sorted(geometry) if identity != pivot)
    dimension = len(satellites)
    code_sd = {identity: second[identity].pr_mes_m - first[identity].pr_mes_m for identity in geometry}
    phase_sd = {
        identity: (
            integer_compatible_carrier_cycles(second[identity])
            - integer_compatible_carrier_cycles(first[identity])
        )
                  * wavelength_m(identity)
        for identity in geometry
    }
    code_dd = np.asarray([code_sd[item] - code_sd[pivot] for item in satellites])
    phase_dd = np.asarray([phase_sd[item] - phase_sd[pivot] for item in satellites])
    observation = np.concatenate((code_dd, phase_dd))
    baseline_rows = np.asarray([-(geometry[item] - geometry[pivot]) for item in satellites])
    baseline_design = np.vstack((baseline_rows, baseline_rows))
    ambiguity_design = np.zeros((2 * dimension, dimension), dtype=float)
    ambiguity_design[dimension:, :] = np.diag([wavelength_m(item) for item in satellites])

    def variances(identity: SignalIdentity) -> tuple[float, float]:
        pr1, cp1, _ = rawx_standard_deviations(first[identity])
        pr2, cp2, _ = rawx_standard_deviations(second[identity])
        wavelength = wavelength_m(identity)
        return pr1 * pr1 + pr2 * pr2, (cp1 * wavelength) ** 2 + (cp2 * wavelength) ** 2

    pivot_code_variance, pivot_phase_variance = variances(pivot)
    code_variances, phase_variances = zip(*(variances(item) for item in satellites))
    code_covariance = correlated_dd_covariance(code_variances, pivot_code_variance)
    phase_covariance = correlated_dd_covariance(phase_variances, pivot_phase_variance)
    covariance = np.block([
        [code_covariance, np.zeros((dimension, dimension))],
        [np.zeros((dimension, dimension)), phase_covariance],
    ])
    if (np.any(~np.isfinite(observation)) or np.any(~np.isfinite(baseline_design))
            or np.any(~np.isfinite(covariance))):
        raise RawBackendError("non-finite DD model")
    model = DoubleDifferenceModel(
        pivot, satellites, observation, ambiguity_design, baseline_design,
        covariance, elevations, accounting, pivot_changed=switched,
    )
    condition = dd_matrix_condition_diagnostics(model)
    if (condition.whitened_design_rank < condition.unknown_count
            or not math.isfinite(condition.whitened_design_condition)):
        raise DoubleDifferenceStageError(
            "NORMAL_MATRIX_RANK_DEFICIENT",
            f"whitened rank {condition.whitened_design_rank} < {condition.unknown_count}",
            accounting,
        )
    return model
