"""Official .pos parsing, deterministic regression, and native normalization."""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .constants import (
    INS_ONLY_STATUS,
    LC_UPDATE_STATUS,
    OFFICIAL_POS_COLUMNS,
    OFFICIAL_STATUS_NAMES,
    POOR_APPLICABILITY_STATUS,
    STANDARD_NAV_COLUMNS,
    SUCCESS_STATUS,
)
from .source import sha256_file


class OutputContractError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class OfficialSolutionRow:
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values) != len(OFFICIAL_POS_COLUMNS):
            raise OutputContractError("official solution row is not 33 fields")

    def __getitem__(self, key: str) -> float:
        try:
            return self.values[OFFICIAL_POS_COLUMNS.index(key)]
        except ValueError as exc:
            raise KeyError(key) from exc

    @property
    def status(self) -> int:
        value = self["status"]
        if value != int(value):
            raise OutputContractError("official status is not integral")
        return int(value)

    @property
    def satellite_count(self) -> int:
        value = self["satellite_count"]
        if value != int(value):
            raise OutputContractError("official satellite count is not integral")
        return int(value)

    @property
    def state_finite(self) -> bool:
        indexes = list(range(2, 5)) + list(range(15, 18)) + list(range(24, 27))
        return all(math.isfinite(self.values[index]) for index in indexes)

    @property
    def covariance_finite(self) -> bool:
        indexes = list(range(7, 13)) + list(range(18, 24)) + list(range(27, 33))
        return all(math.isfinite(self.values[index]) for index in indexes)


def read_official_solution(path: str | Path) -> tuple[OfficialSolutionRow, ...]:
    rows: list[OfficialSolutionRow] = []
    with Path(path).open("r", encoding="utf-8", errors="strict") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("%"):
                continue
            fields = line.split()
            if len(fields) != len(OFFICIAL_POS_COLUMNS):
                raise OutputContractError(
                    f"official solution line {line_number} has {len(fields)} fields"
                )
            try:
                values = tuple(float(item) for item in fields)
            except ValueError as exc:
                raise OutputContractError(
                    f"official solution line {line_number} is nonnumeric"
                ) from exc
            row = OfficialSolutionRow(values)
            if row.status not in OFFICIAL_STATUS_NAMES:
                raise OutputContractError(f"unknown official status {row.status}")
            rows.append(row)
    if not rows:
        raise OutputContractError("official solution contains no data rows")
    return tuple(rows)


def status_run_length(rows: Sequence[OfficialSolutionRow]) -> tuple[dict[str, int], ...]:
    runs: list[dict[str, int]] = []
    for row in rows:
        status = row.status
        if runs and runs[-1]["status"] == status:
            runs[-1]["count"] += 1
        else:
            runs.append({"status": status, "count": 1})
    return tuple(runs)


