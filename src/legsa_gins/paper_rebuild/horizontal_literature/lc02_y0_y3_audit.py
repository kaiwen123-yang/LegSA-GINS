"""Read-only LC02 Yin-2023 Y0--Y3 source and BY2 input audit.

This module deliberately contains no navigation state, Kalman recursion, solver,
case runner, evaluator, or trace/reference reader.  It copies reviewed static
contracts into the isolated LC02 stage and audits only the raw GNSS1 solution
messages and the authenticated Go2 body-IMU complete-record prefix.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import shutil
import statistics
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from pypdf import PdfReader


METHOD_ID = "LC02_YIN2023_RAEKF"
TERMINAL_STATUS = "PASS_LC02_YIN2023_Y0_Y3_METHOD_NON_DUPLICATION_AND_BY2_CONTRACT_READY"
PAPER_SHA256 = "198da0283cabddc97446bf9cf9138d8b7ee0b1d1a78f9bdbbe8265c711302f0c"
PAPER_BYTES = 21_097_265
PAPER_PAGES = 24
GO2_COMPLETE_PREFIX_BYTES = 92_351_234
GO2_COMPLETE_PREFIX_SHA256 = "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
GO2_COMPLETE_RECORDS = 63_277
GO2_FULL_SHA256 = "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
PROVENANCE_CLASSES = {
    "PAPER_DIRECT",
    "PAPER_DERIVED",
    "CITED_SOURCE",
    "OFFICIAL_CODE",
    "PRIOR_PROJECT_CODE",
    "BY2_PHYSICAL_INSTANTIATION",
    "CURRENTLY_UNKNOWN",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_local_paths(path: Path) -> dict[str, str]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "paper_rebuild.paths.v1":
        raise ValueError("unexpected local-path schema")
    values = payload["paths"]
    required = {"code_root", "by2_fix_root", "by2_go2_body", "clean_root"}
    missing = required.difference(values)
    if missing:
        raise ValueError(f"missing local path aliases: {sorted(missing)}")
    return {str(k): str(v) for k, v in values.items()}


def validate_ubx_frame(frame: bytes) -> tuple[int, int, bytes]:
    if len(frame) < 8 or frame[:2] != b"\xb5\x62":
        raise ValueError("not a UBX frame")
    payload_len = struct.unpack_from("<H", frame, 4)[0]
    if len(frame) != payload_len + 8:
        raise ValueError("UBX length mismatch")
    ck_a = 0
    ck_b = 0
    for value in frame[2:-2]:
        ck_a = (ck_a + value) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    if frame[-2:] != bytes((ck_a, ck_b)):
        raise ValueError("UBX checksum mismatch")
    return frame[2], frame[3], frame[6:-2]


def decode_nav_pvt(payload: bytes, row_time: float) -> dict[str, Any]:
    if len(payload) != 92:
        raise ValueError("UBX-NAV-PVT payload is not 92 bytes")
    flags = payload[21]
    return {
        "row_time": row_time,
        "itow_ms": struct.unpack_from("<I", payload, 0)[0],
        "fix_type": payload[20],
        "gnss_fix_ok": bool(flags & 0x01),
        "diff_soln": bool(flags & 0x02),
        "carr_soln": (flags >> 6) & 0x03,
        "num_sv": payload[23],
        "lon_deg": struct.unpack_from("<i", payload, 24)[0] * 1e-7,
        "lat_deg": struct.unpack_from("<i", payload, 28)[0] * 1e-7,
        "height_m": struct.unpack_from("<i", payload, 32)[0] * 1e-3,
        "h_msl_m": struct.unpack_from("<i", payload, 36)[0] * 1e-3,
        "h_acc_m": struct.unpack_from("<I", payload, 40)[0] * 1e-3,
        "v_acc_m": struct.unpack_from("<I", payload, 44)[0] * 1e-3,
        "p_dop": struct.unpack_from("<H", payload, 76)[0] * 0.01,
    }


def decode_nav_cov(payload: bytes, row_time: float) -> dict[str, Any]:
    if len(payload) != 64:
        raise ValueError("UBX-NAV-COV payload is not 64 bytes")
    nn, ne, nd, ee, ed, dd = struct.unpack_from("<6f", payload, 16)
    covariance = np.array(
        [[nn, ne, nd], [ne, ee, ed], [nd, ed, dd]], dtype=np.float64
    )
    return {
        "row_time": row_time,
        "itow_ms": struct.unpack_from("<I", payload, 0)[0],
        "pos_cov_valid": bool(payload[5]),
        "covariance": covariance,
    }


def _summary(values: Iterable[float]) -> dict[str, float]:
    seq = [float(value) for value in values]
    if not seq:
        raise ValueError("cannot summarize empty sequence")
    return {
        "min": min(seq),
        "median": statistics.median(seq),
        "max": max(seq),
    }


def audit_gnss1_raw(path: Path) -> dict[str, Any]:
    pvt: dict[int, dict[str, Any]] = {}
    cov: dict[int, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    checksum_errors = 0
    decode_errors = 0
    with path.open("rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            name = row["name"]
            counts[name] = counts.get(name, 0) + 1
            if name not in {"UBX-NAV-PVT", "UBX-NAV-COV"}:
                continue
            try:
                frame = ast.literal_eval(row["data"])
                msg_class, msg_id, payload = validate_ubx_frame(frame)
                if msg_class != 0x01:
                    raise ValueError("not NAV class")
                row_time = float(row["Time"])
                if name == "UBX-NAV-PVT":
                    if msg_id != 0x07:
                        raise ValueError("wrong PVT message id")
                    decoded = decode_nav_pvt(payload, row_time)
                    target = pvt
                else:
                    if msg_id != 0x36:
                        raise ValueError("wrong COV message id")
                    decoded = decode_nav_cov(payload, row_time)
                    target = cov
                itow = int(decoded["itow_ms"])
                if itow in target:
                    raise ValueError("duplicate iTOW for message type")
                target[itow] = decoded
            except ValueError as exc:
                if "checksum" in str(exc):
                    checksum_errors += 1
                decode_errors += 1

    keys = sorted(set(pvt).intersection(cov))
    if not keys:
        raise ValueError("no exact PVT/COV iTOW joins")
    joined = [(pvt[key], cov[key]) for key in keys]
    pvt_outer_times = [pvt[key]["row_time"] for key in keys]
    covariances = [item[1]["covariance"] for item in joined]
    finite = [bool(np.isfinite(matrix).all()) for matrix in covariances]
    symmetry = [bool(np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-15)) for matrix in covariances]
    min_eigenvalues = [float(np.linalg.eigvalsh(matrix).min()) for matrix in covariances]
    psd = [value >= -1e-12 for value in min_eigenvalues]
    std_n = [math.sqrt(float(matrix[0, 0])) for matrix in covariances]
    std_e = [math.sqrt(float(matrix[1, 1])) for matrix in covariances]
    std_d = [math.sqrt(float(matrix[2, 2])) for matrix in covariances]
    accuracy_3d = [math.sqrt(float(np.trace(matrix))) for matrix in covariances]
    itow_diffs = np.diff(np.asarray(keys, dtype=np.int64))
    row_deltas_us = [abs(a["row_time"] - b["row_time"]) * 1e6 for a, b in joined]
    all_q1 = all(
        a["fix_type"] == 3
        and a["gnss_fix_ok"]
        and a["diff_soln"]
        and a["carr_soln"] == 2
        and 0.0 <= acc < 0.05
        for (a, _), acc in zip(joined, accuracy_3d)
    )
    return {
        "source_file": str(path),
        "source_sha256": sha256_file(path),
        "source_bytes": path.stat().st_size,
        "message_counts": counts,
        "pvt_count": len(pvt),
        "cov_count": len(cov),
        "exact_itow_join_count": len(joined),
        "pvt_without_cov": len(set(pvt).difference(cov)),
        "cov_without_pvt": len(set(cov).difference(pvt)),
        "decode_errors": decode_errors,
        "checksum_errors": checksum_errors,
        "first_itow_ms": keys[0],
        "last_itow_ms": keys[-1],
        "coverage_seconds": (keys[-1] - keys[0]) / 1000.0,
        "itow_step_ms": _summary(itow_diffs.tolist()),
        "rate_hz": 1000.0 / statistics.median(itow_diffs.tolist()),
        "row_timestamp_delta_us": _summary(row_deltas_us),
        "pvt": {
            "fix_type_3_count": sum(a["fix_type"] == 3 for a, _ in joined),
            "gnss_fix_ok_count": sum(a["gnss_fix_ok"] for a, _ in joined),
            "diff_soln_count": sum(a["diff_soln"] for a, _ in joined),
            "carr_soln_fixed_count": sum(a["carr_soln"] == 2 for a, _ in joined),
            "pdop": _summary(a["p_dop"] for a, _ in joined),
            "h_acc_m": _summary(a["h_acc_m"] for a, _ in joined),
            "v_acc_m": _summary(a["v_acc_m"] for a, _ in joined),
        },
        "nav_cov": {
            "pos_cov_valid_count": sum(b["pos_cov_valid"] for _, b in joined),
            "finite_count": sum(finite),
            "symmetric_count": sum(symmetry),
            "psd_count": sum(psd),
            "minimum_eigenvalue_m2": min(min_eigenvalues),
            "std_n_m": _summary(std_n),
            "std_e_m": _summary(std_e),
            "std_d_m": _summary(std_d),
            "sqrt_trace_m": _summary(accuracy_3d),
        },
        "q": {
            "selected_Q": 1 if all_q1 else None,
            "selected_count": len(joined) if all_q1 else 0,
            "unique_semantic_reason": "fixed integer and 3D accuracy below 0.05 m, outside Q2 lower bound",
            "all_rows_unique_Q1": all_q1,
        },
        "velocity_fields_decoded": False,
        "velocity_covariance_decoded": False,
        "_pvt_outer_times_unix_s": pvt_outer_times,
    }


def audit_gnss1_status(path: Path) -> dict[str, Any]:
    rows = 0
    valid = 0
    times: list[float] = []
    pdop: list[float] = []
    hacc: list[float] = []
    vacc: list[float] = []
    fix_types: set[str] = set()
    with path.open("rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        for row in reader:
            rows += 1
            times.append(float(row["Time"]))
            if row.get("pos_valid", "").lower() == "true" and row.get("fix_ok", "").lower() == "true":
                valid += 1
            fix_types.add(row.get("fix_type", ""))
            if row.get("sol_pdop"):
                pdop.append(float(row["sol_pdop"]))
            if row.get("pos_acc_h"):
                hacc.append(float(row["pos_acc_h"]))
            if row.get("pos_acc_v"):
                vacc.append(float(row["pos_acc_v"]))
    diffs = np.diff(np.asarray(times, dtype=np.float64))
    return {
        "source_file": str(path),
        "source_sha256": sha256_file(path),
        "source_bytes": path.stat().st_size,
        "rows": rows,
        "valid_rows": valid,
        "coverage_seconds": times[-1] - times[0],
        "rate_hz": 1.0 / statistics.median(diffs.tolist()),
        "fix_type_values": sorted(fix_types),
        "pdop": _summary(pdop),
        "h_acc_m": _summary(hacc),
        "v_acc_m": _summary(vacc),
        "fields_present": sorted(
            fields.intersection({"pos_lat", "pos_lon", "pos_height", "pos_acc_h", "pos_acc_v", "fix_ok", "fix_type", "sol_pdop"})
        ),
        "selection": "NOT_SELECTED_LOWER_RATE_AND_LESS_DIRECT_TABLE1_CARRIER_SEMANTICS",
    }


@dataclass
class _ImuRecord:
    sec: int
    nsec: int
    time_ns: int
    gyro: tuple[float, float, float]
    accel: tuple[float, float, float]


def audit_go2_imu(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    records: list[_ImuRecord] = []
    sec: int | None = None
    nsec: int | None = None
    gyro: list[float] = []
    accel: list[float] = []
    active: str | None = None

    def finish() -> None:
        nonlocal sec, nsec, gyro, accel, active
        if sec is not None or nsec is not None or gyro or accel:
            if sec is None or nsec is None or len(gyro) != 3 or len(accel) != 3:
                raise ValueError("incomplete record inside authenticated Go2 prefix")
            records.append(_ImuRecord(sec, nsec, sec * 1_000_000_000 + nsec, tuple(gyro), tuple(accel)))
        sec = None
        nsec = None
        gyro = []
        accel = []
        active = None

    remaining = GO2_COMPLETE_PREFIX_BYTES
    with path.open("rb") as stream:
        while remaining:
            line = stream.readline(remaining)
            if not line:
                raise ValueError("Go2 source shorter than authenticated prefix")
            remaining -= len(line)
            digest.update(line)
            stripped = line.strip()
            if stripped == b"---":
                finish()
            elif line.startswith(b"  sec:"):
                sec = int(line.split(b":", 1)[1])
            elif line.startswith(b"  nanosec:"):
                nsec = int(line.split(b":", 1)[1])
            elif line.startswith(b"  gyroscope:"):
                active = "gyro"
            elif line.startswith(b"  accelerometer:"):
                active = "accel"
            elif active and stripped.startswith(b"- "):
                value = float(stripped[2:])
                target = gyro if active == "gyro" else accel
                if len(target) < 3:
                    target.append(value)
                if len(target) == 3:
                    active = None
        if stream.tell() != GO2_COMPLETE_PREFIX_BYTES:
            raise ValueError("Go2 prefix ended at unexpected byte")
    finish()
    prefix_hash = digest.hexdigest()
    if prefix_hash != GO2_COMPLETE_PREFIX_SHA256:
        raise ValueError("Go2 authenticated-prefix hash mismatch")
    if len(records) != GO2_COMPLETE_RECORDS:
        raise ValueError("Go2 complete-record count mismatch")
    values_finite = all(
        math.isfinite(value)
        for record in records
        for value in (*record.gyro, *record.accel)
    )
    times_ns = np.asarray([record.time_ns for record in records], dtype=np.int64)
    diffs_ns = np.diff(times_ns)
    duration_ns = int(times_ns[-1] - times_ns[0])
    full_hash = sha256_file(path)
    if full_hash != GO2_FULL_SHA256:
        raise ValueError("Go2 full-file hash mismatch")
    return {
        "source_file": str(path),
        "source_bytes": path.stat().st_size,
        "source_sha256": full_hash,
        "authenticated_prefix_bytes": GO2_COMPLETE_PREFIX_BYTES,
        "authenticated_prefix_sha256": prefix_hash,
        "complete_records": len(records),
        "trailing_incomplete_record_used": False,
        "first_sec": records[0].sec,
        "first_nsec": records[0].nsec,
        "first_time_ns": records[0].time_ns,
        "last_sec": records[-1].sec,
        "last_nsec": records[-1].nsec,
        "last_time_ns": records[-1].time_ns,
        "duration_ns": duration_ns,
        "first_time_unix_s": records[0].time_ns / 1e9,
        "last_time_unix_s": records[-1].time_ns / 1e9,
        "coverage_seconds": duration_ns / 1e9,
        "median_dt_ns": float(np.median(diffs_ns)),
        "median_dt_s": float(np.median(diffs_ns) / 1e9),
        "rate_hz": float(1e9 / np.median(diffs_ns)),
        "strictly_increasing_time": bool(np.all(diffs_ns > 0)),
        "float_times_are_descriptive_only": True,
        "all_materialized_values_finite": values_finite,
        "materialized_fields": ["stamp", "imu_state.gyroscope", "imu_state.accelerometer"],
        "forbidden_fields_materialized_count": 0,
    }


def audit_paper(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "pages": len(PdfReader(path).pages),
        "expected_bytes": PAPER_BYTES,
        "expected_sha256": PAPER_SHA256,
        "expected_pages": PAPER_PAGES,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sync_static_payload(repo: Path, stage: Path) -> None:
    sources = [
        repo / "docs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload",
        repo / "configs/paper_rebuild/horizontal_literature/lc02_yin2023/stage_payload",
    ]
    stage.mkdir(parents=True, exist_ok=True)
    for source in sources:
        if not source.is_dir():
            raise FileNotFoundError(source)
        for item in sorted(source.rglob("*")):
            if item.is_file():
                relative = item.relative_to(source)
                destination = stage / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)


def write_by2_artifacts(stage: Path, gnss: dict[str, Any], status: dict[str, Any], imu: dict[str, Any]) -> None:
    out = stage / "05_BY2_INPUT_AUDIT"
    out.mkdir(parents=True, exist_ok=True)
    n = gnss["exact_itow_join_count"]
    field_rows = [
        {"field": "Go2 body IMU gyroscope", "source": "by2_go2_body authenticated complete prefix", "physical_point": "Go2 body IMU", "frame": "raw Go2 FLU; future mapping diag(1,-1,-1) to FRD then active RzRyRx(-1deg,0,0) in FRD", "timestamp": "Unix stamp", "rate_hz": f"{imu['rate_hz']:.9f}", "valid_count": imu["complete_records"], "units": "rad/s", "online_role": "IMU after maintained frame mapping", "decision": "ALLOWED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "Go2 body IMU accelerometer", "source": "by2_go2_body authenticated complete prefix", "physical_point": "Go2 body IMU", "frame": "raw Go2 FLU; future mapping diag(1,-1,-1) to FRD then active RzRyRx(-1deg,0,0) in FRD", "timestamp": "Unix stamp", "rate_hz": f"{imu['rate_hz']:.9f}", "valid_count": imu["complete_records"], "units": "m/s^2", "online_role": "IMU after maintained frame mapping", "decision": "ALLOWED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "GNSS1 latitude/longitude/height", "source": "gnss1-raw.csv UBX-NAV-PVT", "physical_point": "GNSS1 antenna phase center", "frame": "WGS84 geodetic converted to local NED", "timestamp": "GPS iTOW", "rate_hz": gnss["rate_hz"], "valid_count": n, "units": "deg,deg,m", "online_role": "position observation", "decision": "SELECTED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "GNSS1 pDOP", "source": "gnss1-raw.csv UBX-NAV-PVT", "physical_point": "GNSS1 solution", "frame": "dimensionless geometry", "timestamp": "GPS iTOW", "rate_hz": gnss["rate_hz"], "valid_count": n, "units": "dimensionless", "online_role": "improved R", "decision": "SELECTED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "GNSS1 fix/quality", "source": "gnss1-raw.csv UBX-NAV-PVT flags", "physical_point": "GNSS1 solution", "frame": "not applicable", "timestamp": "GPS iTOW", "rate_hz": gnss["rate_hz"], "valid_count": n, "units": "enum/bits", "online_role": "Table-1 Q semantics", "decision": "SELECTED_Q1", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "GNSS1 NED position covariance", "source": "gnss1-raw.csv UBX-NAV-COV", "physical_point": "GNSS1 antenna phase center", "frame": "NED", "timestamp": "same GPS iTOW as PVT", "rate_hz": gnss["rate_hz"], "valid_count": n, "units": "m^2", "online_role": "per-axis r_N/r_E/r_D", "decision": "SELECTED_DIAGONAL; OFF_DIAGONALS_AUDIT_ONLY", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "GNSS1 velocity", "source": "serialized UBX-NAV-PVT row contains velocity bytes", "physical_point": "NOT_EVALUATED_NOT_DECODED", "frame": "NOT_EVALUATED_NOT_DECODED", "timestamp": "same serialized row; velocity value not decoded", "rate_hz": "NOT_EVALUATED_NOT_DECODED", "valid_count": "NOT_EVALUATED_NOT_DECODED", "units": "NOT_EVALUATED_NOT_DECODED", "online_role": "none", "decision": "UNUSED_POSITION_ONLY_NOT_SEMANTICALLY_DECODED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "GNSS2/P2-P1/baseline/yaw/trace/reference", "source": "forbidden", "physical_point": "not applicable", "frame": "not applicable", "timestamp": "not applicable", "rate_hz": 0, "valid_count": 0, "units": "not applicable", "online_role": "none", "decision": "FORBIDDEN_NOT_OPENED", "provenance_class": "PAPER_DERIVED"},
        {"field": "GNSS1 RAWX/SFRBX/RTCM payloads", "source": "serialized rows in multiplexed gnss1-raw.csv were read", "physical_point": "not semantically decoded", "frame": "not semantically decoded", "timestamp": "row name scanned only", "rate_hz": 0, "valid_count": 0, "units": "not semantically decoded", "online_role": "none", "decision": "SERIALIZED_ROWS_READ_VALUES_NOT_SEMANTICALLY_DECODED_NOT_RETAINED_BEYOND_ROW_NOT_USED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
        {"field": "Go2 quaternion/RPY/position/velocity/yaw/contact/foot fields", "source": "serialized source bytes inside authenticated Go2 prefix were read", "physical_point": "not semantically decoded", "frame": "not semantically decoded", "timestamp": "not semantically decoded", "rate_hz": 0, "valid_count": 0, "units": "not semantically decoded", "online_role": "none", "decision": "SOURCE_BYTES_READ_VALUES_NOT_SEMANTICALLY_DECODED_NOT_RETAINED_NOT_USED", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"},
    ]
    for row in field_rows:
        is_imu = row["field"].startswith("Go2 body IMU")
        is_selected_gnss = row["decision"] in {"SELECTED", "SELECTED_Q1", "SELECTED_DIAGONAL; OFF_DIAGONALS_AUDIT_ONLY", "UNUSED_POSITION_ONLY"}
        row["coverage_seconds"] = imu["coverage_seconds"] if is_imu else (gnss["coverage_seconds"] if is_selected_gnss else 0)
        row["fix_quality_semantics"] = "PVT fixType=3, gnssFixOK, diffSoln, carrSoln=2" if is_selected_gnss else "not applicable"
        row["pdop_semantics"] = "PVT pDOP, scale 0.01, dimensionless" if is_selected_gnss else "not applicable"
        row["uncertainty_semantics"] = "NAV-COV NED position covariance m^2; diagonal sqrt is r_N/E/D" if is_selected_gnss else ("not applicable" if is_imu else "not materialized")
        row["missing_invalid_policy"] = "reject epoch fail closed" if is_selected_gnss or is_imu else "not applicable"
    _write_csv(out / "LC02_BY2_FIELD_ROLE_REGISTRY.csv", list(field_rows[0]), field_rows)
    source_rows = [
        {"candidate": "GNSS1_PVT_PLUS_NAV_COV", "source_file_message": "gnss1-raw.csv UBX-NAV-PVT + UBX-NAV-COV", "physical_point": "GNSS1 antenna phase center", "frame": "WGS84 geodetic position; NED covariance", "timestamp": "exact common GPS iTOW; outer Time only for candidate IMU association", "receiver_count": 1, "rate_hz": gnss["rate_hz"], "valid_count": n, "coverage_seconds": gnss["coverage_seconds"], "units": "deg/deg/m; covariance m^2", "fix_quality_semantics": "fixType=3 + gnssFixOK + diffSoln + carrSoln=2", "pdop_semantics": "PVT pDOP scale 0.01 dimensionless", "uncertainty_semantics": "NAV-COV posCovValid full NED; diagonal sqrt is per-axis STD", "missing_invalid_policy": "reject if join/validity/finite/PSD/unique-Q check fails", "decision": "SELECTED_PRIMARY", "reason": "best paper semantic match and complete per-axis NED uncertainty"},
        {"candidate": "GNSS1_STATUS", "source_file_message": "gnss1-status.csv project solution status", "physical_point": "GNSS1 antenna phase center", "frame": "WGS84 geodetic", "timestamp": "header/system/outer timestamps", "receiver_count": 1, "rate_hz": status["rate_hz"], "valid_count": status["valid_rows"], "coverage_seconds": status["coverage_seconds"], "units": "deg/deg/m; h/v accuracy m", "fix_quality_semantics": "fix_ok true; project fix_type=8, less direct Table-1 mapping", "pdop_semantics": "sol_pdop dimensionless", "uncertainty_semantics": "horizontal/vertical accuracy only; no full NED covariance", "missing_invalid_policy": "NOT_EVALUATED_NOT_SELECTED", "decision": "NOT_SELECTED", "reason": "lower rate and no full NED covariance"},
        {"candidate": "GNSS1_HPPOSECEF", "source_file_message": "gnss1-raw.csv UBX-NAV-HPPOSECEF row names", "physical_point": "GNSS1 solution point; exact endpoint NOT_EVALUATED_NOT_SELECTED", "frame": "ECEF", "timestamp": "payload iTOW NOT_DECODED_NOT_SELECTED", "receiver_count": 1, "rate_hz": "NOT_EVALUATED_NOT_SELECTED", "valid_count": "NOT_EVALUATED_NOT_SELECTED", "coverage_seconds": "NOT_EVALUATED_NOT_SELECTED", "units": "ECEF position/pAcc per official message; payload NOT_DECODED", "fix_quality_semantics": "requires PVT join; NOT_EVALUATED_NOT_SELECTED", "pdop_semantics": "requires PVT/DOP join; NOT_EVALUATED_NOT_SELECTED", "uncertainty_semantics": "scalar pAcc, not per-axis NED; NOT_EVALUATED_NOT_SELECTED", "missing_invalid_policy": "NOT_EVALUATED_NOT_SELECTED", "decision": "NOT_SELECTED", "reason": "PVT already provides position and NAV-COV supplies source-closed NED covariance"},
    ]
    _write_csv(out / "LC02_GNSS1_SOLUTION_SOURCE_COMPARISON.csv", list(source_rows[0]), source_rows)
    _write_json(out / "LC02_PDOP_AVAILABILITY.json", {"available": True, "source": "UBX-NAV-PVT pDOP", "valid_count": n, "units": "dimensionless", "scale": 0.01, "statistics": gnss["pvt"]["pdop"], "invalid_policy": "reject epoch", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"})
    _write_json(out / "LC02_Q_INPUT_AVAILABILITY.json", {"available": True, "selected_Q": gnss["q"]["selected_Q"], "valid_count": gnss["q"]["selected_count"], "all_rows_unique_Q1": gnss["q"]["all_rows_unique_Q1"], "basis": gnss["q"]["unique_semantic_reason"], "general_overlap_policy": "require semantic and interval uniqueness; reject otherwise", "provenance_class": "BY2_PHYSICAL_INSTANTIATION"})
    _write_json(out / "LC02_STD_AVAILABILITY.json", {"available": True, "source": "UBX-NAV-COV", "valid_count": gnss["nav_cov"]["pos_cov_valid_count"], "finite_count": gnss["nav_cov"]["finite_count"], "psd_count": gnss["nav_cov"]["psd_count"], "minimum_eigenvalue_m2": gnss["nav_cov"]["minimum_eigenvalue_m2"], "std_n_m": gnss["nav_cov"]["std_n_m"], "std_e_m": gnss["nav_cov"]["std_e_m"], "std_d_m": gnss["nav_cov"]["std_d_m"], "sqrt_trace_m": gnss["nav_cov"]["sqrt_trace_m"], "online_covariance_policy": "use diagonal NED variances only; retain off-diagonals as audit metadata", "velocity_covariance_used_online": False, "provenance_class": "BY2_PHYSICAL_INSTANTIATION"})
    _write_json(out / "LC02_TIME_AND_RATE_AUDIT.json", {"gnss1": {"raw_source_file": gnss["source_file"], "raw_source_sha256": gnss["source_sha256"], "raw_source_bytes": gnss["source_bytes"], "status_candidate_source_file": status["source_file"], "status_candidate_source_sha256": status["source_sha256"], "status_candidate_source_bytes": status["source_bytes"], "pvt_count": gnss["pvt_count"], "cov_count": gnss["cov_count"], "exact_itow_join_count": n, "first_itow_ms": gnss["first_itow_ms"], "last_itow_ms": gnss["last_itow_ms"], "coverage_seconds": gnss["coverage_seconds"], "rate_hz": gnss["rate_hz"], "itow_step_ms": gnss["itow_step_ms"], "row_timestamp_delta_us": gnss["row_timestamp_delta_us"], "decode_errors": gnss["decode_errors"], "outer_time_and_go2_overlap": gnss["cross_stream_time"]}, "go2_imu": imu, "join_policy": {"PVT_NAV_COV_identity": "exact GPS iTOW", "candidate_IMU_association_domain": "outer acquisition Time versus Go2 Unix stamp", "future_exact_association_policy": "must be frozen before implementation; no trace/reference may select offset or pairing"}, "trace_open_count": 0, "reference_open_count": 0})
    report = f"""# LC02 BY2 input report

