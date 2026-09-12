"""Fresh-provider adapters and the sixty controlled-degradation handlers.

The adapter starts from the current CLEAN2R2A1 fresh provider bytes.  It never
loads the old M1R2B runtime bundle (whose receiver velocity and Go2 values were
derived placeholders).  All perturbations happen in attempt-owned memory and
are written below the caller-provided provider root.
"""

from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence

import numpy as np

from .case_manifest import validate_case_manifest
from .matrix_spec import CLEAN_CASE_ID, WINDOW_END_S, WINDOW_START_S, load_type_registry
from .seed_anchor import place_interval, place_repeated_d07, stable_component_rngs
from ..evaluator import _ecef, _ecef_to_geodetic


GNSS15_FIELDS = (
    "time", "lat_deg", "lon_deg", "height_m", "std_n_m", "std_e_m", "std_d_m",
    "vn_mps", "ve_mps", "vd_mps", "std_vn_mps", "std_ve_mps", "std_vd_mps",
    "body_yaw_ned_deg", "yaw_std_deg",
)
SOLVER_SOURCE_IDS = (
    "gnss_position", "receiver_velocity", "dual_yaw", "raw_doppler",
    "go2_rp", "go2_hv",
)
D57_TIMING_SOURCE_IDS = SOLVER_SOURCE_IDS
AUDIT_ONLY_SOURCE_IDS = ("source_quality_metadata",)
D57_ORIGINAL_ROW_ID = "__canonical541_original_row_id"
COMPONENT_RNG_NAMES = (
    "selection", "selection:gnss_position", "selection:receiver_velocity",
    "selection:dual_yaw", "direction", "noise_position", "noise_velocity", "noise_yaw",
    "noise_velocity:receiver", "noise_velocity:raw_doppler",
    "phase", "burst", "latency", "jitter", "metadata",
)
OUTPUT_FILENAMES = {
    "gnss_position": "gnss_position_provider.csv",
    "receiver_velocity": "receiver_velocity_provider.csv",
    "dual_yaw": "dual_yaw_provider.csv",
    "raw_doppler": "raw_doppler_provider.csv",
    "go2_rp": "go2_rp_provider.csv",
    "go2_hv": "go2_hv_provider.csv",
    "source_quality_metadata": "source_quality_metadata.csv",
}