def scientific_digest(rows: Sequence[OfficialSolutionRow]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        for index, value in enumerate(row.values):
            if index in (0, 5, 6):
                token = str(int(value))
            else:
                token = float(value).hex()
            digest.update(token.encode("ascii"))
            digest.update(b"\0")
        digest.update(b"\n")
    return digest.hexdigest()


def summarize_solution(rows: Sequence[OfficialSolutionRow]) -> dict[str, Any]:
    status_counts = Counter(row.status for row in rows)
    finite_state = sum(row.state_finite for row in rows)
    finite_covariance = sum(row.covariance_finite for row in rows)

    def ranges(names: Sequence[str]) -> dict[str, dict[str, float | None]]:
        output: dict[str, dict[str, float | None]] = {}
        for name in names:
            values = [row[name] for row in rows if math.isfinite(row[name])]
            output[name] = {
                "minimum": min(values) if values else None,
                "maximum": max(values) if values else None,
            }
        return output

    return {
        "row_count": len(rows),
        "alignment_week": int(rows[0]["gps_week"]),
        "alignment_sow": rows[0]["gps_sow"],
        "status_counts": {
            str(code): {
                "name": OFFICIAL_STATUS_NAMES[code], "count": status_counts.get(code, 0)
            }
            for code in sorted(OFFICIAL_STATUS_NAMES)
        },
        "status_sequence_run_length": list(status_run_length(rows)),
        "state_transition_count": max(0, len(status_run_length(rows)) - 1),
        "internal_spp_fed_lc_update_count": status_counts.get(LC_UPDATE_STATUS, 0),
        "alignment_output_count": int(rows[0].status == INS_ONLY_STATUS),
        "ins_only_propagation_count": max(
            0, status_counts.get(INS_ONLY_STATUS, 0) - int(rows[0].status == INS_ONLY_STATUS)
        ),
        "finite_state_count": finite_state,
        "finite_state_rate": finite_state / len(rows),
        "finite_covariance_count": finite_covariance,
        "finite_covariance_rate": finite_covariance / len(rows),
        "position_ranges": ranges(("ecef_x_m", "ecef_y_m", "ecef_z_m")),
        "velocity_ranges": ranges(("ecef_vx_mps", "ecef_vy_mps", "ecef_vz_mps")),
        "attitude_ranges": ranges(("pitch_deg", "roll_deg", "yaw_deg")),
        "scientific_digest_sha256": scientific_digest(rows),
    }


def compare_sample_runs(
    first_rows: Sequence[OfficialSolutionRow],
    second_rows: Sequence[OfficialSolutionRow],
) -> dict[str, Any]:
    first = summarize_solution(first_rows)
    second = summarize_solution(second_rows)
    checks = {
        "row_count_identical": first["row_count"] == second["row_count"],
        "status_counts_identical": first["status_counts"] == second["status_counts"],
        "status_sequence_identical": (
            first["status_sequence_run_length"] == second["status_sequence_run_length"]
        ),
        "state_transition_count_identical": (
            first["state_transition_count"] == second["state_transition_count"]
        ),
        "scientific_digest_identical": (
            first["scientific_digest_sha256"] == second["scientific_digest_sha256"]
        ),
        "all_position_velocity_attitude_covariance_finite": (
            first["finite_state_rate"] == 1.0
            and second["finite_state_rate"] == 1.0
            and first["finite_covariance_rate"] == 1.0
            and second["finite_covariance_rate"] == 1.0
        ),
    }
    return {
        "schema_version": "ginav2021.official_sample_determinism.v1",
        "official_reference_output_bundled": False,
        "official_reference_or_trajectory_opened": False,
        "first": first,
        "second": second,
        "checks": checks,
        "pass": all(checks.values()),
    }


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    # WGS84 closed independently of any reference trajectory.
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1.0 - e2))
    for _ in range(15):
        sin_lat = math.sin(lat)
        radius = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
        height = p / max(math.cos(lat), 1e-30) - radius
        updated = math.atan2(z, p * (1.0 - e2 * radius / (radius + height)))
        if abs(updated - lat) < 1e-14:
            lat = updated
            break
        lat = updated
    sin_lat = math.sin(lat)
    radius = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    height = p / math.cos(lat) - radius
    return math.degrees(lat), math.degrees(lon), height


def ecef_velocity_to_enu(
    latitude_deg: float, longitude_deg: float,
    velocity: Sequence[float],
) -> tuple[float, float, float]:
    lat = math.radians(latitude_deg)
    lon = math.radians(longitude_deg)
    vx, vy, vz = (float(value) for value in velocity)
    east = -math.sin(lon) * vx + math.cos(lon) * vy
    north = (
        -math.sin(lat) * math.cos(lon) * vx
        - math.sin(lat) * math.sin(lon) * vy
        + math.cos(lat) * vz
    )
    up = (
        math.cos(lat) * math.cos(lon) * vx
        + math.cos(lat) * math.sin(lon) * vy
        + math.sin(lat) * vz
    )
    return east, north, up