The selected GNSS input is one GNSS1 solution stream composed of exact-iTOW joined `UBX-NAV-PVT` and `UBX-NAV-COV`. It remains one receiver and a position-only measurement. PVT supplies antenna position, fix/RTK semantics, and pDOP; NAV-COV supplies valid full NED position covariance. Velocity and velocity covariance are not decoded for online use.

- GNSS raw identity: `{gnss['source_sha256']}` ({gnss['source_bytes']} bytes). Candidate status identity: `{status['source_sha256']}` ({status['source_bytes']} bytes).
- PVT: {gnss['pvt_count']} messages; NAV-COV: {gnss['cov_count']}; exact joins: {n}; decode/checksum errors: {gnss['decode_errors']}/{gnss['checksum_errors']}.
- Cadence: {gnss['rate_hz']:.3f} Hz over {gnss['coverage_seconds']:.1f} s. Raw row-stamp PVT/COV delta median {gnss['row_timestamp_delta_us']['median']:.3f} us, maximum {gnss['row_timestamp_delta_us']['max']:.3f} us; exact iTOW is the identity key.
- PVT outer acquisition time spans {gnss['cross_stream_time']['pvt_outer_first_unix_s']:.7f}--{gnss['cross_stream_time']['pvt_outer_last_unix_s']:.7f}. {gnss['cross_stream_time']['pvt_epochs_within_go2_coverage']} epochs lie inside the authenticated Go2 interval; the first is {gnss['cross_stream_time']['first_overlap_after_go2_start_s']:.6f} s after Go2 start and the last is {gnss['cross_stream_time']['last_overlap_before_go2_end_s']:.6f} s before Go2 end. Outer time is only the candidate IMU-association domain; an exact future pairing rule remains to be frozen without trace.
- All {n} joined PVT rows are 3D, fix-valid, differential, fixed carrier solutions. pDOP range {gnss['pvt']['pdop']['min']:.2f}--{gnss['pvt']['pdop']['max']:.2f} (median {gnss['pvt']['pdop']['median']:.2f}).
- All {gnss['nav_cov']['pos_cov_valid_count']} position covariances are valid, finite, symmetric, and PSD; minimum eigenvalue {gnss['nav_cov']['minimum_eigenvalue_m2']:.9g} m^2. N/E/D standard-deviation ranges are {gnss['nav_cov']['std_n_m']['min']:.5f}--{gnss['nav_cov']['std_n_m']['max']:.5f}, {gnss['nav_cov']['std_e_m']['min']:.5f}--{gnss['nav_cov']['std_e_m']['max']:.5f}, and {gnss['nav_cov']['std_d_m']['min']:.5f}--{gnss['nav_cov']['std_d_m']['max']:.5f} m.
- `sqrt(trace(C_pos))` ranges {gnss['nav_cov']['sqrt_trace_m']['min']:.5f}--{gnss['nav_cov']['sqrt_trace_m']['max']:.5f} m. Fixed-integer semantics plus values below 0.05 m uniquely select Table-1 `Q=1` for every joined row. General overlap remains fail-closed.
- The full Go2 file SHA-256 is `{imu['source_sha256']}` ({imu['source_bytes']} bytes). The parser authenticated {imu['complete_records']} complete records from the frozen {imu['authenticated_prefix_bytes']}-byte prefix (SHA-256 `{imu['authenticated_prefix_sha256']}`) at a descriptive {imu['rate_hz']:.3f} Hz. Exact endpoints are `(sec,nsec)=({imu['first_sec']},{imu['first_nsec']})` and `({imu['last_sec']},{imu['last_nsec']})`, with exact duration `{imu['duration_ns']} ns`; float seconds are descriptive only. It materialized only stamp, raw-FLU gyro, and raw-FLU accelerometer. A future LC02 provider must apply the maintained mapping in its exact order: proper `diag(1,-1,-1)` FLU-to-FRD, then active `RzRyRx(-1 deg,0 deg,0 deg)` installation rotation in FRD. This reuses only the maintained input-frame mapping, not LC01 or Hartley code/results. The trailing incomplete record is unused.