class ProviderGenerationError(RuntimeError):
    pass


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_provider_bundle_sha256(*, imu_sha256: str,
                                     source_hashes: Mapping[str, str]) -> str:
    """Hash scientific provider content only, never storage paths/modes.

    中文说明：pointer 绝对路径和 materialized/pointer 存储方式只是 attempt
    元数据；把它们写进去重键会让内容相同的 case 无法安全复用。
    """

    payload = {
        "imu_sha256": str(imu_sha256),
        "source_sha256": {key: str(source_hashes[key]) for key in sorted(source_hashes)},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    fields = tuple(reader.fieldnames or ())
    if not fields or not rows:
        raise ProviderGenerationError(f"empty provider table: {path.name}")
    return fields, rows


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _write_deterministic_gzip_csv(path: Path, fields: Sequence[str],
                                  rows: Iterable[Mapping[str, Any]]) -> None:
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    with path.open("xb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=9, mtime=0) as compressor:
            compressor.write(buffer.getvalue().encode("utf-8"))


def perturbation_ledger_rows(base: "ProviderBundle", generated: "ProviderBundle",
                             type_id: str) -> list[dict[str, Any]]:
    """Record exact changed row/field identity for later mechanism joins."""

    rows: list[dict[str, Any]] = []
    for source in sorted(generated.tables):
        before = base.tables[source]; after = generated.tables[source]
        if len(before.rows) != len(after.rows):
            raise ProviderGenerationError(f"provider row count changed: {source}")
        if type_id == "D57" and source in D57_TIMING_SOURCE_IDS:
            by_identity = {int(row[D57_ORIGINAL_ROW_ID]): row for row in after.rows}
            if set(by_identity) != set(range(len(before.rows))):
                raise ProviderGenerationError(f"D57 original-row identity closure failed: {source}")
            pairs = ((index, left, by_identity[index]) for index, left in enumerate(before.rows))
        else:
            pairs = ((index, left, right) for index, (left, right) in enumerate(zip(before.rows, after.rows)))
        for index, left, right in pairs:
            changed = sorted(field for field in set(left) | set(right)
                             if field != D57_ORIGINAL_ROW_ID
                             and str(left.get(field, "")) != str(right.get(field, "")))
            if type_id == "D57" and source in D57_TIMING_SOURCE_IDS:
                changed = sorted(set(changed) | {"time"})
            if not changed:
                continue
            rows.append({
                "source": source, "row_index": index,
                "base_time": left.get("time", ""), "generated_time": right.get("time", ""),
                "changed_fields": ";".join(changed),
            })
    return rows


def _finite(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ProviderGenerationError("provider contains NaN or Inf")
    return number


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "active", "available"}


def _wrap_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


@dataclass
class ProviderTable:
    fields: tuple[str, ...]
    rows: list[dict[str, Any]]

    def clone(self) -> "ProviderTable":
        return ProviderTable(self.fields, copy.deepcopy(self.rows))

    def canonical_bytes(self) -> bytes:
        import io
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(self.fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(self.rows)
        return buffer.getvalue().encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass
class ProviderBundle:
    imu_path: Path
    tables: dict[str, ProviderTable]
    raw_input_hashes: Mapping[str, str]
    base_provider_hashes: Mapping[str, str]
    dual_yaw_audit_rows: list[dict[str, str]]
    original_provider_paths: Mapping[str, Path] = field(default_factory=dict)

    def clone(self) -> "ProviderBundle":
        return ProviderBundle(
            self.imu_path, {key: value.clone() for key, value in self.tables.items()},
            dict(self.raw_input_hashes), dict(self.base_provider_hashes),
            copy.deepcopy(self.dual_yaw_audit_rows), dict(self.original_provider_paths),
        )

    def hashes(self) -> dict[str, str]:
        return {key: table.sha256() for key, table in self.tables.items()}


def load_current_fresh_bundle(
    *, imu_path: str | Path, gnss15_path: str | Path, raw_doppler_path: str | Path,
    go2_rp_path: str | Path, go2_hv_path: str | Path,
    dual_yaw_audit_path: str | Path, source_quality_path: str | Path,
    raw_input_hashes: Mapping[str, str],
) -> ProviderBundle:
    """Adapt only current fresh clean artifacts into separate canonical sources."""

    paths = [Path(value).expanduser().resolve(strict=True) for value in (
        imu_path, gnss15_path, raw_doppler_path, go2_rp_path, go2_hv_path,
        dual_yaw_audit_path, source_quality_path,
    )]
    imu, gnss, raw, rp, hv, yaw_audit, quality = paths
    gnss_rows: list[dict[str, Any]] = []
    for number, line in enumerate(gnss.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        values = line.split()
        if len(values) != 15:
            raise ProviderGenerationError(f"fresh GNSS row {number} is not 15 columns")
        [_finite(value) for value in values]
        gnss_rows.append(dict(zip(GNSS15_FIELDS, values)))
    if not gnss_rows:
        raise ProviderGenerationError("fresh GNSS provider is empty")
    position_rows = [{
        "time": row["time"], "lat_deg": row["lat_deg"], "lon_deg": row["lon_deg"],
        "height_m": row["height_m"], "std_n_m": row["std_n_m"],
        "std_e_m": row["std_e_m"], "std_d_m": row["std_d_m"],
        "valid": "1", "status": "clean_active",
    } for row in gnss_rows]
    velocity_rows = [{
        "time": row["time"], "vn": row["vn_mps"], "ve": row["ve_mps"], "vd": row["vd_mps"],
        "std_vn": row["std_vn_mps"], "std_ve": row["std_ve_mps"], "std_vd": row["std_vd_mps"],
        "valid": "1", "status": "clean_active",
    } for row in gnss_rows]
    yaw_fields, yaw_audit_rows = _read_csv(yaw_audit)
    audit_times = np.asarray([_finite(row["time"]) for row in yaw_audit_rows])
    # source_timestamp is Unix time.  Rebase through the frozen CLEAN1 base time,
    # not by first-row alignment (which would introduce a ~0.206 s shift).
    rebased_audit_times = np.asarray([
        _finite(row["source_timestamp"]) - 1772784000.0 for row in yaw_audit_rows
    ])
    yaw_rows = []
    for row in gnss_rows:
        time = _finite(row["time"])
        audit = yaw_audit_rows[int(np.argmin(np.abs(rebased_audit_times - time)))]
        yaw_rows.append({
            "time": row["time"], "yaw_deg": row["body_yaw_ned_deg"],
            "yaw_std_deg": row["yaw_std_deg"], "valid": "1",
            "baseline_n_m": audit["baseline_n_m"], "baseline_e_m": audit["baseline_e_m"],
            "baseline_d_m": audit["baseline_d_m"], "baseline_length_m": audit["baseline_length_m"],
            "physical_in_band": audit["physical_in_band"], "source_status": audit["source_status"],
            "gnss_order": "GNSS2-GNSS1", "lateral_to_body_offset_deg": "90.0",
            "wrap_safe_residual": "True", "trace_sign_or_offset_selection": "False",
        })
    raw_fields, raw_rows = _read_csv(raw)
    rp_fields, rp_rows = _read_csv(rp)
    hv_fields, hv_rows = _read_csv(hv)
    quality_fields, quality_rows = _read_csv(quality)
    tables = {
        "gnss_position": ProviderTable(tuple(position_rows[0]), position_rows),
        "receiver_velocity": ProviderTable(tuple(velocity_rows[0]), velocity_rows),
        "dual_yaw": ProviderTable(tuple(yaw_rows[0]), yaw_rows),
        "raw_doppler": ProviderTable(raw_fields, raw_rows),
        "go2_rp": ProviderTable(rp_fields, rp_rows),
        "go2_hv": ProviderTable(hv_fields, hv_rows),
        "source_quality_metadata": ProviderTable(quality_fields, quality_rows),
    }
    return ProviderBundle(
        imu_path=imu, tables=tables, raw_input_hashes=dict(raw_input_hashes),
        base_provider_hashes={
            "imu": sha256_file(imu), "gnss": sha256_file(gnss),
            "raw_doppler": sha256_file(raw), "go2_rp": sha256_file(rp), "go2_hv": sha256_file(hv),
        }, dual_yaw_audit_rows=yaw_audit_rows,
        original_provider_paths={
            "combined_gnss": gnss, "raw_doppler": raw,
            "go2_rp": rp, "go2_hv": hv,
        },
    )


def _times(table: ProviderTable) -> np.ndarray:
    return np.asarray([_finite(row["time"]) for row in table.rows])


def _valid_indices(table: ProviderTable) -> np.ndarray:
    return np.asarray([index for index, row in enumerate(table.rows) if _bool(row.get("valid", row.get("update_flag", 1)))], dtype=int)


def _interval_indices(table: ProviderTable, interval: tuple[float, float]) -> np.ndarray:
    times = _times(table); start, end = interval
    return np.flatnonzero((times >= start) & (times < end))


def _random_subset(rng: np.random.Generator, candidates: np.ndarray, ratio: float) -> np.ndarray:
    count = int(round(float(ratio) * len(candidates)))
    if count <= 0:
        return np.asarray([], dtype=int)
    return np.sort(rng.choice(candidates, size=min(count, len(candidates)), replace=False).astype(int))


def _invalidate(table: ProviderTable, indices: Iterable[int], status: str) -> int:
    count = 0
    for index in indices:
        row = table.rows[int(index)]
        row["valid"] = "0"
        if "update_flag" in row:
            row["update_flag"] = "False"
        if "provider_status" in row:
            row["provider_status"] = status
        if "source_status" in row:
            row["source_status"] = status
        row["status"] = status
        count += 1
    return count


def _add_position(row: MutableMapping[str, Any], north: float, east: float, up: float) -> None:
    """Apply a local N/E/U displacement through exact WGS84 ECEF rotation."""

    lat = _finite(row["lat_deg"]); lon = _finite(row["lon_deg"]); height = _finite(row["height_m"])
    x, y, z = _ecef(lat, lon, height)
    phi = math.radians(lat); lam = math.radians(lon); down = -float(up)
    # evaluator._ecef_delta_ned 的正交旋转转置：NED -> ECEF。
    dx = (-math.sin(phi) * math.cos(lam) * north
          - math.sin(lam) * east
          - math.cos(phi) * math.cos(lam) * down)
    dy = (-math.sin(phi) * math.sin(lam) * north
          + math.cos(lam) * east
          - math.cos(phi) * math.sin(lam) * down)
    dz = math.cos(phi) * north - math.sin(phi) * down
    new_lat, new_lon, new_height = _ecef_to_geodetic(x + dx, y + dy, z + dz)
    row["lat_deg"] = f"{new_lat:.10f}"
    row["lon_deg"] = f"{new_lon:.10f}"
    row["height_m"] = f"{new_height:.6f}"


def _add_velocity(row: MutableMapping[str, Any], delta: Sequence[float]) -> None:
    fields = ("vn", "ve", "vd")
    for field, value in zip(fields, delta):
        row[field] = f"{_finite(row[field]) + float(value):.9f}"


def _scale(row: MutableMapping[str, Any], fields: Sequence[str], factor: float, floor: float | None = None) -> None:
    for field in fields:
        value = _finite(row[field]) * factor
        if floor is not None:
            value = max(floor, value)
        row[field] = f"{value:.9f}"


def _component(name: str, source: str, count: int, **details: Any) -> dict[str, Any]:
    return {"component": name, "affected_source": source, "affected_epoch_count": int(count),
            "details": details, "status": "PASS"}


def _source_table(bundle: ProviderBundle, source: str) -> ProviderTable:
    aliases = {
        "gnss_position": "gnss_position", "receiver_velocity": "receiver_velocity",
        "dual_yaw": "dual_yaw", "raw_doppler": "raw_doppler",
        "go2_rp": "go2_rp", "go2_hv": "go2_hv",
    }
    return bundle.tables[aliases[source]]


def _interval(case: Mapping[str, Any], duration: float) -> tuple[float, float]:
    return place_interval(float(case["anchor_time_s"]), duration)


def _outage(bundle: ProviderBundle, case: Mapping[str, Any], sources: Sequence[str], duration: float) -> list[dict[str, Any]]:
    interval = _interval(case, duration); rows = []
    for source in sources:
        table = _source_table(bundle, source); indices = _interval_indices(table, interval)
        rows.append(_component("outage", source, _invalidate(table, indices, "controlled_outage"), interval=interval))
    return rows


def _position_noise(table: ProviderTable, rng: np.random.Generator, h_sigma: float, v_sigma: float,
                    indices: np.ndarray | None = None) -> int:
    selected = np.arange(len(table.rows)) if indices is None else indices
    north = rng.normal(0.0, h_sigma, len(selected)); east = rng.normal(0.0, h_sigma, len(selected)); up = rng.normal(0.0, v_sigma, len(selected))
    for index, n, e, u in zip(selected, north, east, up):
        _add_position(table.rows[int(index)], float(n), float(e), float(u))
    return len(selected)


def _velocity_noise(table: ProviderTable, rng: np.random.Generator, sigma: float,
                    indices: np.ndarray | None = None) -> int:
    selected = np.arange(len(table.rows)) if indices is None else indices
    noise = rng.normal(0.0, sigma, (len(selected), 3))
    for index, delta in zip(selected, noise):
        _add_velocity(table.rows[int(index)], delta)
    return len(selected)


def _spike_vectors(rng: np.random.Generator, count: int, magnitude: float, dimensions: int = 3) -> np.ndarray:
    values = rng.normal(size=(count, dimensions)); norms = np.linalg.norm(values, axis=1)
    values[norms <= 1e-15, 0] = 1.0; norms = np.linalg.norm(values, axis=1)
    return magnitude * values / norms[:, None]


def apply_degradation(base: ProviderBundle, case: Mapping[str, Any]) -> tuple[ProviderBundle, list[dict[str, Any]], dict[str, Any]]:
    """Apply one exact D01..D60 case with stable named RNG substreams."""

    bundle = base.clone()
    type_id = str(case["degradation_type_id"])
    if type_id == "CLEAN":
        return bundle, [_component("clean_reference_no_degradation", "none", 0)], {"no_active_path": False}
    spec = load_type_registry()[int(type_id[1:]) - 1]
    rngs = stable_component_rngs(int(case["seed_value"]), COMPONENT_RNG_NAMES)
    c: list[dict[str, Any]] = []
    no_active_path = False
    pos = bundle.tables["gnss_position"]; vel = bundle.tables["receiver_velocity"]
    yaw = bundle.tables["dual_yaw"]; raw = bundle.tables["raw_doppler"]
    rp = bundle.tables["go2_rp"]; hv = bundle.tables["go2_hv"]
    metadata = bundle.tables["source_quality_metadata"]
    n = int(type_id[1:])
    if n in range(1, 7):
        duration = (3, 5, 10, 20, 10, 20)[n - 1]
        sources = ["gnss_position"]
        if n >= 5: sources.append("receiver_velocity")
        if n == 6: sources.append("dual_yaw")
        c.extend(_outage(bundle, case, sources, duration))
    elif n == 7:
        count = 0; intervals = place_repeated_d07(float(case["anchor_time_s"]))
        for interval in intervals:
            count += _invalidate(pos, _interval_indices(pos, interval), "controlled_repeated_outage")
        c.append(_component("repeated_3x3s_outage", "gnss_position", count, intervals=intervals))
    elif n in (8, 9, 10):
        target = {8: 5.0, 9: 2.0, 10: 1.0}[n]; changed = 0; idempotent = True
        for table in (pos, vel, yaw):
            valid = _valid_indices(table); times = _times(table)[valid]
            if len(times) < 2: continue
            median_rate = 1.0 / float(np.median(np.diff(times)))
            if median_rate <= target + 1e-9: continue
            idempotent = False
            phase = float(case["anchor_time_s"]) % (1.0 / target)
            slots = np.floor((times - phase) * target + 1e-9).astype(np.int64)
            keep_positions = np.unique(slots, return_index=True)[1]
            drop = np.delete(valid, keep_positions)
            changed += _invalidate(table, drop, "controlled_downsample")
        c.append(_component("downsample", "gnss_position+receiver_velocity+dual_yaw", changed, target_rate_hz=target, idempotent=idempotent))
    elif n in (11, 12):
        ratio = 0.30 if n == 11 else 0.60; changed = 0
        for source, table in (("gnss_position", pos), ("receiver_velocity", vel), ("dual_yaw", yaw)):
            selected = _random_subset(rngs[f"selection:{source}"], _valid_indices(table), ratio)
            changed += _invalidate(table, selected, "controlled_random_dropout")
        c.append(_component("random_dropout", "gnss_position+receiver_velocity+dual_yaw", changed, ratio=ratio))
    elif n in (13, 14, 15):
        h, v = {13: (0.5, 1.0), 14: (1.5, 2.5), 15: (3.0, 5.0)}[n]
        c.append(_component("position_gaussian_noise", "gnss_position", _position_noise(pos, rngs["noise_position"], h, v), h_sigma=h, v_sigma=v))
    elif n in (16, 17):
        h, v = {16: (1.5, 0.5), 17: (3.0, 1.0)}[n]
        theta = float(rngs["direction"].uniform(0, 2 * math.pi)); sign = float(rngs["direction"].choice((-1, 1)))
        for row in pos.rows: _add_position(row, h * math.cos(theta), h * math.sin(theta), sign * v)
        c.append(_component("position_static_bias", "gnss_position", len(pos.rows), horizontal_m=h, vertical_m=v, direction_rad=theta, vertical_sign=sign))
    elif n == 18:
        theta = float(rngs["direction"].uniform(0, 2 * math.pi)); vertical_sign = float(rngs["direction"].choice((-1, 1))); count = len(pos.rows)
        times = _times(pos); denominator = WINDOW_END_S - WINDOW_START_S
        for row, time_value in zip(pos.rows, times):
            # 中文说明：漂移只按冻结 evaluator 窗口 66..340 s 归一化，窗口外保持端点值。
            fraction = float(np.clip((time_value - WINDOW_START_S) / denominator, 0.0, 1.0))
            _add_position(row, 3 * fraction * math.cos(theta), 3 * fraction * math.sin(theta), vertical_sign * fraction)
        c.append(_component("position_slow_drift", "gnss_position", count, horizontal_end_m=3.0, vertical_end_m=1.0))
    elif n == 19:
        phase = float(rngs["phase"].uniform(0, 2 * math.pi))
        for row in pos.rows:
            angle = _finite(row["time"]) / 30.0 + phase
            # Preserved effect-validated law: N/E are quadrature components,
            # therefore horizontal magnitude is exactly 2 m at every epoch.
            _add_position(row, 2 * math.cos(angle), 2 * math.sin(angle), 0.5 * math.sin(angle))
        c.append(_component("position_sinusoidal_multipath", "gnss_position", len(pos.rows),
                            period_s=60 * math.pi, phase_rad=phase,
                            horizontal_law="north=2*cos;east=2*sin", vertical_law="up=0.5*sin"))
    elif n in (20, 21):
        ratio, hm, vm = {20: (0.02, 2.0, 1.0), 21: (0.05, 4.0, 2.0)}[n]
        selected = _random_subset(rngs["selection"], _valid_indices(pos), ratio)
        for index in selected:
            theta = float(rngs["direction"].uniform(0, 2 * math.pi)); sign = float(rngs["direction"].choice((-1, 1)))
            _add_position(pos.rows[int(index)], hm * math.cos(theta), hm * math.sin(theta), sign * vm)
        c.append(_component("position_spikes", "gnss_position", len(selected), probability=ratio, horizontal_m=hm, vertical_m=vm))
    elif n == 22:
        length = int(rngs["burst"].integers(3, 6)); valid = _valid_indices(pos)
        start_slot = int(rngs["burst"].integers(0, max(1, len(valid) - length + 1))); selected = valid[start_slot:start_slot + length]
        theta = float(rngs["direction"].uniform(0, 2 * math.pi)); sign = float(rngs["direction"].choice((-1, 1)))
        for index in selected: _add_position(pos.rows[int(index)], 8 * math.cos(theta), 8 * math.sin(theta), sign * 4)
        c.append(_component("position_burst_spike", "gnss_position", len(selected), burst_length=len(selected), horizontal_m=8, vertical_m=4))
    elif n in (23, 24, 25, 26, 28):
        factor = {23: 1.5, 24: 2.5, 25: 4.0, 26: 0.25, 28: 4.0}[n]
        for row in pos.rows: _scale(row, ("std_n_m", "std_e_m", "std_d_m"), factor)
        c.append(_component("position_std_scale", "gnss_position_std", len(pos.rows), factor=factor, values_unchanged=True))
    elif n == 27:
        count = _position_noise(pos, rngs["noise_position"], 3.0, 5.0)
        for row in pos.rows: _scale(row, ("std_n_m", "std_e_m", "std_d_m"), 0.25)
        c.append(_component("bad_position_optimistic_std", "gnss_position+std", count, h_sigma=3, v_sigma=5, std_factor=0.25))
    elif n == 29:
        # 当前18列 solver schema没有 status quality 列；只保留审计动作。
        for row in metadata.rows: row["audit_gnss_quality"] = "controlled_downgrade_no_active_path"
        if "audit_gnss_quality" not in metadata.fields: metadata.fields += ("audit_gnss_quality",)
        no_active_path = True
        c.append(_component("gnss_status_quality_downgrade_only", "source_quality_metadata", len(metadata.rows), no_active_path=True, solver_values_unchanged=True))
    elif n in (30, 31):
        c.extend(_outage(bundle, case, ("dual_yaw",), 5.0 if n == 30 else 20.0))
    elif n in (32, 33, 38):
        sigma = {32: 1.0, 33: 5.0, 38: 10.0}[n]; noise = rngs["noise_yaw"].normal(0, sigma, len(yaw.rows))
        for row, delta in zip(yaw.rows, noise):
            row["yaw_deg"] = f"{_wrap_deg(_finite(row['yaw_deg']) + float(delta)):.9f}"
            if n == 38: _scale(row, ("yaw_std_deg",), 0.25)
        c.append(_component("dual_yaw_noise" if n != 38 else "bad_yaw_optimistic_std", "dual_yaw", len(yaw.rows), sigma_deg=sigma, std_factor=0.25 if n == 38 else 1.0))
    elif n in (34, 35):
        ratio = 0.05 if n == 34 else 0.10; selected = _random_subset(rngs["selection"], _valid_indices(yaw), ratio)
        for index in selected:
            row = yaw.rows[int(index)]; row["yaw_deg"] = f"{_wrap_deg(_finite(row['yaw_deg']) + float(rngs['direction'].choice((-10.0, 10.0)))):.9f}"
        c.append(_component("dual_yaw_spikes", "dual_yaw", len(selected), probability=ratio, signed_magnitude_deg=10.0))
    elif n in (36, 37):
        factor = 1.5 if n == 36 else 3.0
        for row in yaw.rows: _scale(row, ("yaw_std_deg",), factor)
        c.append(_component("dual_yaw_std_scale", "dual_yaw_std", len(yaw.rows), factor=factor))
    elif n == 39:
        valid = _valid_indices(yaw); selected: set[int] = set(); lengths = []; occupied_slots: set[int] = set()
        for _ in range(3):
            length = int(rngs["burst"].integers(2, 5)); lengths.append(length)
            candidates = [slot for slot in range(max(1, len(valid) - length + 1))
                          if not set(range(max(0, slot - 1), min(len(valid), slot + length + 1))) & occupied_slots]
            if not candidates:
                raise ProviderGenerationError("D39 cannot place three non-overlapping valid bursts")
            slot = int(rngs["burst"].choice(candidates)); occupied_slots.update(range(slot, slot + length))
            selected.update(int(value) for value in valid[slot:slot + length])
        for index in sorted(selected):
            row = yaw.rows[index]; row["valid"] = "0"; row["source_status"] = "quality_unavailable"
        c.append(_component("baseline_quality_dropout", "dual_yaw_quality", len(selected), burst_count=3, burst_lengths=lengths))
    elif n == 40:
        noise = rngs["noise_yaw"].normal(0, 0.03, len(yaw.rows))
        for row, delta in zip(yaw.rows, noise):
            row["baseline_length_m"] = f"{max(0.01, _finite(row['baseline_length_m']) + float(delta)):.9f}"
        # 中文说明：preserved handler 的第二项是 rel_acc_m×2，但 fresh
        # dual-yaw schema没有 rel_acc_m，C++ 18列输入也不消费 baseline length。
        # 米制 rel_acc 绝不能被猜测映射为角度制 yaw_std；因此仅保留
        # baseline-length 审计扰动，并明确记录当前 solver 路径为 no-active-path。
        no_active_path = True
        c.append(_component(
            "baseline_length_jitter_relacc", "dual_yaw_quality", len(yaw.rows),
            sigma_m=0.03, rel_acc_factor=2, yaw_unchanged=True,
            rel_acc_field_available=False,
            rel_acc_no_active_path=True,
            baseline_length_solver_visible=False,
            solver_visible_mapping="none_audit_only_baseline_metadata",
            solver_runtime_input_unchanged=True,
            unit_aliasing_forbidden=True,
        ))
    elif n == 41:
        target = "GNSS1" if int(case["seed_value"]) % 2 == 0 else "GNSS2"; sign = -1.0 if target == "GNSS1" else 1.0
        noise = rngs["noise_position"].normal(0, (3.0, 3.0, 2.0), (len(yaw.rows), 3))
        for index, (row, delta) in enumerate(zip(yaw.rows, noise)):
            bn = _finite(row["baseline_n_m"]) + sign * float(delta[0]); be = _finite(row["baseline_e_m"]) + sign * float(delta[1]); bd = _finite(row["baseline_d_m"]) + sign * float(delta[2])
            length = math.sqrt(bn * bn + be * be + bd * bd); heading = math.degrees(math.atan2(be, bn)); body = _wrap_deg(heading + 90.0)
            row.update(baseline_n_m=f"{bn:.9f}", baseline_e_m=f"{be:.9f}", baseline_d_m=f"{bd:.9f}", baseline_length_m=f"{length:.9f}", yaw_deg=f"{body:.9f}")
        c.append(_component("asymmetric_antenna_noise", target, len(yaw.rows), horizontal_sigma_m=3, vertical_sigma_m=2, geometry="GNSS2-GNSS1+90deg"))
    elif n in (42, 46):
        c.extend(_outage(bundle, case, ("receiver_velocity" if n == 42 else "raw_doppler",), 20.0))
    elif n in (43, 47):
        table = vel if n == 43 else raw; count = _velocity_noise(table, rngs["noise_velocity"], 0.5)
        c.append(_component("velocity_noise", "receiver_velocity" if n == 43 else "raw_doppler", count, sigma_mps=0.5))
    elif n in (44, 48):
        table = vel if n == 44 else raw; magnitude = 2.0 if n == 44 else 1.5
        selected = _random_subset(rngs["selection"], _valid_indices(table), 0.02)
        dimensions = 3 if n == 44 else 2
        vectors = _spike_vectors(rngs["direction"], len(selected), magnitude, dimensions=dimensions)
        if dimensions == 2: vectors = np.column_stack((vectors, np.zeros(len(vectors))))
        for index, delta in zip(selected, vectors): _add_velocity(table.rows[int(index)], delta)
        c.append(_component("velocity_spikes", "receiver_velocity" if n == 44 else "raw_doppler", len(selected), probability=0.02, magnitude_mps=magnitude))
    elif n in (45, 49):
        table = vel if n == 45 else raw; count = _velocity_noise(table, rngs["noise_velocity"], 0.5)
        for row in table.rows: _scale(row, ("std_vn", "std_ve", "std_vd"), 0.25)
        c.append(_component("velocity_bad_optimistic_std", "receiver_velocity" if n == 45 else "raw_doppler", count, sigma_mps=0.5, std_factor=0.25, spike_component=False))
    elif n == 50:
        theta = float(rngs["direction"].uniform(0, 2 * math.pi)); delta = (math.cos(theta), math.sin(theta), 0.0)
        for row in raw.rows: _add_velocity(row, delta)
        c.append(_component("raw_receiver_velocity_conflict", "raw_doppler", len(raw.rows), raw_horizontal_offset_mps=1.0, receiver_velocity_unchanged=True, direction_rad=theta))
    elif n == 51:
        selected = set(int(v) for v in _random_subset(rngs["selection"], _valid_indices(rp), 0.5)); count = 0
        for index, row in enumerate(rp.rows):
            if index in selected: _invalidate(rp, (index,), "controlled_dropout")
            else:
                row["roll_rad"] = f"{_finite(row['roll_rad']) + math.radians(float(rngs['noise_yaw'].normal(0, 3))):.12f}"
                row["pitch_rad"] = f"{_finite(row['pitch_rad']) + math.radians(float(rngs['noise_yaw'].normal(0, 3))):.12f}"
            count += 1
        c.append(_component("go2_rp_dropout_noise", "go2_rp", count, dropout_ratio=0.5, remaining_sigma_deg=3))
    elif n == 52:
        theta = float(rngs["direction"].uniform(0, 2 * math.pi)); dr = math.radians(2 * math.cos(theta)); dp = math.radians(2 * math.sin(theta))
        for row in rp.rows: row["roll_rad"] = f"{_finite(row['roll_rad']) + dr:.12f}"; row["pitch_rad"] = f"{_finite(row['pitch_rad']) + dp:.12f}"
        c.append(_component("go2_rp_bias", "go2_rp", len(rp.rows), vector_magnitude_deg=2, direction_rad=theta))
    elif n == 53:
        noise = rngs["noise_velocity"].normal(0, 1.0, (len(hv.rows), 2))
        for row, delta in zip(hv.rows, noise): row["vn"] = f"{_finite(row['vn']) + float(delta[0]):.9f}"; row["ve"] = f"{_finite(row['ve']) + float(delta[1]):.9f}"
        c.append(_component("go2_hv_noise", "go2_hv", len(hv.rows), sigma_mps=1.0))
    elif n == 54:
        seed_index = int(str(case["seed_index"])[-2:]); scale = 1.5 if seed_index <= 3 or seed_index == 8 else 1.0; ratio = 0.5 if seed_index >= 4 else 0.0
        for row in hv.rows: row["vn"] = f"{_finite(row['vn']) * scale:.9f}"; row["ve"] = f"{_finite(row['ve']) * scale:.9f}"
        selected = _random_subset(rngs["selection"], _valid_indices(hv), ratio) if ratio else np.asarray([], dtype=int); _invalidate(hv, selected, "controlled_dropout")
        c.append(_component("go2_hv_scale_dropout", "go2_hv", len(hv.rows), scale=scale, dropout_count=len(selected), dropout_ratio=ratio))
    elif n in (55, 56):
        # C++ active path does not load SOURCE_QUALITY_METADATA.csv.  Preserve the
        # requested audit perturbation but do not invent a factor to force output.
        ratio = 0.35 if n == 55 else 0.30; selected = _random_subset(rngs["metadata"], np.arange(len(metadata.rows)), ratio)
        field = "audit_go2_metadata"
        if field not in metadata.fields: metadata.fields += (field,)
        for ordinal, index in enumerate(selected):
            seed_index = int(str(case["seed_index"])[-2:])
            if n == 55: value = "contact_uncertain_mode_gait_unknown"
            elif seed_index == 8: value = "high_high" if ordinal % 2 == 0 else "low_low"
            else: value = "high_high" if seed_index % 2 == 0 else "low_low"
            metadata.rows[int(index)][field] = value
        no_active_path = True
        c.append(_component("go2_metadata_uncertain" if n == 55 else "go2_foot_speed_contact_conflict", "source_quality_metadata", len(selected), no_active_path=True, ratio=ratio))
    elif n == 57:
        timing_sources = D57_TIMING_SOURCE_IDS
        timing_names = tuple(f"{source}:{component}" for source in timing_sources for component in ("latency", "jitter_max", "jitter"))
        timing_rngs = stable_component_rngs(int(case["seed_value"]), timing_names)
        for source in timing_sources:
            table = bundle.tables[source]
            latency = float(timing_rngs[f"{source}:latency"].uniform(0.1, 0.3)); jmax = float(timing_rngs[f"{source}:jitter_max"].uniform(0.020, 0.050)); jitter = timing_rngs[f"{source}:jitter"].uniform(-jmax, jmax, len(table.rows))
            for original_index, (row, value) in enumerate(zip(table.rows, jitter)):
                row[D57_ORIGINAL_ROW_ID] = str(original_index)
                row["time"] = f"{_finite(row['time']) + latency + float(value):.12f}"
            table.rows.sort(key=lambda row: _finite(row["time"]))
            # Tiny collisions are resolved deterministically without reordering source identities.
            previous = -math.inf
            for row in table.rows:
                current = _finite(row["time"])
                if current <= previous: current = math.nextafter(previous, math.inf); row["time"] = f"{current:.15f}"
                previous = current
            c.append(_component("latency_jitter", source, len(table.rows), latency_s=latency, jitter_max_s=jmax))
    elif n == 58:
        interval = _interval(case, 10.0); c.extend(_outage(bundle, case, ("gnss_position",), 10.0))
        candidates = _interval_indices(yaw, interval); candidates = np.asarray([i for i in candidates if _bool(yaw.rows[int(i)].get("valid", 1))], dtype=int); selected = _random_subset(rngs["selection"], candidates, 0.10)
        for index in selected: yaw.rows[int(index)]["yaw_deg"] = f"{_wrap_deg(_finite(yaw.rows[int(index)]['yaw_deg']) + float(rngs['direction'].choice((-10, 10)))):.9f}"
        c.append(_component("yaw_spikes_during_outage", "dual_yaw", len(selected), magnitude_deg=10)); c.append(_component("clean_recovery_interval", "all_sources", 0, interval=(interval[1], min(WINDOW_END_S, interval[1] + 20.0))))
    elif n == 59:
        count = _position_noise(pos, rngs["noise_position"], 3.0, 5.0); theta = float(rngs["direction"].uniform(0, 2 * math.pi)); delta = (math.cos(theta), math.sin(theta), 0)
        for row in raw.rows: _add_velocity(row, delta)
        c.extend((_component("bad_position", "gnss_position", count, h_sigma=3, v_sigma=5), _component("good_yaw_preserved", "dual_yaw", 0, values_unchanged=True), _component("raw_receiver_conflict", "raw_doppler", len(raw.rows), offset_mps=1, receiver_unchanged=True)))
    elif n == 60:
        interval = _interval(case, 20.0); pi = _interval_indices(pos, interval); yi = _interval_indices(yaw, interval); vi = _interval_indices(vel, interval); ri = _interval_indices(raw, interval)
        _position_noise(pos, rngs["noise_position"], 3, 5, pi)
        for index in pi: _scale(pos.rows[int(index)], ("std_n_m", "std_e_m", "std_d_m"), 0.25)
        ynoise = rngs["noise_yaw"].normal(0, 10, len(yi))
        for index, delta in zip(yi, ynoise): yaw.rows[int(index)]["yaw_deg"] = f"{_wrap_deg(_finite(yaw.rows[int(index)]['yaw_deg']) + float(delta)):.9f}"; _scale(yaw.rows[int(index)], ("yaw_std_deg",), 0.25)
        # 中文说明：D60 两个速度源使用命名独立子流，增加/重排其他组件不改变其随机序列。
        _velocity_noise(vel, rngs["noise_velocity:receiver"], 0.5, vi)
        _velocity_noise(raw, rngs["noise_velocity:raw_doppler"], 0.5, ri)
        for index in vi: _scale(vel.rows[int(index)], ("std_vn", "std_ve", "std_vd"), 0.25)
        for index in ri: _scale(raw.rows[int(index)], ("std_vn", "std_ve", "std_vd"), 0.25)
        c.append(_component("multisource_bad_optimistic", "position+yaw+receiver_velocity+raw_doppler", len(pi) + len(yi) + len(vi) + len(ri), interval=interval)); c.append(_component("clean_recovery_interval", "all_sources", 0, interval=(interval[1], min(WINDOW_END_S, interval[1] + 20.0))))
    else:  # pragma: no cover - registry test guarantees closure
        raise ProviderGenerationError(f"handler not implemented: {type_id}")
    return bundle, c, {"no_active_path": no_active_path, "degradation_type_id": type_id,
                       "seed_replay": int(case["seed_value"]), "trace_read_count": 0}


HANDLERS: dict[str, Callable[[ProviderBundle, Mapping[str, Any]], tuple[ProviderBundle, list[dict[str, Any]], dict[str, Any]]]] = {
    f"D{index:02d}": apply_degradation for index in range(1, 61)
}


def compose_solver_gnss18(bundle: ProviderBundle) -> list[list[str]]:
    """Compose 18-column GNSS without deleting any multi-source epoch.

    Position, receiver velocity and yaw have independent validity flags.  For
    D57 the union of their timestamps is emitted so a latency shift never
    silently deletes an adjacent source update.
    """

    sources = [bundle.tables[name] for name in ("gnss_position", "receiver_velocity", "dual_yaw")]
    union = sorted(set(float(row["time"]) for table in sources for row in table.rows))
    source_times = [_times(table) for table in sources]
    rows: list[list[str]] = []
    tolerance = 1e-8
    for time in union:
        selected: list[dict[str, Any] | None] = []
        for table, times in zip(sources, source_times):
            index = int(np.argmin(np.abs(times - time))); selected.append(table.rows[index] if abs(float(times[index]) - time) <= tolerance else None)
        position, velocity, yaw = selected
        # Placeholders are numeric but disabled by validity; C++ must not consume them.
        position = position or sources[0].rows[0]; velocity = velocity or sources[1].rows[0]; yaw = yaw or sources[2].rows[0]
        p_valid = int(selected[0] is not None and _bool(position.get("valid", 1)))
        v_valid = int(selected[1] is not None and _bool(velocity.get("valid", 1)))
        y_valid = int(selected[2] is not None and _bool(yaw.get("valid", 1)))
        rows.append([
            f"{time:.12f}", str(position["lat_deg"]), str(position["lon_deg"]), str(position["height_m"]),
            str(position["std_n_m"]), str(position["std_e_m"]), str(position["std_d_m"]),
            str(velocity["vn"]), str(velocity["ve"]), str(velocity["vd"]),
            str(velocity["std_vn"]), str(velocity["std_ve"]), str(velocity["std_vd"]),
            str(yaw["yaw_deg"]), str(yaw["yaw_std_deg"]), str(p_valid), str(v_valid), str(y_valid),
        ])
    return rows


def write_case_provider(
    *, base: ProviderBundle, case: Mapping[str, Any], case_root: str | Path,
    clean_case_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(case_root).resolve(strict=False)
    if root.exists():
        raise ProviderGenerationError("case root already exists; attempt-owned generation does not overwrite")
    bundle, components, semantics = apply_degradation(base, case)
    spec_dir = root / "00_CASE_SPEC"; hash_dir = root / "01_INPUT_HASHES"
    provider_dir = root / "02_PROVIDERS"; validation_dir = root / "03_EFFECT_VALIDATION"; ready_dir = root / "04_PROVIDER_READY"
    for directory in (spec_dir, hash_dir, provider_dir, validation_dir, ready_dir): directory.mkdir(parents=True, exist_ok=False)
    _write_json(spec_dir / "case_spec_dump.json", dict(case))
    _write_json(spec_dir / "seed_replay_dump.json", {"seed_index": case["seed_index"], "seed_value": case.get("seed_value"), "rng": "PCG64", "substreams": "SeedSequence.spawn"})
    _write_json(spec_dir / "anchor_realization.json", {key: case.get(key) for key in ("anchor_name", "anchor_time_s", "anchor_selection_status")})
    _write_json(spec_dir / "source_role_manifest.json", {"trace": "evaluation_only", "go2": "weak_prior_not_truth", "raw_doppler": "observation_distinct_from_receiver_velocity", "source_quality_metadata": "audit_only_no_current_C++_loader"})
    input_rows = [{"source": key, "sha256": value} for key, value in sorted(base.hashes().items())]
    _write_csv(hash_dir / "input_sha256_manifest.csv", ("source", "sha256"), input_rows)
    storage_entries: list[dict[str, Any]] = []
    for source, filename in OUTPUT_FILENAMES.items():
        table = bundle.tables[source]; destination = provider_dir / filename
        semantic_sha = table.sha256()
        if (case["case_id"] == CLEAN_CASE_ID and source in base.original_provider_paths):
            original = Path(base.original_provider_paths[source]).resolve(strict=True)
            actual_sha = sha256_file(original)
            expected_actual = base.base_provider_hashes[
                {"raw_doppler": "raw_doppler", "go2_rp": "go2_rp", "go2_hv": "go2_hv"}[source]
            ]
            if actual_sha != expected_actual:
                raise ProviderGenerationError(f"C00 original provider hash drift: {source}")
            # 中文说明：C00 必须指向 fresh 原始字节，不能把 CSV 解析后重写成“等价”文件。
            storage_entries.append({"source": source, "relative_path": filename,
                                    "storage_mode": "base_provider_pointer",
                                    "pointer_target": str(original), "semantic_sha256": semantic_sha,
                                    "size_bytes": original.stat().st_size, "sha256": actual_sha})
        elif clean_case_root is not None and semantic_sha == base.tables[source].sha256():
            # /mnt/g 不保证 hardlink；用hash绑定的 C00 source pointer，禁止静默复制。
            storage_entries.append({"source": source, "relative_path": filename,
                                    "storage_mode": "manifest_pointer",
                                    "pointer_case_id": CLEAN_CASE_ID,
                                    "pointer_case_directory": Path(clean_case_root).name,
                                    "pointer_source": source,
                                    "pointer_relative_path": "",
                                    "pointer_target": "",
                                    "size_bytes": None, "sha256": "",
                                    "semantic_sha256": semantic_sha})
        else:
            _write_csv(destination, table.fields, table.rows)
            storage_entries.append({"source": source, "relative_path": filename,
                                    "storage_mode": "materialized",
                                    "pointer_target": "", "semantic_sha256": semantic_sha,
                                    "size_bytes": destination.stat().st_size, "sha256": sha256_file(destination)})
    gnss_path = provider_dir / "combined_gnss_runtime_input_18col.gnss"
    gnss_text = "".join(" ".join(row) + "\n" for row in compose_solver_gnss18(bundle))
    gnss_digest = hashlib.sha256(gnss_text.encode()).hexdigest()
    gnss_tables_clean = all(bundle.tables[name].sha256() == base.tables[name].sha256()
                            for name in ("gnss_position", "receiver_velocity", "dual_yaw"))
    if case["case_id"] == CLEAN_CASE_ID and "combined_gnss" in base.original_provider_paths:
        original = Path(base.original_provider_paths["combined_gnss"]).resolve(strict=True)
        actual_sha = sha256_file(original)
        if actual_sha != base.base_provider_hashes["gnss"] or not gnss_tables_clean:
            raise ProviderGenerationError("C00 original 15-column GNSS identity drift")
        storage_entries.append({"source": "combined_gnss", "relative_path": gnss_path.name,
                                "storage_mode": "base_provider_pointer", "pointer_target": str(original),
                                "semantic_sha256": actual_sha, "runtime_schema_columns": 15,
                                "size_bytes": original.stat().st_size, "sha256": actual_sha})
    elif clean_case_root is not None and gnss_tables_clean:
        storage_entries.append({"source": "combined_gnss", "relative_path": gnss_path.name,
                                "storage_mode": "manifest_pointer", "pointer_case_id": CLEAN_CASE_ID,
                                "pointer_case_directory": Path(clean_case_root).name,
                                "pointer_source": "combined_gnss", "pointer_relative_path": "", "pointer_target": "",
                                "semantic_sha256": base.base_provider_hashes["gnss"], "runtime_schema_columns": 15,
                                "size_bytes": None, "sha256": ""})
    else:
        gnss_path.write_text(gnss_text, encoding="utf-8")
        storage_entries.append({"source": "combined_gnss", "relative_path": gnss_path.name,
                                "storage_mode": "materialized", "pointer_target": "",
                                "semantic_sha256": gnss_digest, "runtime_schema_columns": 18,
                                "size_bytes": gnss_path.stat().st_size, "sha256": gnss_digest})
    index = {
        "case_id": case["case_id"], "provider_files": storage_entries,
        "imu_pointer": str(base.imu_path), "imu_sha256": sha256_file(base.imu_path),
        "raw_source_hashes": dict(base.raw_input_hashes), "trace_used": False,
        "final_v23_output_used": False, "LegSA_output_used": False,
        "raw_mutation": False, "synthetic_data_used": False, "semisynthetic_data_used": False,
    }
    _write_json(provider_dir / "provider_index.json", index)
    _write_json(provider_dir / "provider_generation_log.json", {"components": components, **semantics, "per_case_tuning": False, "metric_used": False})
    perturbation_rows = perturbation_ledger_rows(base, bundle, str(case["degradation_type_id"]))
    _write_deterministic_gzip_csv(
        provider_dir / "CASE_PERTURBATION_LEDGER.csv.gz",
        ("source", "row_index", "base_time", "generated_time", "changed_fields"),
        perturbation_rows,
    )
    # Validation is imported lazily to keep pure handler tests independent.
    from .effect_validation import validate_case_effect
    validation = validate_case_effect(base=base, generated=bundle, case=case, components=components)
    _write_json(validation_dir / "effect_validation_summary.json", validation)
    detail_rows = validation.pop("detail_rows")
    _write_csv(validation_dir / "effect_validation_detail.csv", tuple(detail_rows[0]) if detail_rows else ("check", "passed", "detail"), detail_rows)
    if not validation["passed"]:
        raise ProviderGenerationError(f"effect validation failed: {case['case_id']}")
    (validation_dir / "validation_pass.flag").write_text("PASS\n", encoding="utf-8")
    for table in bundle.tables.values():
        for row in table.rows:
            row.pop(D57_ORIGINAL_ROW_ID, None)
    solver_hashes = {key: bundle.tables[key].sha256() for key in SOLVER_SOURCE_IDS}
    audit_hashes = {key: bundle.tables[key].sha256() for key in AUDIT_ONLY_SOURCE_IDS}
    resolved_runtime_inputs = resolve_provider_index(root)
    actual_runtime_hashes = {
        key: sha256_file(value) for key, value in resolved_runtime_inputs.items()
        if key in ("combined_gnss", "raw_doppler", "go2_rp", "go2_hv")
    }
    # 中文说明：bundle identity 必须绑定 solver 真正打开的 GNSS payload。
    # C00/未改变 GNSS 的 case 使用 fresh 15 列文件，不能错误地声称执行了
    # 仅在内存中组合、但从未打开的 18 列字节。
    content_hashes = {
        **solver_hashes, **audit_hashes,
        "combined_gnss": actual_runtime_hashes["combined_gnss"],
    }
    ready = {"case_id": case["case_id"], "provider_ready": True, "effect_validation_passed": True,
             "provider_bundle_sha256": canonical_provider_bundle_sha256(
                 imu_sha256=index["imu_sha256"], source_hashes=content_hashes),
             "solver_consumed_hashes": solver_hashes,
             "audit_only_hashes": audit_hashes,
             "combined_gnss_semantic_candidate_sha256": gnss_digest,
             "actual_runtime_input_hashes": {
                 "imu": sha256_file(base.imu_path),
                 **actual_runtime_hashes,
             },
             "storage_index_sha256": sha256_file(provider_dir / "provider_index.json")}
    _write_json(ready_dir / "provider_ready_manifest.json", ready)
    (ready_dir / "provider_ready.flag").write_text("PASS\n", encoding="utf-8")
    return ready


def resolve_provider_index(case_root: str | Path) -> dict[str, Path]:
    """Resolve materialized files and C00 pointers with size/hash closure."""

    root = Path(case_root).resolve(strict=True); index_path = root / "02_PROVIDERS/provider_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8")); output: dict[str, Path] = {}
    for row in payload.get("provider_files", ()):
        mode = row.get("storage_mode")
        if mode == "materialized": candidate = root / "02_PROVIDERS" / row["relative_path"]
        elif mode == "manifest_pointer":
            case_id = str(row.get("pointer_case_id", ""))
            case_directory = str(row.get("pointer_case_directory", ""))
            pointer_source = str(row.get("pointer_source", ""))
            if (case_id != CLEAN_CASE_ID or not case_directory or Path(case_directory).name != case_directory or
                    pointer_source not in (*OUTPUT_FILENAMES, "combined_gnss")):
                raise ProviderGenerationError("provider pointer is not the exact C00-relative contract")
            candidate = resolve_provider_index(root.parent / case_directory)[pointer_source]
        elif mode == "base_provider_pointer":
            candidate = Path(str(row.get("pointer_target", "")))
        else: raise ProviderGenerationError("unknown provider storage mode")
        candidate = candidate.resolve(strict=True)
        expected_size = row.get("size_bytes"); expected_sha = str(row.get("sha256", ""))
        if (not candidate.is_file() or
                (expected_size is not None and candidate.stat().st_size != int(expected_size)) or
                (expected_sha and sha256_file(candidate) != expected_sha)):
            raise ProviderGenerationError("provider pointer/materialized hash closure failed")
        semantic_expected = str(row.get("semantic_sha256", ""))
        if not semantic_expected:
            raise ProviderGenerationError("provider index lacks semantic_sha256")
        if str(row["source"]) == "combined_gnss":
            semantic_actual = sha256_file(candidate)
        else:
            fields, rows = _read_csv(candidate)
            semantic_actual = ProviderTable(fields, rows).sha256()
        if semantic_actual != semantic_expected:
            raise ProviderGenerationError("provider semantic hash closure failed")
        output[str(row["source"])] = candidate
    return output


def load_case_bundle(case_root: str | Path, *, base: ProviderBundle) -> ProviderBundle:
    resolved = resolve_provider_index(case_root); tables: dict[str, ProviderTable] = {}
    for source in (*OUTPUT_FILENAMES,):
        fields, rows = _read_csv(resolved[source]); tables[source] = ProviderTable(fields, rows)
    return ProviderBundle(base.imu_path, tables, dict(base.raw_input_hashes),
                          dict(base.base_provider_hashes), copy.deepcopy(base.dual_yaw_audit_rows),
                          dict(base.original_provider_paths))