def standard_nav_row(row: OfficialSolutionRow) -> dict[str, Any]:
    lat, lon, height = ecef_to_geodetic(
        row["ecef_x_m"], row["ecef_y_m"], row["ecef_z_m"]
    )
    east, north, up = ecef_velocity_to_enu(
        lat, lon,
        (row["ecef_vx_mps"], row["ecef_vy_mps"], row["ecef_vz_mps"]),
    )
    status = row.status
    return {
        "gps_week": int(row["gps_week"]),
        "gps_sow": row["gps_sow"],
        "status_code": status,
        "status_name": OFFICIAL_STATUS_NAMES[status],
        "satellite_count": row.satellite_count,
        "ecef_x_m": row["ecef_x_m"], "ecef_y_m": row["ecef_y_m"],
        "ecef_z_m": row["ecef_z_m"], "latitude_deg": lat,
        "longitude_deg": lon, "height_m": height,
        "ecef_vx_mps": row["ecef_vx_mps"],
        "ecef_vy_mps": row["ecef_vy_mps"],
        "ecef_vz_mps": row["ecef_vz_mps"],
        "velocity_east_mps": east, "velocity_north_mps": north,
        "velocity_up_mps": up, "velocity_north_ned_mps": north,
        "velocity_east_ned_mps": east, "velocity_down_ned_mps": -up,
        "pitch_deg": row["pitch_deg"], "roll_deg": row["roll_deg"],
        "yaw_deg": row["yaw_deg"],
        "position_covariance_finite": all(math.isfinite(row.values[i]) for i in range(7, 13)),
        "velocity_covariance_finite": all(math.isfinite(row.values[i]) for i in range(18, 24)),
        "attitude_covariance_finite": all(math.isfinite(row.values[i]) for i in range(27, 33)),
        "lc_update": status == LC_UPDATE_STATUS,
        "ins_only": status == INS_ONLY_STATUS,
    }