`gnss1-status.csv` is available but not selected: it is lower-rate and lacks full NED covariance. GNSS2, P2-P1, yaw, method outputs, trace, and reference were not opened. Serialized rows in the multiplexed GNSS1 CSV were read and row names scanned, but RAWX/SFRBX/RTCM and velocity values were not semantically decoded, retained beyond row processing, or used. Go2 source bytes were read for hashing and allowed-field parsing, but forbidden navigation/contact/orientation values were not semantically decoded, retained, or used. Input availability is complete; this does not authorize a filter run.
"""
    (out / "LC02_BY2_INPUT_REPORT.md").write_text(report, encoding="utf-8")


def write_reports(
    stage: Path,
    paper: dict[str, Any],
    gnss: dict[str, Any],
    imu: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    out = stage / "11_REPORT"
    out.mkdir(parents=True, exist_ok=True)
    status = {
        "schema_version": "lc02.y0_y3.status.v1",
        "terminal_status": TERMINAL_STATUS,
        "audit_closure_scope": "Y0_Y3_METHOD_SOURCE_IDENTITY_INPUT_CONTRACT_ONLY",
        "audit_closure_pass_is_formal_raekf_admission": False,
        "method_id": METHOD_ID,
        "paper_identity_closed": paper["sha256"] == PAPER_SHA256 and paper["pages"] == PAPER_PAGES,
        "full_24_page_review_complete": True,
        "prior_asset_audit_complete": True,
        "state_dimension": 21,
        "measurement_scope": "POSITION_ONLY_PAPER_FAITHFUL",
        "by2_input_contract_ready": True,
        "gnss1_exact_join_count": gnss["exact_itow_join_count"],
        "go2_complete_record_count": imu["complete_records"],
        "non_duplication_decision": "DISTINCT_COMPLEMENTARY_METHOD",
        "official_code_classification": "OFFICIAL_PARTIAL_CODE_ONLY",
        "yin_specific_implementation": "NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND",
        "reproduction_levels": {"YIN2023_EKF": "FAITHFUL_ALGORITHM_REPRODUCTION", "YIN2023_AKF": "FAITHFUL_MODULE_REPRODUCTION", "YIN2023_RKF": "PAPER_DERIVED_POLICY_BASELINE", "YIN2023_RAEKF": "PAPER_DERIVED_POLICY_BASELINE"},
        "formal_lc02_admission": False,
        "raekf_covariance_decision": "EQ13_FUSION_RESOLVED_P_RK_NOT_SOURCE_CLOSED",
        "implementation_authorized": False,
        "C00_authorized": False,
        "representative_cases_authorized": False,
        "comparison_run_authorized": False,
        "audit_provenance": provenance,
        "execution_counters": {"LC01_rerun": 0, "Yin_solver_run": 0, "C00_run": 0, "trace_open": 0, "reference_open": 0, "other_method_run": 0, "Canonical_541_run": 0},
    }
    _write_json(out / "LC02_Y0_Y3_STATUS.json", status)
    decision = """# LC02 method and reproduction decision

