"""Parse UBX-RXM-RAWX frames and export satellite-level Doppler epochs.

中文说明：本解析器只消费 RAWX 卫星级 doMes 观测；NAV-PVT velocity、trace 和
final_v23 输出均不能作为 raw Doppler factor 输入。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .raw_doppler_types import LIGHT_SPEED_MPS, RawDopplerMeasurement
from .ubx_raw_binary_rebuilder import iter_ubx_frames, parse_bytes_cell


GNSS_NAMES = {0: "GPS", 1: "SBAS", 2: "GALILEO", 3: "BEIDOU", 5: "QZSS", 6: "GLONASS"}


def wavelength_m(gnss_id: int, sig_id: int, freq_id: int) -> float | None:
    # 中文说明：只在明确可识别频点时解算波长；未知信号进入 wavelength_missing 统计。
    if gnss_id in (0, 5):
        if sig_id in (0, 3, 4, 6, 7):
            return LIGHT_SPEED_MPS / 1_575_420_000.0
        if sig_id in (8, 9):
            return LIGHT_SPEED_MPS / 1_227_600_000.0
    if gnss_id == 2:
        if sig_id in (0, 1, 5, 6):
            return LIGHT_SPEED_MPS / 1_575_420_000.0
        if sig_id in (7, 8):
            return LIGHT_SPEED_MPS / 1_176_450_000.0
    if gnss_id == 3:
        if sig_id in (0, 1, 2):
            return LIGHT_SPEED_MPS / 1_561_098_000.0
        if sig_id in (5, 6, 7):
            return LIGHT_SPEED_MPS / 1_575_420_000.0
    if gnss_id == 6:
        channel = freq_id - 7
        return LIGHT_SPEED_MPS / (1_602_000_000.0 + channel * 562_500.0)
    return None


def _frame_time(frame: bytes, csv_time: float | None) -> float:
    if csv_time is not None:
        return csv_time
    payload = frame[6:-2]
    return float(struct.unpack_from("<d", payload, 0)[0])


def parse_rawx_frame(frame: bytes, *, source_file: str = "", csv_time: float | None = None) -> list[RawDopplerMeasurement]:
    if len(frame) < 24 or frame[2] != 0x02 or frame[3] != 0x15:
        return []
    payload = frame[6:-2]
    if len(payload) < 16:
        return []
    rcv_tow = struct.unpack_from("<d", payload, 0)[0]
    week = struct.unpack_from("<H", payload, 8)[0]
    num_meas = payload[11]
    out: list[RawDopplerMeasurement] = []
    offset = 16
    for _ in range(num_meas):
        if offset + 32 > len(payload):
            break
        pr_mes, cp_mes, do_mes = struct.unpack_from("<ddf", payload, offset)
        gnss_id = payload[offset + 20]
        sv_id = payload[offset + 21]
        sig_id = payload[offset + 22]
        freq_id = payload[offset + 23]
        locktime = struct.unpack_from("<H", payload, offset + 24)[0]
        cno = payload[offset + 26]
        do_stdev = payload[offset + 29]
        trk_stat = payload[offset + 30]
        _ = locktime
        out.append(
            RawDopplerMeasurement(
                time=_frame_time(frame, csv_time),
                rcv_tow=rcv_tow,
                week=week,
                gnss_id=gnss_id,
                sv_id=sv_id,
                sig_id=sig_id,
                freq_id=freq_id,
                pr_mes=pr_mes,
                cp_mes=cp_mes,
                do_mes_hz=do_mes,
                cno=float(cno),
                do_stdev=do_stdev,
                trk_stat=trk_stat,
                wavelength_m=wavelength_m(gnss_id, sig_id, freq_id),
                source_file=source_file,
            )
        )
        offset += 32
    return out


def parse_rawx_from_ubx(path: str | Path) -> list[RawDopplerMeasurement]:
    path = Path(path)
    if not path.exists():
        return []
    measurements: list[RawDopplerMeasurement] = []
    for frame in iter_ubx_frames(path.read_bytes()):
        measurements.extend(parse_rawx_frame(frame, source_file=path.name))
    return measurements


def parse_rawx_from_csv(path: str | Path) -> list[RawDopplerMeasurement]:
    path = Path(path)
    measurements: list[RawDopplerMeasurement] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "data" not in (reader.fieldnames or []):
            return []
        for row in reader:
            name = (row.get("name") or "").upper()
            if "RAWX" not in name:
                continue
            try:
                csv_time = float(row.get("Time", "nan"))
            except ValueError:
                csv_time = None
            for frame in iter_ubx_frames(parse_bytes_cell(row.get("data", ""))):
                measurements.extend(parse_rawx_frame(frame, source_file=path.name, csv_time=csv_time))
    return measurements


def group_epochs(measurements: Iterable[RawDopplerMeasurement]) -> dict[float, list[RawDopplerMeasurement]]:
    epochs: dict[float, list[RawDopplerMeasurement]] = defaultdict(list)
    for meas in measurements:
        epochs[round(meas.rcv_tow, 3)].append(meas)
    return dict(sorted(epochs.items()))


def report_measurements(measurements: list[RawDopplerMeasurement]) -> dict[str, Any]:
    epochs = group_epochs(measurements)
    constellation_counts = Counter(GNSS_NAMES.get(m.gnss_id, f"GNSS_{m.gnss_id}") for m in measurements)
    signal_counts = Counter(f"{m.gnss_id}:{m.sig_id}" for m in measurements)
    valid = [m for m in measurements if math.isfinite(m.do_mes_hz) and abs(m.do_mes_hz) > 0.0]
    wavelength_resolved = [m for m in measurements if m.wavelength_m is not None]
    times = [m.time for m in measurements]
    weeks = [m.week for m in measurements if m.week > 0]
    return {
        "rawx_epoch_count": len(epochs),
        "doppler_measurement_count": len(measurements),
        "constellation_counts": dict(sorted(constellation_counts.items())),
        "signal_counts": dict(sorted(signal_counts.items())),
        "wavelength_resolved_count": len(wavelength_resolved),
        "wavelength_missing_count": len(measurements) - len(wavelength_resolved),
        "doMes_valid_count": len(valid),
        "doMes_invalid_count": len(measurements) - len(valid),
        "rawx_time_range": [min(times), max(times)] if times else [],
        "gps_week_available": bool(weeks),
        "raw_doppler_source": "UBX-RXM-RAWX doMes",
        "pvt_velocity_used": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_epochs_jsonl(measurements: list[RawDopplerMeasurement], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for meas in measurements:
            handle.write(json.dumps(meas.__dict__, sort_keys=True) + "\n")


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_fix_root(fix_root: str | Path, rebuilt_ubx_paths: list[str | Path] | None = None) -> list[RawDopplerMeasurement]:
    root = Path(fix_root)
    measurements: list[RawDopplerMeasurement] = []
    if rebuilt_ubx_paths:
        for path in rebuilt_ubx_paths:
            measurements.extend(parse_rawx_from_ubx(path))
    if not measurements:
        for name in ("gnss1-raw.csv", "gnss2-raw.csv"):
            path = root / name
            if path.exists():
                measurements.extend(parse_rawx_from_csv(path))
    return measurements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--rebuilt-ubx", action="append", default=[])
    args = parser.parse_args(argv)
    measurements = parse_fix_root(args.fix_root, args.rebuilt_ubx)
    write_report(report_measurements(measurements), args.output_json)
    write_epochs_jsonl(measurements, args.output_jsonl)
    print(f"Wrote {args.output_json} and {args.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