def write_standard_nav(path: str | Path, rows: Sequence[OfficialSolutionRow]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_NAV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(standard_nav_row(row))
    return destination


def write_status_stream(path: str | Path, rows: Sequence[OfficialSolutionRow]) -> Path:
    destination = Path(path)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "row_index", "gps_week", "gps_sow", "status_code", "status_name",
                "satellite_count", "lc_update", "ins_only", "state_finite",
                "covariance_finite",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        for index, row in enumerate(rows):
            writer.writerow(
                {
                    "row_index": index, "gps_week": int(row["gps_week"]),
                    "gps_sow": row["gps_sow"], "status_code": row.status,
                    "status_name": OFFICIAL_STATUS_NAMES[row.status],
                    "satellite_count": row.satellite_count,
                    "lc_update": row.status == LC_UPDATE_STATUS,
                    "ins_only": row.status == INS_ONLY_STATUS,
                    "state_finite": row.state_finite,
                    "covariance_finite": row.covariance_finite,
                }
            )
    return destination


WARNING_RE = re.compile(r"^(Warning:|Error:|Exception:)(?P<message>.*)$", re.IGNORECASE)


def failure_ledger(stdout: str, stderr: str) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for stream_name, text in (("stdout", stdout), ("stderr", stderr)):
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = WARNING_RE.match(line.strip())
            if match:
                rows.append(
                    {
                        "sequence": len(rows) + 1,
                        "stream": stream_name,
                        "line_number": line_number,
                        "severity": match.group(1).rstrip(":").upper(),
                        "message": match.group("message").strip(),
                    }
                )
    return tuple(rows)


def formal_admission(summary: Mapping[str, Any], *, process_returncode: int) -> dict[str, Any]:
    if process_returncode != 0:
        raise OutputContractError(
            "formal admission requires a zero MATLAB process return code"
        )
    row_count = int(summary.get("row_count") or 0)
    finite_state_rate = float(summary.get("finite_state_rate") or 0.0)
    finite_covariance_rate = float(summary.get("finite_covariance_rate") or 0.0)
    q5_updates = int(summary.get("internal_spp_fed_lc_update_count") or 0)
    finite_lc_updates = int(summary.get("finite_lc_update_count") or 0)
    initialized = row_count > 0 and q5_updates > 0
    finite_lc_segment = initialized and finite_lc_updates > 0
    admitted = finite_lc_segment
    poor = initialized and (
        not finite_lc_segment
        or finite_state_rate < 1.0
        or finite_covariance_rate < 1.0
    )
    terminal = (
        POOR_APPLICABILITY_STATUS if poor else
        SUCCESS_STATUS if admitted else
        "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP"
    )
    return {
        "formal_lc02_slot": "FILLED" if admitted else "VACANT",
        "formal_lc02_admission": admitted,
        "BY2_C00_complete": initialized,
        "official_route_initialized": initialized,
        "finite_lc_segment_produced": finite_lc_segment,
        "finite_lc_update_count": finite_lc_updates,
        "poor_or_divergent_native_result": poor,
        "matlab_process_returncode": process_returncode,
        "terminal_status": terminal,
        "accuracy_or_superiority_claim": False,
    }


def freeze_native_solution(
    native_solution: str | Path,
    output_root: str | Path,
    *,
    matlab_result: Mapping[str, Any],
    input_counts: Mapping[str, Any],
    provenance: Mapping[str, Any],
    normalization_root: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(native_solution).resolve(strict=True)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    frozen = root / "GINAV_BY2_C00_NATIVE_SOLUTION.pos"
    frozen.write_bytes(source.read_bytes())
    if sha256_file(frozen) != sha256_file(source):
        raise OutputContractError("native solution freeze hash parity failed")
    rows = read_official_solution(frozen)
    summary = summarize_solution(rows)
    summary["finite_lc_update_count"] = sum(
        row.status == LC_UPDATE_STATUS and row.state_finite and row.covariance_finite
        for row in rows
    )
    normalized_root = Path(normalization_root) if normalization_root is not None else root
    normalized_root.mkdir(parents=True, exist_ok=True)
    standard_nav_path = normalized_root / "GINAV_BY2_C00_STANDARD_NAV.csv"
    write_standard_nav(standard_nav_path, rows)
    write_status_stream(root / "GINAV_BY2_C00_STATUS_STREAM.csv", rows)
    failures = failure_ledger(
        str(matlab_result.get("stdout") or ""), str(matlab_result.get("stderr") or "")
    )
    with (root / "GINAV_BY2_C00_FAILURE_LEDGER.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fieldnames = ("sequence", "stream", "line_number", "severity", "message")
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(failures)
    with (root / "GINAV_BY2_C00_RUNTIME.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("runtime_seconds", "matlab_returncode", "warning_failure_count"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "runtime_seconds": matlab_result.get("runtime_seconds"),
                "matlab_returncode": matlab_result.get("returncode"),
                "warning_failure_count": len(failures),
            }
        )
    returncode = matlab_result.get("returncode")
    if returncode is None:
        raise OutputContractError("native result is missing MATLAB return code")
    admission = formal_admission(summary, process_returncode=int(returncode))
    required_provenance_keys = (
        "data_mode", "dataset_role", "raw_source_hashes", "provider_hashes",
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input",
        "LegSA_output_solver_input", "per_case_tuning",
        "output_only_correction", "epoch_deleted_for_metric",
        "old_runtime_input_count", "code_commit", "config_hash",
    )
    missing_provenance = [
        key for key in required_provenance_keys if key not in provenance
    ]
    if missing_provenance:
        raise OutputContractError(
            "native provenance is incomplete: " + ",".join(missing_provenance)
        )
    native_provenance = {
        key: provenance[key] for key in required_provenance_keys
    }
    native_summary = {
        "schema_version": "ginav2021.by2_c00_native_summary.v1",
        **native_provenance,
        **dict(input_counts),
        **summary,
        "warning_failure_count": len(failures),
        "runtime_seconds": matlab_result.get("runtime_seconds"),
        "native_solution_sha256": sha256_file(frozen),
        "trace_or_reference_opened": False,
        "performance_judged_against_reference": False,
        **admission,
    }
    (root / "GINAV_BY2_C00_NATIVE_SUMMARY.json").write_text(
        json.dumps(native_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    freeze = {
        "schema_version": "ginav2021.by2_c00_native_freeze.v1",
        **native_provenance,
        "freeze_precedes_reference_access": True,
        "native_solution": {
            "path": frozen.name,
            "bytes": frozen.stat().st_size,
            "sha256": sha256_file(frozen),
        },
        "standard_nav_path": str(standard_nav_path),
        "standard_nav_sha256": sha256_file(standard_nav_path),
        "status_stream_sha256": sha256_file(root / "GINAV_BY2_C00_STATUS_STREAM.csv"),
        "trace_open_count_at_freeze": 0,
        "reference_open_count_at_freeze": 0,
        "formal_admission": admission,
    }
    (root / "GINAV_BY2_C00_NATIVE_FREEZE.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return native_summary
