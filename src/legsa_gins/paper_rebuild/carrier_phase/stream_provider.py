"""Causal broadcast states from the original, independently decoded UBX streams.

SFRBX has no reception timestamp in these files. Its availability is bounded
by the next original RAWX in the same stream, exactly as in the prefix producer.
Only arrived frames enter RTKLIB; the two receiver page banks never mix. The
raw carrier/code measurements do not pass through RTKLIB's RINEX conversion.
"""
from __future__ import annotations

from collections import Counter
import ctypes
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from ..horizontal_literature import shared_raw_backend as raw
from .ephemeris import CheckedRtklibProvider

RTKLIB_COMMIT = "180043ee24b6d2b168f98b64be15f69d50046b1a"
BRIDGE_SOURCE_SHA256 = "8449592c9a4bbb0bf77ca6a03b2a31e74ccf6ca41ad94bba123d9b66b1a06854"
UBLOX_SOURCE_SHA256 = "d08da0090cb0a93d3d78c77bc29b658f9f8371485d8855b08b442c6da29dccb7"
GAL_GUARD = "    if (raw->len<44+off) return 0; /* E5b I/NAV */"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_stream_library(rtklib_root: Path, bridge_source: Path, output: Path):
    """Build the narrow ingestion ABI; preserve the existing decoder repair."""
    rtklib_root, bridge_source, output = map(Path, (rtklib_root, bridge_source, output))
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=rtklib_root,
                               text=True).strip() != RTKLIB_COMMIT:
        raise ValueError("stream provider needs the registered RTKLIB revision")
    if sha256(bridge_source) != BRIDGE_SOURCE_SHA256:
        raise ValueError("registered broadcast bridge source differs")
    src = rtklib_root / "src"
    original = src / "rcv/ublox.c"
    if sha256(original) != UBLOX_SOURCE_SHA256:
        raise ValueError("registered original UBX decoder differs")
    output.mkdir(parents=True, exist_ok=False)
    text = original.read_text()
    if text.count(GAL_GUARD) != 1:
        raise ValueError("the registered Galileo guard is not unique")
    overlay = output / "ublox_e1b_8word.c"
    overlay.write_text(text.replace(GAL_GUARD,
        "    /* E1B has 8 words; retain the existing bounds/CRC/IOD checks. */"))
    main = "rtkcmn rinex sbas preceph rcvraw convrnx rtcm rtcm2 rtcm3 rtcm3e pntpos ephemeris ionex lambda".split()
    receivers = "novatel ss2 ublox crescent skytraq javad nvs binex rt17 septentrio".split()
    wrapper = Path(__file__).with_name("stream_rtklib.c")
    sources = [wrapper, bridge_source.with_name("rtklib_compat.c")] + [src / (name+".c") for name in main]
    sources += [overlay if name == "ublox" else src / "rcv" / (name+".c") for name in receivers]
    pins = {str(p): sha256(p) for p in [src / "rtklib.h", bridge_source, original, *sources]}
    library = output / "libcausal_carrier_rtklib.so"
    command = ["gcc", "-O2", "-shared", "-fPIC", "-Wl,-Bsymbolic",
        "-I"+str(src), "-I"+str(bridge_source.parent), "-DTRACE", "-DENAGLO",
        "-DENAQZS", "-DENAGAL", "-DENACMP", "-DENAIRN", "-DNFREQ=5", "-DNEXOBS=3",
        *map(str, sources), "-lm", "-lrt", "-o", str(library)]
    record = dict(argv=command, source_sha256=pins, rtklib_commit=RTKLIB_COMMIT,
        patch_scope="existing E1B 8-word length guard repair only; receiver CRC/IOD/health unchanged")
    (output / "BUILD.json").write_text(json.dumps(record, indent=2)+"\n")
    run = subprocess.run(command, capture_output=True, text=True)
    (output / "stdout.log").write_text(run.stdout)
    (output / "stderr.log").write_text(run.stderr)
    if run.returncode:
        raise RuntimeError("causal broadcast bridge build failed: "+run.stderr[-3000:])
    if any(sha256(Path(path)) != expected for path, expected in pins.items()):
        raise RuntimeError("source changed during stream bridge build")
    record["library_sha256"] = sha256(library)
    (output / "BUILD.json").write_text(json.dumps(record, indent=2)+"\n")
    return library, record


def relative_time(epoch, base_time):
    return 315964800.+epoch.gps_week*604800.+epoch.gps_tow_seconds-epoch.leap_seconds-base_time


def wrap_frame(message_class, message_id, payload):
    body = bytes([message_class, message_id])+struct.pack("<H", len(payload))+payload
    return b"\xb5\x62"+body+bytes(raw.ubx_checksum(body))


@dataclass(frozen=True)
class ArrivedPacket:
    time_s: float
    epoch: raw.RawxEpoch
    # Original frame index, message kind, complete original UBX bytes.
    frames: tuple[tuple[int, int, bytes], ...]