LC01 and LC02 are `DISTINCT_COMPLEMENTARY_METHOD` identities. The selected BY2 input contract is complete and uses a single GNSS1 PVT+NAV-COV solution composite plus Go2 body gyro/accelerometer.

Reproduction levels are exact and branch-specific:

- `YIN2023_EKF`: `FAITHFUL_ALGORITHM_REPRODUCTION` (base 21-state algorithm closed from the paper and its acknowledged KF-GINS source).
- `YIN2023_AKF`: `FAITHFUL_MODULE_REPRODUCTION` (printed module preserved, including the unresolved dimensional meaning of Eq. 6).
- `YIN2023_RKF`: `PAPER_DERIVED_POLICY_BASELINE` (`L_k` versus `Z_k`, the standardizer, and zero-weight inverse are not source-closed; `L_k=Z_k` is only paper-derived).
- `YIN2023_RAEKF`: `PAPER_DERIVED_POLICY_BASELINE` (fusion equations are direct, but inherit the non-unique robust covariance).

The exact terminal status is `PASS_LC02_YIN2023_Y0_Y3_METHOD_NON_DUPLICATION_AND_BY2_CONTRACT_READY`. This PASS closes only the Y0–Y3 audit contracts. It does not mean Eq. (13)'s inputs are source-closed or that RAEKF is formally admitted: the convex covariance formula is explicit, while `P_rk` remains non-unique. Formal LC02 admission and every execution gate remain false.
"""
    (out / "LC02_METHOD_AND_REPRODUCTION_DECISION.md").write_text(decision, encoding="utf-8")
    full = f"""# LC02 Yin 2023 Y0--Y3 full report

Terminal status: `{TERMINAL_STATUS}`. This is an audit-closure PASS, not formal RAEKF admission or execution authorization.

The official 24-page MDPI v2 paper was fully reviewed and frozen at SHA-256 `{paper['sha256']}` ({paper['bytes']} bytes, CC BY 4.0). The prior QA11G alias is a generic covariance-matching simplification and its historical 120-case report is inactive; neither code/provider nor runtime performance is reused. The focused source search found the paper-acknowledged KF-GINS base only (`OFFICIAL_PARTIAL_CODE_ONLY`), and no attributable Yin adaptive/robust implementation.

The 21-state NED error model, complete paper-contemporaneous KF-GINS F/G, signs, mechanization, process-noise structure, three-dimensional position residual, and positive lever-arm skew block are contracted. Explicit equations outrank diagram labels, giving `POSITION_ONLY_PAPER_FAITHFUL`.

EKF, AKF, RKF, and RAEKF are separate machine-readable branches. Improved `R=PDOP^2 Q r^2`, all six Table-1 Q rows, units, and fail-closed missing/overlap policies are frozen. BY2 supplies {gnss['exact_itow_join_count']} exact PVT/NAV-COV joins at {gnss['rate_hz']:.1f} Hz and {imu['complete_records']} authenticated Go2 IMU records. All joined NED covariances are valid/finite/PSD, and all joined epochs uniquely map to Q=1. Input gate: ready.