def read_arrival_packets(source: Path, expected_sha256: str, base_time: float):
    payload = Path(source).read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("original UBX source identity differs")
    packets, pending, counts = [], [], Counter()
    for index, (cls, ident, body) in enumerate(raw.iter_ubx_frames(payload)):
        counts["source_frames"] += 1
        if (cls, ident) == (2, 0x13):
            sfrbx = raw.decode_sfrbx(body)
            if sfrbx.gnss_id == 2 and (sfrbx.version != 2 or sfrbx.reserved1 != 1):
                counts["Gal_non_E1B_frames_excluded_same_as_existing_provider"] += 1
                continue
            pending.append((index, ident, wrap_frame(cls, ident, body)))
        elif (cls, ident) == (2, 0x15):
            epoch = raw.decode_rawx(body)
            t = relative_time(epoch, base_time)
            if packets and t <= packets[-1].time_s:
                raise ValueError("original RAWX must be strictly increasing")
            pending.append((index, ident, wrap_frame(cls, ident, body)))
            packets.append(ArrivedPacket(t, epoch, tuple(pending)))
            pending = []
    counts["unreleased_trailing_SFRBX_frames_without_next_RAWX"] = len(pending)
    if not packets:
        raise ValueError("no original RAWX time tags")
    return packets, dict(counts)


class StreamingBroadcastBackend(raw.RtklibBroadcastProvider):
    """Reuse the existing checked state ABI, owning an incremental raw context."""
    def __init__(self, library, first_epoch):
        self._library = ctypes.CDLL(str(library))
        self._configure_abi()
        lib = self._library
        lib.legsa_stream_new.argtypes = [ctypes.c_int, ctypes.c_double]
        lib.legsa_stream_new.restype = ctypes.c_void_p
        lib.legsa_stream_nav.argtypes = [ctypes.c_void_p]
        lib.legsa_stream_nav.restype = ctypes.c_void_p
        lib.legsa_stream_free.argtypes = [ctypes.c_void_p]
        lib.legsa_stream_free.restype = None
        lib.legsa_stream_frame.argtypes = [ctypes.c_void_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.legsa_stream_frame.restype = ctypes.c_int
        lib.legsa_stream_selected.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double, ctypes.c_int]
        lib.legsa_stream_selected.restype = ctypes.c_int
        self._stream = lib.legsa_stream_new(first_epoch.gps_week, first_epoch.gps_tow_seconds)
        if not self._stream:
            raise RuntimeError("RTKLIB raw context allocation failed")
        self._handle = lib.legsa_stream_nav(self._stream)
        self.ephemeris_events, self.decoder_rejections = [], []

    def feed(self, receiver, packet):
        for frame_index, kind, frame in packet.frames:
            payload = (ctypes.c_ubyte*len(frame)).from_buffer_copy(frame)
            satellite = ctypes.c_int()
            result = self._library.legsa_stream_frame(self._stream, receiver, payload,
                len(frame), ctypes.byref(satellite))
            if result <= -100:
                raise RuntimeError("stream ABI failure: "+str(result))
            if result < 0:
                # A received page that fails the unchanged native decoder is
                # not an ephemeris; preserve it as a physical qualification.
                self.decoder_rejections.append(dict(receiver=receiver,
                    available_time_s=packet.time_s, frame_index=frame_index,
                    message_id=kind, decoder_status=result))
            elif result > 0:
                if result != len(self.ephemeris_events)+1:
                    raise RuntimeError("ephemeris provenance index differs")
                self.ephemeris_events.append(dict(receiver=receiver,
                    available_time_s=packet.time_s, frame_index=frame_index,
                    satellite_number=satellite.value, record_index=result-1))

    def selected_source(self, identity, week, tow):
        index = self._library.legsa_stream_selected(self._stream, week, tow,
                                                   self.satellite_number(identity))
        if index < 0:
            raise raw.RawBackendError("no arrived broadcast ephemeris")
        return dict(self.ephemeris_events[index])

    def close(self):
        stream = getattr(self, "_stream", None)
        if stream:
            self._library.legsa_stream_free(stream)
            self._stream = self._handle = None


class CausalUbxProvider(CheckedRtklibProvider):
    """Checked per-signal CDMA geometry from the arrived ephemeris history."""
    status = "CAUSAL_ORIGINAL_UBX_SFRBX_RTKLIB_BROADCAST"

    def __init__(self, library, packets_by_receiver):
        self.packets = packets_by_receiver
        self.cursors = {rx: 0 for rx in self.packets}
        first = min((items[0] for items in self.packets.values()), key=lambda p: p.time_s)
        self.backend = StreamingBroadcastBackend(library, first.epoch)
        self.last_qualification = {}
        self.time_s = float("-inf")

    def advance(self, time_s):
        if time_s < self.time_s:
            raise ValueError("broadcast source cannot move backward")
        arrived = []
        for rx, items in self.packets.items():
            cursor = self.cursors[rx]
            while cursor < len(items) and items[cursor].time_s <= time_s:
                arrived.append((items[cursor].time_s, rx, items[cursor]))
                cursor += 1
            self.cursors[rx] = cursor
        for _, rx, packet in sorted(arrived, key=lambda row: (row[0], row[1])):
            self.backend.feed(rx, packet)
        self.time_s = float(time_s)
        self.last_qualification = {}

    def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
        result = super().state(identity, gps_week, gps_tow_seconds, pseudorange_m)
        source = self.backend.selected_source(identity, gps_week, gps_tow_seconds)
        if source["available_time_s"] > self.time_s:
            raise RuntimeError("future broadcast state entered current geometry")
        self.last_qualification[raw.identity_text(identity)].update(source)
        return result