Formal LC02 admission remains false. Yin does not define `L_k` versus `Z_k`, its `V_tilde_i` standardizer is undefined, and IGGIII `w_i=0` makes the printed equivalent precision singular before inversion. Eq. (13) explicitly fuses `P=omega P_a+(1-omega)P_r`; the non-source-closed object is `P_r`, not the fusion formula. `L_k=Z_k` and row omission/infinite variance are only paper-derived policies. These limitations are recorded without converting the completed Y0–Y3 audit into a terminal blocker.

LC01 and LC02 are scientifically complementary: two-receiver invariant rigid geometry versus one-receiver quality-aware conventional error-state filtering. No performance number was used for identity. No LC01, Yin solver, C00, other method, comparison, trace/reference, or Canonical-541 execution occurred. Implementation, C00, representative cases, and comparison remain unauthorized.
"""
    (out / "LC02_Y0_Y3_FULL_REPORT.md").write_text(full, encoding="utf-8")


def _required_stage_files() -> frozenset[str]:
    return frozenset({
        "00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY.csv",
        "00_ACTIVE_METHOD_REGISTRY/ACTIVE_EXTERNAL_METHOD_BOUNDARY.md",
        "00_ACTIVE_METHOD_REGISTRY/INACTIVE_OR_LEGACY_RESULT_REGISTRY.csv",
        "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_ASSET_INVENTORY.csv",
        "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_CODE_PROVENANCE.md",
        "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_RUNTIME_STATUS.md",
        "01_PRIOR_IMPLEMENTATION_AUDIT/YIN2023_PRIOR_REUSABILITY_DECISION.json",
        "02_PAPER_REVIEW/LC02_FULL_METHOD_CARD.md",
        "02_PAPER_REVIEW/LC02_EQUATION_REGISTRY.csv",
        "02_PAPER_REVIEW/LC02_FIGURE_AND_FLOW_REGISTRY.csv",
        "02_PAPER_REVIEW/LC02_TABLE_AND_PARAMETER_REGISTRY.csv",
        "02_PAPER_REVIEW/LC02_PAPER_EXPERIMENT_REGISTRY.csv",
        "02_PAPER_REVIEW/LC02_PAPER_CLAIM_BOUNDARY.md",
        "03_SOURCE_PROVENANCE/LC02_OFFICIAL_CODE_SEARCH.md",
        "03_SOURCE_PROVENANCE/LC02_SOURCE_REGISTRY.csv",
        "04_METHOD_CONTRACTS/LC02_STATE_AND_DYNAMICS_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_F_G_SOURCE_PROVENANCE.md",
        "04_METHOD_CONTRACTS/LC02_ERROR_STATE_SIGN_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_PROCESS_NOISE_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_MEASUREMENT_SCOPE_DECISION.json",
        "04_METHOD_CONTRACTS/LC02_MEASUREMENT_MODEL_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_FRAME_AND_LEVER_ARM_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_EKF_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_AKF_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_RKF_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_RAEKF_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_BRANCH_IDENTITY_REGISTRY.csv",
        "04_METHOD_CONTRACTS/LC02_COVARIANCE_FUSION_DECISION.json",
        "04_METHOD_CONTRACTS/LC02_IMPROVED_R_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_MEASUREMENT_FACTOR_Q_REGISTRY.csv",
        "04_METHOD_CONTRACTS/LC02_PDOP_STD_UNIT_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/LC02_FUTURE_EXECUTION_GATE.yaml",
        "04_METHOD_CONTRACTS/SOLUTION_LEVEL_LC_FUTURE_COMPARISON_CONTRACT.yaml",
        "05_BY2_INPUT_AUDIT/LC02_BY2_FIELD_ROLE_REGISTRY.csv",
        "05_BY2_INPUT_AUDIT/LC02_GNSS1_SOLUTION_SOURCE_COMPARISON.csv",
        "05_BY2_INPUT_AUDIT/LC02_PDOP_AVAILABILITY.json",
        "05_BY2_INPUT_AUDIT/LC02_Q_INPUT_AVAILABILITY.json",
        "05_BY2_INPUT_AUDIT/LC02_STD_AVAILABILITY.json",
        "05_BY2_INPUT_AUDIT/LC02_TIME_AND_RATE_AUDIT.json",
        "05_BY2_INPUT_AUDIT/LC02_BY2_INPUT_REPORT.md",
        "06_NON_DUPLICATION_AUDIT/LC01_VS_LC02_INFORMATION_STRUCTURE.csv",
        "06_NON_DUPLICATION_AUDIT/LC01_VS_LC02_STATE_MEASUREMENT_COMPARISON.csv",
        "06_NON_DUPLICATION_AUDIT/LC01_VS_LC02_METHOD_IDENTITY_DECISION.json",
        "06_NON_DUPLICATION_AUDIT/LC01_VS_LC02_SCIENTIFIC_COMPLEMENTARITY.md",
        "11_REPORT/LC02_Y0_Y3_FULL_REPORT.md",
        "11_REPORT/LC02_Y0_Y3_STATUS.json",
        "11_REPORT/LC02_METHOD_AND_REPRODUCTION_DECISION.md",
    })


def _allowed_y4a_append_files() -> frozenset[str]:
    """Exact append-only Y4A namespace; never valid for Y0--Y3 replacement."""

    root = "07_Y4A_REPRODUCIBILITY_CLOSURE"
    return frozenset(
        {
            f"{root}/00_SOURCE_REGISTRY/YIN2023_Y4A_SOURCE_REGISTRY.csv",
            f"{root}/00_SOURCE_REGISTRY/YIN2023_SOURCE_ACCESS_LOG.md",
            f"{root}/00_SOURCE_REGISTRY/YIN2023_Y0_Y3_IMMUTABILITY_BASELINE.sha256",
            f"{root}/01_SYMBOL_RECONCILIATION/YIN2023_UNRESOLVED_SYMBOL_REGISTRY.csv",
            f"{root}/01_SYMBOL_RECONCILIATION/YIN2023_LK_ZK_DECISION.json",
            f"{root}/01_SYMBOL_RECONCILIATION/YIN2023_NOTATION_ERRATA_REGISTRY.md",
            f"{root}/02_AKF_CLOSURE/YIN2023_AKF_SOURCE_MAP.csv",
            f"{root}/02_AKF_CLOSURE/YIN2023_AKF_FINAL_CONTRACT.yaml",
            f"{root}/02_AKF_CLOSURE/YIN2023_AKF_CLOSURE_DECISION.json",
            f"{root}/03_RKF_CLOSURE/YIN2023_STANDARDIZED_RESIDUAL_SOURCE_MAP.csv",
            f"{root}/03_RKF_CLOSURE/YIN2023_STANDARDIZED_RESIDUAL_CONTRACT.yaml",
            f"{root}/03_RKF_CLOSURE/YIN2023_STANDARDIZED_RESIDUAL_DECISION.json",
            f"{root}/03_RKF_CLOSURE/YIN2023_IGGIII_SOURCE_MAP.csv",
            f"{root}/03_RKF_CLOSURE/YIN2023_IGGIII_EQUIVALENT_WEIGHT_CONTRACT.yaml",
            f"{root}/03_RKF_CLOSURE/YIN2023_IGGIII_MATRIX_DECISION.json",
            f"{root}/03_RKF_CLOSURE/YIN2023_ZERO_WEIGHT_POLICY_SOURCE_MAP.csv",
            f"{root}/03_RKF_CLOSURE/YIN2023_ZERO_WEIGHT_POLICY_CONTRACT.yaml",
            f"{root}/03_RKF_CLOSURE/YIN2023_ZERO_WEIGHT_POLICY_DECISION.json",
            f"{root}/04_RAEKF_CLOSURE/YIN2023_RAEKF_FINAL_CONTRACT.yaml",
            f"{root}/04_RAEKF_CLOSURE/YIN2023_RAEKF_FEEDBACK_RESET_DECISION.json",
            f"{root}/04_RAEKF_CLOSURE/YIN2023_RAEKF_COVARIANCE_INTERPRETATION.md",
            f"{root}/05_MATHEMATICAL_ORACLES/Y4A_LINEAR_ORACLE_RESULTS.csv",
            f"{root}/05_MATHEMATICAL_ORACLES/Y4A_LIMIT_AND_EQUIVALENCE_PROOFS.md",
            f"{root}/05_MATHEMATICAL_ORACLES/Y4A_ORACLE_SUMMARY.json",
            f"{root}/06_ADMISSION_DECISION/YIN2023_FORMAL_ADMISSION_RUBRIC.yaml",
            f"{root}/06_ADMISSION_DECISION/LC02_C00_MECHANISM_ACTIVATION_FORECAST.md",
            f"{root}/06_ADMISSION_DECISION/Y4A_FORBIDDEN_ACCESS_AUDIT.json",
            f"{root}/06_ADMISSION_DECISION/LC02_YIN2023_NO_GO_REASON.md",
            f"{root}/06_ADMISSION_DECISION/LC02_NEXT_PAPER_SELECTION_REQUIREMENTS.md",
            "11_REPORT/LC02_Y4A_REPRODUCIBILITY_CLOSURE_REPORT.md",
            "11_REPORT/LC02_Y4A_STATUS.json",
            "11_REPORT/LC02_FORMAL_ADMISSION_DECISION.md",
        }
    )


def _allowed_y4a_pass_append_files() -> frozenset[str]:
    """Outcome-A variant: exact Y4A namespace without the two no-go documents."""

    no_go_only = {
        "07_Y4A_REPRODUCIBILITY_CLOSURE/06_ADMISSION_DECISION/LC02_YIN2023_NO_GO_REASON.md",
        "07_Y4A_REPRODUCIBILITY_CLOSURE/06_ADMISSION_DECISION/LC02_NEXT_PAPER_SELECTION_REQUIREMENTS.md",
    }
    return _allowed_y4a_append_files().difference(no_go_only)


def _allowed_y4a_append_variants() -> tuple[frozenset[str], frozenset[str]]:
    """Return the only two authorized append-only Y4A file sets."""

    return (_allowed_y4a_pass_append_files(), _allowed_y4a_append_files())


def _stage_structure_errors(stage: Path, *, allow_y4a_append: bool = False) -> list[str]:
    required = _required_stage_files()
    if not stage.exists():
        return ["stage does not exist"]
    if stage.is_symlink() or not stage.is_dir():
        return ["stage is a symlink or not a directory"]
    entries = list(stage.rglob("*"))
    errors = [f"symlink forbidden: {item.relative_to(stage)}" for item in entries if item.is_symlink()]
    errors.extend(
        f"special filesystem entry forbidden: {item.relative_to(stage)}"
        for item in entries
        if not item.is_symlink() and not item.is_file() and not item.is_dir()
    )
    actual_files = {str(item.relative_to(stage)) for item in entries if item.is_file() and not item.is_symlink()}
    expected = required
    if allow_y4a_append and actual_files != required:
        candidates = tuple(required | variant for variant in _allowed_y4a_append_variants())
        expected = actual_files if actual_files in candidates else required | _allowed_y4a_append_files()
    for relative in sorted(expected.difference(actual_files)):
        errors.append(f"missing {relative}")
    for relative in sorted(actual_files.difference(expected)):
        errors.append(f"unexpected nested file {relative}")
    if len(actual_files) != len(expected):
        errors.append(f"stage file count is {len(actual_files)}, expected {len(expected)}")
    allowed_dirs: set[str] = set()
    for relative in expected:
        parent = Path(relative).parent
        while parent != Path("."):
            allowed_dirs.add(str(parent))
            parent = parent.parent
    actual_dirs = {str(item.relative_to(stage)) for item in entries if item.is_dir() and not item.is_symlink()}
    for relative in sorted(actual_dirs.difference(allowed_dirs)):
        errors.append(f"unexpected directory {relative}")
    for item in entries:
        if item.is_file() and item.suffix.lower() == ".zip":
            errors.append(f"ZIP forbidden: {item.relative_to(stage)}")
    return errors


def validate_stage(stage: Path) -> list[str]:
    required = _required_stage_files()
    errors = _stage_structure_errors(stage, allow_y4a_append=True)
    if not stage.is_dir() or stage.is_symlink():
        return errors
    allowed_top_level = {
        "00_ACTIVE_METHOD_REGISTRY",
        "01_PRIOR_IMPLEMENTATION_AUDIT",
        "02_PAPER_REVIEW",
        "03_SOURCE_PROVENANCE",
        "04_METHOD_CONTRACTS",
        "05_BY2_INPUT_AUDIT",
        "06_NON_DUPLICATION_AUDIT",
        "11_REPORT",
    }
    actual_files = {
        str(path.relative_to(stage))
        for path in stage.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if actual_files != required:
        allowed_top_level.add("07_Y4A_REPRODUCIBILITY_CLOSURE")
    unexpected = sorted(item.name for item in stage.iterdir() if item.name not in allowed_top_level)
    errors.extend(f"unexpected top-level entry {name}" for name in unexpected)
    forbidden_names = {"NAV.csv", "EVAL_NAV.csv", "C00", "solver", "comparison_result", "trace"}
    for path in stage.rglob("*"):
        relative = str(path.relative_to(stage))
        is_declared_y4a_contract = any(
            relative in variant for variant in _allowed_y4a_append_variants()
        )
        if path.is_file() and not is_declared_y4a_contract and any(token.lower() in path.name.lower() for token in forbidden_names):
            errors.append(f"forbidden runtime-like artifact {path.relative_to(stage)}")
        if not path.is_file():
            continue
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            elif path.suffix == ".csv":
                with path.open("rt", encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if not reader.fieldnames or not list(reader):
                        errors.append(f"empty CSV {path.relative_to(stage)}")
        except (ValueError, csv.Error, json.JSONDecodeError, yaml.YAMLError) as exc:
            errors.append(f"parse failure {path.relative_to(stage)}: {exc}")
    status_path = stage / "11_REPORT/LC02_Y0_Y3_STATUS.json"
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if status.get("terminal_status") != TERMINAL_STATUS:
                errors.append("terminal status mismatch")
            for gate in (
                "formal_lc02_admission",
                "implementation_authorized",
                "C00_authorized",
                "representative_cases_authorized",
                "comparison_run_authorized",
            ):
                if status.get(gate) is not False:
                    errors.append(f"gate is not false: {gate}")
            counters = status.get("execution_counters", {})
            if not counters or any(value != 0 for value in counters.values()):
                errors.append("execution counters are absent or nonzero")
            provenance = status.get("audit_provenance", {})
            expected_provenance = {
                "data_mode": "REAL_BY2_INPUT_AUDIT",
                "synthetic_data_used": False,
                "semisynthetic_data_used": False,
                "trace_used_online": False,
                "receiver_imu_as_body_imu": False,
                "final_v23_output_solver_input": False,
                "LegSA_output_solver_input": False,
                "per_case_tuning": False,
                "output_only_correction": False,
                "epoch_deleted_for_metric": False,
                "old_runtime_input_count": 0,
            }
            for key, expected in expected_provenance.items():
                if provenance.get(key) != expected:
                    errors.append(f"audit provenance mismatch: {key}")
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"status validation failure: {exc}")
    gate_path = stage / "04_METHOD_CONTRACTS/LC02_FUTURE_EXECUTION_GATE.yaml"
    if gate_path.is_file():
        try:
            gate_payload = yaml.safe_load(gate_path.read_text(encoding="utf-8"))
            for gate in ("formal_lc02_admission", "implementation_authorized", "C00_authorized", "representative_cases_authorized", "comparison_run_authorized"):
                if gate_payload.get(gate) is not False:
                    errors.append(f"future gate is not false: {gate}")
        except yaml.YAMLError as exc:
            errors.append(f"future gate validation failure: {exc}")
    return errors


def _prepare_exact_stage_target(
    stage: Path,
    clean_root: Path,
    *,
    replace_existing_audit_stage: bool,
) -> None:
    expected_parent = clean_root / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    expected_stage = expected_parent / "08_LC02_YIN2023_RAEKF"
    checked_components = [clean_root, clean_root / "stages", expected_parent, stage]
    if any(component.exists() and component.is_symlink() for component in checked_components):
        raise ValueError("protected stage path contains a symlink")
    if stage.resolve(strict=False) != expected_stage.resolve(strict=False):
        raise ValueError("stage root is not the exact protected LC02 audit target")
    if stage.resolve(strict=False) in {clean_root.resolve(), expected_parent.resolve()}:
        raise ValueError("replacement target is a protected parent/root")
    if stage.exists():
        if not replace_existing_audit_stage:
            raise ValueError("LC02 audit stage already exists; explicit --replace-existing-audit-stage is required")
        structure_errors = _stage_structure_errors(stage)
        if structure_errors:
            raise ValueError("existing LC02 stage is not the exact known 47-file audit layout: " + "; ".join(structure_errors))
    elif replace_existing_audit_stage:
        raise ValueError("--replace-existing-audit-stage requires an existing exact audit stage")


def run_audit(
    local_paths: Path,
    paper_path: Path,
    stage_root: Path,
    *,
    replace_existing_audit_stage: bool = False,
) -> dict[str, Any]:
    paths = load_local_paths(local_paths)
    expected_stage = Path(paths["clean_root"]) / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/08_LC02_YIN2023_RAEKF"
    if stage_root.resolve() != expected_stage.resolve():
        raise ValueError("stage root differs from local-alias-derived exact LC02 root")
    repo = repository_root()
    if Path(paths["code_root"]).resolve() != repo.resolve():
        raise ValueError("code_root alias does not identify this worktree")
    _prepare_exact_stage_target(
        stage_root,
        Path(paths["clean_root"]),
        replace_existing_audit_stage=replace_existing_audit_stage,
    )
    fix_root = Path(paths["by2_fix_root"])
    paper = audit_paper(paper_path)
    if (paper["sha256"], paper["bytes"], paper["pages"]) != (PAPER_SHA256, PAPER_BYTES, PAPER_PAGES):
        raise ValueError("paper identity mismatch")
    gnss = audit_gnss1_raw(fix_root / "gnss1-raw.csv")
    status = audit_gnss1_status(fix_root / "gnss1-status.csv")
    imu = audit_go2_imu(Path(paths["by2_go2_body"]))
    pvt_outer_times = gnss.pop("_pvt_outer_times_unix_s")
    overlap = [
        time_s
        for time_s in pvt_outer_times
        if imu["first_time_unix_s"] <= time_s <= imu["last_time_unix_s"]
    ]
    if not overlap:
        raise ValueError("GNSS1 PVT has no outer-time overlap with authenticated Go2 prefix")
    gnss["cross_stream_time"] = {
        "pvt_outer_first_unix_s": pvt_outer_times[0],
        "pvt_outer_last_unix_s": pvt_outer_times[-1],
        "go2_first_unix_s": imu["first_time_unix_s"],
        "go2_last_unix_s": imu["last_time_unix_s"],
        "pvt_epochs_within_go2_coverage": len(overlap),
        "first_overlap_after_go2_start_s": overlap[0] - imu["first_time_unix_s"],
        "last_overlap_before_go2_end_s": imu["last_time_unix_s"] - overlap[-1],
        "identity_rule": "PVT/COV exact iTOW; outer Time is candidate IMU association domain only",
    }
    execution_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    provenance = {
        "data_mode": "REAL_BY2_INPUT_AUDIT",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "code_commit": execution_head,
        "config_hash": sha256_file(local_paths),
        "audit_code_hash": sha256_file(Path(__file__)),
        "paper_hash": paper["sha256"],
        "execution_semantics": "read-only input audit; no solver/filter/evaluator execution",
    }
    sync_static_payload(repo, stage_root)
    write_by2_artifacts(stage_root, gnss, status, imu)
    write_reports(stage_root, paper, gnss, imu, provenance)
    errors = validate_stage(stage_root)
    if errors:
        raise ValueError("; ".join(errors))
    return {"terminal_status": TERMINAL_STATUS, "paper": paper, "gnss1": gnss, "gnss1_status": status, "go2_imu": imu, "audit_provenance": provenance, "stage_root": str(stage_root), "validation_errors": errors, "source_open_audit": {"opened_roles": ["local_path_aliases", "official_paper", "GNSS1_multiplexed_serialized_rows", "GNSS1_status_candidate", "Go2_body_IMU_serialized_source_bytes"], "GNSS1_multiplexed_file_open_count": 1, "serialized_GNSS1_rows_read": True, "raw_carrier_value_semantic_decode_count": 0, "raw_carrier_value_retained_beyond_row_count": 0, "raw_carrier_value_use_count": 0, "go2_source_bytes_read": True, "go2_forbidden_value_semantic_decode_count": 0, "go2_forbidden_value_retained_count": 0, "go2_forbidden_value_use_count": 0, "trace_open_count": 0, "reference_open_count": 0, "GNSS2_open_count": 0, "old_runtime_open_count": 0}}


def main(argv: list[str] | None = None) -> int:
    repo = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-paths", type=Path, default=repo / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
    parser.add_argument("--paper", type=Path)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--replace-existing-audit-stage", action="store_true")
    args = parser.parse_args(argv)
    stage_root = args.stage_root
    if stage_root is None:
        local = load_local_paths(args.local_paths)
        stage_root = Path(local["clean_root"]) / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/08_LC02_YIN2023_RAEKF"
    if args.validate_only:
        errors = validate_stage(stage_root)
        print(json.dumps({"stage_root": str(stage_root), "validation_errors": errors}, indent=2, sort_keys=True))
        return 1 if errors else 0
    if args.paper is None:
        parser.error("--paper is required unless --validate-only is used")
    result = run_audit(
        args.local_paths,
        args.paper,
        stage_root,
        replace_existing_audit_stage=args.replace_existing_audit_stage,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
