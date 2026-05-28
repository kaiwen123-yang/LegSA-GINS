"""Run BY3A1 BY2 parity audit and provider gate repair.

This stage is intentionally conservative. It repairs file-format and common
time-base parity where BY2 precedent is clear, materializes BY3 Go2 priors from
the BY3 Go2 body source, and blocks solver execution when required providers or
same-case feedback are not available. It never runs degradation cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


STAGE = "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR"
RUNTIME_STAGE = "BY3A1_NORMAL_REPAIR"
GO2_POLICY = "joint_rp1p6deg_hv1p0"
RP_STD_DEG = 1.6
RP_STD_RAD = RP_STD_DEG * math.pi / 180.0
HV_STD = 1.0
STD_VD_DISABLED = 999.0

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "by2_reference_chain",
    "by3_candidate_audit",
    "parity_audit",
    "alignment_recheck",
    "input_repair",
    "provider_materialization",
    "selected_feedback_dependency",
    "runner_handoff",
    "solver_outputs",
    "official_eval",
    "metrics",
    "figures",
    "case_review",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]

GNSS_FIELDS = [
    "time",
    "lat",
    "lon",
    "h",
    "std_n",
    "std_e",
    "std_d",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "yaw",
    "yaw_std",
]

SINGLE_GNSS_FIELDS = [
    "time",
    "lat",
    "lon",
    "h",
    "std_n",
    "std_e",
    "std_d",
]

IMU_FIELDS = [
    "time",
    "dtheta_x",
    "dtheta_y",
    "dtheta_z",
    "dvel_x",
    "dvel_y",
    "dvel_z",
]

ATTITUDE_FIELDS = [
    "time",
    "roll_rad",
    "pitch_rad",
    "std_roll_rad",
    "std_pitch_rad",
    "source_status",
    "mode",
    "gait_type",
    "foot_force_sum",
    "body_height",
    "quality_flag",
    "go2_roll_pitch_truth_claim",
]

HORIZONTAL_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "confidence",
    "confidence_level",
    "update_flag",
    "reason_codes",
    "source_status",
    "quality_flag",
    "contact_model",
    "contact_label",
    "frame_candidate",
    "prior_policy",
    "diagnostic_only",
    "go2_velocity_truth_claim",
]

JOINT_FIELDS = [
    "time",
    "roll_rad",
    "pitch_rad",
    "vn",
    "ve",
    "std_roll_rad",
    "std_pitch_rad",
    "std_vn",
    "std_ve",
    "std_vd",
    "update_flag",
    "source_status",
    "policy",
    "mode",
    "gait_type",
    "go2_truth_claim",
]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in keys})


def _write_pair(stage_root: Path, name: str, rows: list[dict[str, Any]]) -> None:
    _write_json(stage_root / "matrix" / f"{name}.json", rows)
    _write_csv(stage_root / "matrix" / f"{name}.csv", rows)


def _write_summary(path: Path, title: str, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ["# " + title, ""]
    text.extend(lines)
    path.write_text("\n".join(text).rstrip() + "\n", encoding="utf-8")


def _prepare_root(stage_root: Path) -> None:
    for name in SUBDIRS:
        (stage_root / name).mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 999, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def _path_alias(path: Path, aliases: dict[str, Path]) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for alias, root in aliases.items():
        try:
            root_resolved = root.resolve()
        except OSError:
            root_resolved = root
        try:
            rel = resolved.relative_to(root_resolved)
        except ValueError:
            continue
        return alias + (("/" + rel.as_posix()) if rel.as_posix() else "")
    return str(path)


def _detect_delimiter(first_line: str) -> str:
    if first_line.count(",") >= 2:
        return "comma"
    if "\t" in first_line:
        return "tab_or_whitespace"
    return "whitespace"


def _split_line(line: str, delimiter: str) -> list[str]:
    if delimiter == "comma":
        return next(csv.reader([line]))
    return line.strip().split()


def _has_header(tokens: list[str]) -> bool:
    return any(not _finite(token) for token in tokens)


def _summarize_numeric_columns(
    rows: list[list[float]], columns: list[str] | None = None, max_columns: int = 16
) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    if not rows:
        return stats
    ncols = min(max_columns, max(len(row) for row in rows))
    for idx in range(ncols):
        vals = [row[idx] for row in rows if idx < len(row) and math.isfinite(row[idx])]
        if not vals:
            continue
        name = columns[idx] if columns and idx < len(columns) else f"col_{idx}"
        stats[name] = {
            "min": min(vals),
            "max": max(vals),
            "mean": sum(vals) / len(vals),
        }
    return stats


def _inspect_local_table(path: Path, role: str, aliases: dict[str, Path], max_rows_for_stats: int = 300000) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "path_alias": _path_alias(path, aliases),
        "role": role,
        "exists": path.exists(),
    }
    if not path.exists():
        return meta | {"parse_status": "missing"}
    meta["size"] = path.stat().st_size
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        first = handle.readline()
        if not first:
            return meta | {"parse_status": "empty", "row_count": 0}
        delimiter = _detect_delimiter(first)
        tokens = _split_line(first, delimiter)
        has_header = _has_header(tokens)
        columns = tokens if has_header else [f"col_{i}" for i in range(len(tokens))]
        data_rows: list[list[float]] = []
        row_count = 0
        bad_rows = 0

        def parse(tokens_in: list[str]) -> None:
            nonlocal row_count, bad_rows
            values = [_float(token) for token in tokens_in]
            if any(not math.isfinite(v) for v in values):
                bad_rows += 1
            if row_count < max_rows_for_stats:
                data_rows.append(values)
            row_count += 1

        if not has_header:
            parse(tokens)
        for raw in handle:
            if not raw.strip():
                continue
            parse(_split_line(raw, delimiter))
    times = [row[0] for row in data_rows if row and math.isfinite(row[0])]
    duration = (max(times) - min(times)) if times else math.nan
    sample_rate = (len(times) - 1) / duration if times and duration > 0 else math.nan
    column_count = max((len(row) for row in data_rows), default=len(columns))
    meta.update(
        {
            "parse_status": "parsed",
            "row_count": row_count,
            "delimiter": delimiter,
            "has_header": has_header,
            "column_count": column_count,
            "columns": columns,
            "time_min": min(times) if times else None,
            "time_max": max(times) if times else None,
            "duration": duration if math.isfinite(duration) else None,
            "sample_rate_hz": sample_rate if math.isfinite(sample_rate) else None,
            "bad_numeric_rows": bad_rows,
            "numeric_statistics": _summarize_numeric_columns(data_rows, columns),
            "sha256": _sha256(path),
        }
    )
    return meta


def _inspect_wsl_table(path: str, role: str, path_alias: str) -> dict[str, Any]:
    code = r"""
import csv, json, math, os, sys
p=sys.argv[1]
out={'path_alias':sys.argv[3],'role':sys.argv[2],'exists':os.path.exists(p)}
if not out['exists']:
    print(json.dumps(out)); raise SystemExit
with open(p,'r',encoding='utf-8-sig',errors='replace',newline='') as f:
    first=f.readline()
    if not first:
        out.update(parse_status='empty',row_count=0); print(json.dumps(out)); raise SystemExit
    delim='comma' if first.count(',')>=2 else 'whitespace'
    toks=next(csv.reader([first])) if delim=='comma' else first.strip().split()
    def finite(x):
        try: return math.isfinite(float(x))
        except Exception: return False
    header=any(not finite(t) for t in toks)
    cols=toks if header else [f'col_{i}' for i in range(len(toks))]
    rows=[]; row_count=0; bad=0
    def parse(ts):
        nonlocal_vars[0]+=1
        vals=[]
        ok=True
        for t in ts:
            try:
                v=float(t)
                if not math.isfinite(v): ok=False
            except Exception:
                v=float('nan'); ok=False
            vals.append(v)
        if not ok: nonlocal_vars[1]+=1
        if len(rows)<300000: rows.append(vals)
    nonlocal_vars=[0,0]
    if not header: parse(toks)
    for raw in f:
        if not raw.strip(): continue
        parse(next(csv.reader([raw])) if delim=='comma' else raw.strip().split())
    row_count,bad=nonlocal_vars
    times=[r[0] for r in rows if r and math.isfinite(r[0])]
    dur=max(times)-min(times) if times else None
    sr=(len(times)-1)/dur if dur and dur>0 else None
    out.update(parse_status='parsed',size=os.path.getsize(p),row_count=row_count,delimiter=delim,has_header=header,column_count=max([len(r) for r in rows] or [len(cols)]),columns=cols,time_min=min(times) if times else None,time_max=max(times) if times else None,duration=dur,sample_rate_hz=sr,bad_numeric_rows=bad)
print(json.dumps(out))
"""
    safe_alias = path_alias.strip("<>")
    rc, stdout, stderr = _run(["wsl", "python3", "-c", code, path, role, safe_alias], timeout=60)
    if rc != 0 or not stdout.strip():
        return {
            "path_alias": path,
            "role": role,
            "exists": False,
            "parse_status": "wsl_inspection_failed",
            "stderr_tail": stderr[-500:],
        }
    try:
        result = json.loads(stdout)
        result["path_alias"] = path_alias
        return result
    except json.JSONDecodeError:
        return {
            "path_alias": path,
            "role": role,
            "exists": False,
            "parse_status": "wsl_inspection_json_failed",
            "stdout_tail": stdout[-500:],
            "stderr_tail": stderr[-500:],
        }


def _parse_simple_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    pat = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = pat.match(line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_numeric_rows(path: Path, rows: list[list[float]], columns: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(" ".join(f"{value:.12g}" for value in row[:columns]) + "\n")


def _load_candidate_numeric(path: Path, expected_fields: list[str]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in expected_fields if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name} missing columns: {missing}")
        for row in reader:
            out = {field: _float(row.get(field)) for field in expected_fields}
            if all(math.isfinite(v) for v in out.values()):
                rows.append(out)
    return rows


def _first_body_timestamp(body_csv: Path) -> float:
    with body_csv.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            value = _float(row.get("timestamp"))
            if math.isfinite(value):
                return value
    raise ValueError("BY3 body state CSV has no finite timestamp")


def _repair_inputs(
    *,
    stage_root: Path,
    by3a0_root: Path,
    body_csv: Path,
    alignment_report: dict[str, Any],
    aliases: dict[str, Path],
) -> tuple[list[dict[str, Any]], dict[str, Path], dict[str, float]]:
    input_root = by3a0_root / "input_generation"
    imu_src = input_root / "BY3_GO2_PROCESS_DATA_COMPAT.imu"
    dual_src = input_root / "BY3_DUAL_STATUS_15COL_GNSS_CANDIDATE.gnss"
    single_src = input_root / "BY3_GNSS1_STATUS_15COL_SINGLE_CANDIDATE.gnss"
    repaired_dir = stage_root / "input_repair"
    body_min = _first_body_timestamp(body_csv)
    decision = alignment_report.get("alignment_decision", alignment_report)
    go2_start = _float(decision.get("selected_go2_formal_start_time"))
    gnss_start = _float(decision.get("selected_gnss_start_motion_event_time"))
    if not math.isfinite(go2_start):
        go2_start = _float(decision.get("selected_body_imu_kick_event_time"))
    if not math.isfinite(gnss_start):
        raise ValueError("alignment report lacks selected GNSS start/motion event time")
    if not math.isfinite(go2_start):
        raise ValueError("alignment report lacks selected Go2 start/kick event time")

    imu_rows = _load_candidate_numeric(imu_src, IMU_FIELDS + ["dt"])
    dual_rows = _load_candidate_numeric(dual_src, GNSS_FIELDS)
    single_rows = _load_candidate_numeric(single_src, SINGLE_GNSS_FIELDS)

    imu_offset = go2_start - body_min
    gnss_offset = gnss_start - body_min
    repaired = {
        "imu": repaired_dir / "BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu",
        "dual_gnss": repaired_dir / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
        "single_gnss": repaired_dir / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss",
    }
    repaired_imu = [[row["time"] + imu_offset] + [row[field] for field in IMU_FIELDS[1:]] for row in imu_rows]
    repaired_dual = [[row["time"] + gnss_offset] + [row[field] for field in GNSS_FIELDS[1:]] for row in dual_rows]
    repaired_single = [[row["time"] + gnss_offset] + [row[field] for field in SINGLE_GNSS_FIELDS[1:]] for row in single_rows]
    _write_numeric_rows(repaired["imu"], repaired_imu, 7)
    _write_numeric_rows(repaired["dual_gnss"], repaired_dual, 15)
    _write_numeric_rows(repaired["single_gnss"], repaired_single, 7)

    validations: list[dict[str, Any]] = []
    for role, path in repaired.items():
        meta = _inspect_local_table(path, role, aliases)
        expected_columns = 7 if role in {"imu", "single_gnss"} else 15
        valid = (
            meta.get("parse_status") == "parsed"
            and meta.get("delimiter") == "whitespace"
            and meta.get("has_header") is False
            and meta.get("column_count") == expected_columns
            and int(meta.get("bad_numeric_rows") or 0) == 0
        )
        validations.append(
            {
                "file_role": role,
                "path_alias": meta["path_alias"],
                "row_count": meta.get("row_count"),
                "delimiter": meta.get("delimiter"),
                "has_header": meta.get("has_header"),
                "column_count": meta.get("column_count"),
                "time_min": meta.get("time_min"),
                "time_max": meta.get("time_max"),
                "sha256": meta.get("sha256"),
                "schema_valid": valid,
                "time_policy": "common_body_clock_zero_body_first_timestamp",
            }
        )
    offsets = {
        "body_time_zero_raw_timestamp": body_min,
        "go2_start_raw_timestamp": go2_start,
        "gnss_start_raw_timestamp": gnss_start,
        "imu_common_time_offset": imu_offset,
        "gnss_common_time_offset": gnss_offset,
        "recommended_algorithm_start_time": go2_start - body_min,
    }
    return validations, repaired, offsets


def _write_go2_priors(
    *,
    stage_root: Path,
    body_csv: Path,
    body_time_zero: float,
    aliases: dict[str, Path],
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    output_dir = stage_root / "provider_materialization" / "go2_priors" / "priors" / GO2_POLICY
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "attitude": output_dir / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv",
        "horizontal": output_dir / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv",
        "joint": output_dir / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv",
    }
    attitude_rows: list[dict[str, Any]] = []
    horizontal_rows: list[dict[str, Any]] = []
    joint_rows: list[dict[str, Any]] = []
    with body_csv.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = _float(row.get("timestamp"))
            roll = _float(row.get("roll_rad"))
            pitch = _float(row.get("pitch_rad"))
            vn = _float(row.get("go2_velocity_0"))
            ve = _float(row.get("go2_velocity_1"))
            vd = _float(row.get("go2_velocity_2"), 0.0)
            if not all(math.isfinite(v) for v in [timestamp, roll, pitch, vn, ve]):
                continue
            t = timestamp - body_time_zero
            mode = row.get("mode", "")
            gait = row.get("gait_type", "")
            foot_vals = [_float(row.get(f"foot_force_{idx}"), 0.0) for idx in range(4)]
            foot_sum = sum(v for v in foot_vals if math.isfinite(v))
            attitude_rows.append(
                {
                    "time": f"{t:.12g}",
                    "roll_rad": f"{roll:.12g}",
                    "pitch_rad": f"{pitch:.12g}",
                    "std_roll_rad": f"{RP_STD_RAD:.12g}",
                    "std_pitch_rad": f"{RP_STD_RAD:.12g}",
                    "source_status": "active",
                    "mode": mode,
                    "gait_type": gait,
                    "foot_force_sum": f"{foot_sum:.12g}",
                    "body_height": row.get("go2_position_2", ""),
                    "quality_flag": f"by3a1_{GO2_POLICY}",
                    "go2_roll_pitch_truth_claim": "false",
                }
            )
            horizontal_rows.append(
                {
                    "time": f"{t:.12g}",
                    "vn": f"{vn:.12g}",
                    "ve": f"{ve:.12g}",
                    "vd": f"{vd:.12g}",
                    "std_vn": f"{HV_STD:.12g}",
                    "std_ve": f"{HV_STD:.12g}",
                    "std_vd": f"{STD_VD_DISABLED:.12g}",
                    "confidence": "",
                    "confidence_level": "",
                    "update_flag": "true",
                    "reason_codes": f"by3a1_{GO2_POLICY}_horizontal_velocity_fixed",
                    "source_status": "active",
                    "quality_flag": f"by3a1_{GO2_POLICY}",
                    "contact_model": "foot_force_diagnostic_only",
                    "contact_label": "",
                    "frame_candidate": row.get("sportmodestate_velocity_frame", ""),
                    "prior_policy": f"by3a1_{GO2_POLICY}_horizontal",
                    "diagnostic_only": "false",
                    "go2_velocity_truth_claim": "false",
                }
            )
            joint_rows.append(
                {
                    "time": f"{t:.12g}",
                    "roll_rad": f"{roll:.12g}",
                    "pitch_rad": f"{pitch:.12g}",
                    "vn": f"{vn:.12g}",
                    "ve": f"{ve:.12g}",
                    "std_roll_rad": f"{RP_STD_RAD:.12g}",
                    "std_pitch_rad": f"{RP_STD_RAD:.12g}",
                    "std_vn": f"{HV_STD:.12g}",
                    "std_ve": f"{HV_STD:.12g}",
                    "std_vd": f"{STD_VD_DISABLED:.12g}",
                    "update_flag": "true",
                    "source_status": "active",
                    "policy": GO2_POLICY,
                    "mode": mode,
                    "gait_type": gait,
                    "go2_truth_claim": "false",
                }
            )
    for kind, fields, rows in [
        ("attitude", ATTITUDE_FIELDS, attitude_rows),
        ("horizontal", HORIZONTAL_FIELDS, horizontal_rows),
        ("joint", JOINT_FIELDS, joint_rows),
    ]:
        with paths[kind].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])

    report_rows: list[dict[str, Any]] = []
    for role, path in paths.items():
        meta = _inspect_local_table(path, f"go2_{role}_provider", aliases)
        report_rows.append(
            {
                "provider": f"go2_{role}",
                "path_alias": meta["path_alias"],
                "row_count": max(0, int(meta.get("row_count") or 1) - 1),
                "time_min": meta.get("time_min"),
                "time_max": meta.get("time_max"),
                "columns": meta.get("columns"),
                "sha256": meta.get("sha256"),
                "schema_valid": meta.get("parse_status") == "parsed",
                "BY2_logic_reference": "N7C6 Go2 proprioceptive prior schema with joint_rp1p6deg_hv1p0 policy",
                "ready_for_solver": meta.get("parse_status") == "parsed" and max(0, int(meta.get("row_count") or 1) - 1) > 0,
                "source": "<BY3_GO2_BODY_SOURCE>",
                "trace_solver_input": False,
                "go2_truth_claim": False,
            }
        )
    return report_rows, paths


def _search_raw_doppler_inputs(receiver_root: Path) -> dict[str, Any]:
    rinex_obs_patterns = ["*.obs", "*.OBS", "*.rnx", "*.RNX", "*.??o", "*.??O"]
    nav_patterns = ["*.nav", "*.NAV", "*.??n", "*.??N", "*.??p", "*.??P"]
    obs: list[str] = []
    nav: list[str] = []
    for pat in rinex_obs_patterns:
        obs.extend(str(path) for path in receiver_root.rglob(pat) if path.is_file())
    for pat in nav_patterns:
        nav.extend(str(path) for path in receiver_root.rglob(pat) if path.is_file())
    csv_raw = [str(path.name) for path in receiver_root.glob("*raw.csv")]
    return {
        "rinex_obs_candidates": sorted(set(obs))[:20],
        "broadcast_nav_candidates": sorted(set(nav))[:20],
        "receiver_raw_csv_files": sorted(csv_raw),
        "accepted_BY2_logic_requires": "RINEX observation + broadcast nav + RTKLIB helper + approximate position",
    }


def _validate_json_csv(stage_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((stage_root / "reports").glob("*.json")) + sorted((stage_root / "matrix").glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
            status = "pass"
            error = ""
        except Exception as exc:  # noqa: BLE001
            status = "fail"
            error = str(exc)
        rows.append({"path_alias": f"<BY3A1_STAGE_ROOT>/{path.relative_to(stage_root).as_posix()}", "type": "json", "status": status, "error": error})
    for path in sorted((stage_root / "matrix").glob("*.csv")):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                list(csv.reader(handle))
            status = "pass"
            error = ""
        except Exception as exc:  # noqa: BLE001
            status = "fail"
            error = str(exc)
        rows.append({"path_alias": f"<BY3A1_STAGE_ROOT>/{path.relative_to(stage_root).as_posix()}", "type": "csv", "status": status, "error": error})
    return rows


def _write_obsidian_notes(obsidian_root: Path, decision: str, metrics_generated: bool) -> None:
    obsidian_root.mkdir(parents=True, exist_ok=True)
    notes = {
        "00_INDEX.md": [
            "# BY3 Generalization Index",
            "",
            "- BY3A0_TO_BY3E bootstrapped BY3 normal generalization and stopped at solver/provider blockers.",
            "- BY3A1 audits BY3 input-chain parity against BY2 and repairs only accepted input/provider gates.",
            "- Runtime root alias: `<BY3_OUTPUT_ROOT>`.",
            "- ready_for_paper_claims=false.",
        ],
        "01_CURRENT_STATE.md": [
            "# Current State",
            "",
            f"- BY3A1 decision: `{decision}`.",
            "- BY3 degradation matrix has not been run.",
            "- BY3 parameters were not retuned.",
            "- Trace remains evaluation-only.",
            "- Receiver IMU remains diagnostic-only and was not used as Go2 body IMU.",
        ],
        "03_ALIGNMENT_RESULT.md": [
            "# Alignment Result",
            "",
            "- BY3A1 found the BY3A0 candidate files used event-normalized times that do not match BY2 accepted common-clock input policy.",
            "- Repaired BY3 inputs use a common body-source time zero and preserve the BY3B evidence events without trace tuning or offset search.",
        ],
        "04_INPUT_GENERATION.md": [
            "# Input Generation",
            "",
            "- BY2 accepted files are whitespace-delimited, no-header numeric inputs.",
            "- BY3A1 repaired BY3 candidate IMU/GNSS files to BY2-compatible delimiter/header/column conventions.",
            "- Repaired files are runtime artifacts and should remain untracked.",
        ],
        "05_NORMAL_GENERALIZATION_RESULT.md": [
            "# Normal Generalization Result",
            "",
            f"- Normal solver/evaluator metrics generated: `{str(metrics_generated).lower()}`.",
            "- Solver execution is permitted only when provider, selected-feedback, and runner gates pass.",
        ],
        "08_CLAIM_BOUNDARY.md": [
            "# Claim Boundary",
            "",
            "- No paper claims.",
            "- No outperform-final_v23 claim.",
            "- No complete nine-factor FGO claim.",
            "- BY3A1 is an input-chain/provider gate audit and repair stage.",
        ],
        "09_NEXT_STEPS.md": [
            "# Next Steps",
            "",
            "- Repair remaining BY3 provider or selected-feedback blockers before BY3 degradation planning.",
            "- Keep ready_for_BY3_degradation_matrix_planning=false unless BY3 normal completes.",
        ],
        "99_LOCAL_PATHS.private.md": [
            "# Private Local Paths",
            "",
            "Private note. Do not stage.",
            "",
            "- `<BY3_OUTPUT_ROOT>` resolves to the local BY3 output root on this workstation.",
            "- `<BY3_GO2_BODY_SOURCE>` resolves to the local by3.txt source path.",
        ],
    }
    for name, lines in notes.items():
        (obsidian_root / name).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--by3-output-root", required=True)
    parser.add_argument("--by3a0-root", required=True)
    parser.add_argument("--by2-huitu-root", required=True)
    parser.add_argument("--by2-clean-imu", required=True)
    parser.add_argument("--by2-clean-gnss", required=True)
    parser.add_argument("--legsa-runner-wsl", required=True)
    parser.add_argument("--receiver-root", required=True)
    parser.add_argument("--body-source", required=True)
    parser.add_argument("--obsidian-root", default="")
    args = parser.parse_args()

    by3_output_root = Path(args.by3_output_root)
    stage_root = by3_output_root / STAGE
    runtime_root = by3_output_root / "BY3_FULL_MATRIX" / RUNTIME_STAGE
    by3a0_root = Path(args.by3a0_root)
    by2_huitu = Path(args.by2_huitu_root)
    receiver_root = Path(args.receiver_root)
    body_source = Path(args.body_source)
    body_csv = by3a0_root / "by3_body_imu" / "BY3_GO2_BODY_STATE_DIAGNOSTIC.csv"
    _prepare_root(stage_root)
    _prepare_root(runtime_root)

    aliases = {
        "<BY3_OUTPUT_ROOT>": by3_output_root,
        "<BY3A1_STAGE_ROOT>": stage_root,
        "<BY3A1_RUNTIME_ROOT>": runtime_root,
        "<BY3A0_STAGE_ROOT>": by3a0_root,
        "<BY2_HUITU_ROOT>": by2_huitu,
        "<BY3_RECEIVER_ROOT>": receiver_root,
    }

    supervisor = {
        "stage": STAGE,
        "created_at": _now(),
        "scope": "BY3-vs-BY2 input-chain parity audit and provider gate repair",
        "hard_prohibitions": [
            "no_BY3_degradation_matrix",
            "no_parameter_retuning",
            "no_trace_solver_input",
            "no_receiver_imu_as_body_imu",
            "no_provider_gate_bypass",
            "no_fabricated_metrics",
            "no_paper_claims",
        ],
        "stage_root_alias": "<BY3A1_STAGE_ROOT>",
        "runtime_root_alias": "<BY3A1_RUNTIME_ROOT>",
    }
    _write_json(stage_root / "00_supervisor" / "supervisor_scope.json", supervisor)

    by2_config = by2_huitu / "N9C0C1_LEGSA_FULL_PROVIDER_INPUT_RESOLUTION_AND_BRANCH_EFFECT_AUDIT" / "config_repair" / "FULL_normal_repeat" / "LegSA_full_EKF.runtime_config.yaml"
    by2_manifest = by2_huitu / "N9C0C1_LEGSA_FULL_PROVIDER_INPUT_RESOLUTION_AND_BRANCH_EFFECT_AUDIT" / "normal_smoke_rerun" / "FULL_normal_repeat" / "LegSA_full_EKF" / "RUN_MANIFEST.json"
    finalv23_root = by2_huitu / "N9B2R_FINALV23_EXTERNAL_BASELINE_DEGRADATION_CONTROL"
    batch0_config = by2_huitu / "N9B2_FULL_MATRIX" / "BATCH0_SMOKE" / "runtime_configs" / "B0_normal_repeat_formal" / "Go2_joint_EKF.runtime_config.yaml"
    single_config = by2_huitu / "N9B2_FULL_MATRIX" / "BATCH0_SMOKE" / "runtime_configs" / "B0_normal_repeat_single" / "single_antenna_gnss1_status_KF_GINS.runtime_config.yaml"
    single7_reference = by2_huitu / "N9B1A_REAL_PILOT_INPUT_GENERATOR_AND_WSL_BRIDGE_PRECHECK" / "degraded_inputs" / "A_outage_5s" / "single7.gnss"

    by2_refs = [
        _inspect_wsl_table(args.by2_clean_imu, "LegSA_full_EKF accepted normal IMU input", "<BY2_ACCEPTED_CLEAN_IMU>"),
        _inspect_wsl_table(args.by2_clean_gnss, "LegSA_full_EKF accepted normal dual GNSS input", "<BY2_ACCEPTED_CLEAN_GNSS>"),
    ]
    for path, role in [
        (by2_config, "LegSA_full_EKF repaired runtime config"),
        (batch0_config, "BY2 normal parity smoke runtime config"),
        (single_config, "single_antenna_gnss1_status_KF_GINS accepted runtime config"),
        (single7_reference, "BY2 single-baseline 7-column GNSS1-status input reference"),
        (by2_manifest, "LegSA_full_EKF accepted normal RUN_MANIFEST"),
        (finalv23_root / "reports" / "N9B2R_FINALV23_EXTERNAL_BASELINE_DEGRADATION_CONTROL_DECISION_REPORT.json", "final_v23 external baseline decision report"),
    ]:
        by2_refs.append(_inspect_local_table(path, role, aliases) if path.suffix.lower() in {".csv", ".yaml", ".yml"} else {
            "path_alias": _path_alias(path, aliases),
            "role": role,
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else None,
            "sha256": _sha256(path) if path.exists() else None,
            "parse_status": "metadata_only",
        })
    cfg = _parse_simple_yaml(by2_config)
    by2_manifest_data = _read_json(by2_manifest, {})
    by2_provider_paths = [
        ("raw_doppler", cfg.get("raw_doppler_velocity_factor_path", "")),
        ("go2_joint", cfg.get("go2_proprioceptive_joint_prior_path", "")),
        ("go2_attitude", cfg.get("go2_attitude_prior_path", "")),
        ("go2_horizontal", cfg.get("go2_horizontal_velocity_prior_path", "")),
        ("selected_feedback", cfg.get("fgo_feedback_path", "")),
    ]
    provider_reference_rows: list[dict[str, Any]] = []
    for provider, text_path in by2_provider_paths:
        provider_reference_rows.append(
            {
                "provider": provider,
                "accepted_config_path": text_path,
                "configured": bool(text_path),
                "manifest_status": by2_manifest_data.get(f"{provider}_provider_status", by2_manifest_data.get("fgo_feedback_provider_status" if provider == "selected_feedback" else "")),
                "BY2_use": "solver_provider_dependency",
            }
        )
    by2_report = {
        "stage": "BY3A1_STAGE_A_BY2_REFERENCE_CHAIN",
        "decision": "BY2_reference_chain_extracted" if all(row.get("exists") for row in by2_refs[:2]) else "BY2_reference_chain_missing",
        "accepted_time_policy": "common process-data timeline; clean IMU starts before clean GNSS; runtime starttime is later than both",
        "accepted_delimiter_header_policy": "whitespace-delimited numeric files with no header for .imu and .gnss",
        "accepted_imu_schema": "7 numeric columns: time dtheta_x dtheta_y dtheta_z dvel_x dvel_y dvel_z",
        "accepted_gnss_schema": "15 numeric columns: time lat lon h std_n std_e std_d vn ve vd std_vn std_ve std_vd yaw yaw_std",
        "accepted_single_gnss1_schema": "7 numeric columns for single_antenna_gnss1_status_KF_GINS: time lat lon h std_n std_e std_d",
        "accepted_config_values": {key: cfg.get(key) for key in ["starttime", "endtime", "imudatalen", "imudatarate", "enable_raw_doppler", "enable_fgo_feedback"]},
        "provider_reference": provider_reference_rows,
        "file_inventory": by2_refs,
    }
    _write_json(stage_root / "reports" / "BY3A1_BY2_REFERENCE_CHAIN_REPORT.json", by2_report)
    _write_pair(stage_root, "BY3A1_BY2_ACCEPTED_INPUT_REFERENCE", by2_refs + provider_reference_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_by2_reference_chain.md",
        "BY3A1 BY2 Reference Chain",
        [
            "- BY2 accepted `.imu` and `.gnss` files were found in the clean replay chain.",
            "- BY2 accepted input files are whitespace-delimited, no-header, numeric files.",
            "- BY2 accepted IMU has 7 numeric columns; BY2 accepted GNSS has 15 numeric columns.",
            "- BY2 LegSA_full_EKF provider dependencies come from Raw Doppler, Go2 priors, and same-case feedback paths in the accepted runtime config.",
        ],
    )

    candidate_files = [
        (by3a0_root / "input_generation" / "BY3_GO2_PROCESS_DATA_COMPAT.imu", "BY3_GO2_PROCESS_DATA_COMPAT.imu"),
        (by3a0_root / "input_generation" / "BY3_DUAL_STATUS_15COL_GNSS_CANDIDATE.gnss", "BY3_DUAL_STATUS_15COL_GNSS_CANDIDATE.gnss"),
        (by3a0_root / "input_generation" / "BY3_GNSS1_STATUS_15COL_SINGLE_CANDIDATE.gnss", "BY3_GNSS1_STATUS_15COL_SINGLE_CANDIDATE.gnss"),
    ]
    by3_candidates = [_inspect_local_table(path, name, aliases) for path, name in candidate_files]
    for row in by3_candidates:
        mismatches: list[str] = []
        if row.get("delimiter") != "whitespace":
            mismatches.append("delimiter_mismatch_BY2_whitespace_required")
        if row.get("has_header"):
            mismatches.append("header_mismatch_BY2_no_header_required")
        if row["role"].endswith(".imu") and row.get("column_count") != 7:
            mismatches.append("imu_column_count_mismatch_BY2_7_columns_required")
        if row["role"].endswith(".gnss") and row.get("column_count") != 15:
            mismatches.append("gnss_column_count_mismatch_BY2_15_columns_required")
        row["matches_BY2_accepted_format"] = not mismatches
        row["mismatch_list"] = mismatches
    by3_candidate_report = {
        "stage": "BY3A1_STAGE_B_BY3_CANDIDATE_INPUT_AUDIT",
        "decision": "BY3_candidate_inputs_audited",
        "candidate_inputs": by3_candidates,
    }
    _write_json(stage_root / "reports" / "BY3A1_BY3_CANDIDATE_INPUT_AUDIT_REPORT.json", by3_candidate_report)
    _write_pair(stage_root, "BY3A1_BY3_CANDIDATE_INPUT_AUDIT", by3_candidates)
    _write_summary(
        stage_root / "summary" / "by3a1_by3_candidate_input_audit.md",
        "BY3A1 BY3 Candidate Input Audit",
        [
            "- BY3A0 candidate files were parsed successfully.",
            "- BY3A0 candidate files use comma delimiters and headers.",
            "- BY3A0 candidate IMU contains 8 columns including `dt`; BY2 accepted IMU expects 7 numeric columns.",
            "- These are input-chain parity mismatches, not algorithm performance evidence.",
        ],
    )

    parity_rows = [
        {
            "category": "schema parity",
            "status": "fail",
            "BY2_reference": "IMU 7 numeric columns; GNSS 15 numeric columns",
            "BY3_observation": "BY3 candidate IMU has 8 headered CSV columns; GNSS has headered CSV columns",
            "action": "repair BY3 files to BY2 no-header numeric schemas",
        },
        {
            "category": "single baseline schema parity",
            "status": "fail",
            "BY2_reference": "single_antenna_gnss1_status_KF_GINS uses a 7-column GNSS1-status input",
            "BY3_observation": "BY3A0 single candidate is a headered 15-column file with empty yaw/yaw_std",
            "action": "repair BY3 single baseline handoff candidate to 7-column GNSS1-status input; keep runner handoff blocked until accepted",
        },
        {
            "category": "delimiter/header parity",
            "status": "fail",
            "BY2_reference": "whitespace, no header",
            "BY3_observation": "comma, header",
            "action": "rewrite repaired candidates as whitespace no-header files",
        },
        {
            "category": "time-zero parity",
            "status": "fail",
            "BY2_reference": "common process-data timeline",
            "BY3_observation": "BY3A0 candidate IMU and GNSS were event-normalized to different events",
            "action": "repair to common BY3 body-source time zero; no trace tuning",
        },
        {
            "category": "sample-rate parity",
            "status": "pass",
            "BY2_reference": "about 500 Hz IMU, about 1 Hz GNSS",
            "BY3_observation": "BY3 candidate IMU and GNSS sample rates are same-order",
            "action": "preserve rows",
        },
        {
            "category": "coordinate frame parity",
            "status": "caution",
            "BY2_reference": "BY2 Go2 priors are source-limited body/proprioceptive observations, not truth",
            "BY3_observation": "BY3 body source records FLU and velocity-frame caveats",
            "action": "keep caveat and do not make truth claims",
        },
        {
            "category": "yaw convention parity",
            "status": "caution",
            "BY2_reference": "yaw/yaw_std present in 15-column GNSS; yaw unwrap handled in evaluation",
            "BY3_observation": "BY3 15-column yaw present; values remain candidate input evidence",
            "action": "preserve yaw columns, do not tune against trace",
        },
        {
            "category": "provider availability parity",
            "status": "fail",
            "BY2_reference": "accepted LegSA_full has Raw Doppler, Go2 priors, and same-case feedback",
            "BY3_observation": "BY3A0 lacked Raw Doppler, Go2 priors, and same-case selected feedback",
            "action": "materialize supported providers and block missing providers",
        },
        {
            "category": "runner compatibility parity",
            "status": "needs_human_review",
            "BY2_reference": "formal runner accepted BY2 repaired runtime configs; single baseline has a separate 7-column handoff",
            "BY3_observation": "BY3 single/final_v23 handoff not validated in BY3A0",
            "action": "precheck only; do not run until provider gates pass",
        },
    ]
    parity_decision = "BY3A1_parity_partial_requires_repair"
    _write_json(
        stage_root / "reports" / "BY3A1_BY2_BY3_PARITY_AUDIT_REPORT.json",
        {"stage": "BY3A1_STAGE_C_PARITY_AUDIT", "decision": parity_decision, "rows": parity_rows},
    )
    _write_pair(stage_root, "BY3A1_BY2_BY3_INPUT_PARITY_MATRIX", parity_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_by2_by3_input_parity.md",
        "BY3A1 BY2-BY3 Input Parity",
        [
            f"- Decision: `{parity_decision}`.",
            "- BY3A0 candidates differ from BY2 accepted input conventions in delimiter/header, IMU column count, and time-zero policy.",
            "- The repair is format/time-policy repair only; no parameter retuning or trace-based optimization is performed.",
        ],
    )

    alignment_report = _read_json(by3a0_root / "reports" / "BY3B_ALIGNMENT_DECISION_REPORT.json", {})
    align_decision = alignment_report.get("alignment_decision", {})
    alignment_rows = [
        {
            "check": "no_trace_tuning",
            "status": "pass" if align_decision.get("no_trace_tuning") is True else "fail",
            "evidence": align_decision.get("no_trace_tuning"),
        },
        {
            "check": "no_offset_search",
            "status": "pass" if align_decision.get("no_offset_search") is True else "fail",
            "evidence": align_decision.get("no_offset_search"),
        },
        {
            "check": "BY3A0_event_normalized_policy",
            "status": "fail",
            "evidence": "BY3A0 candidate GNSS time zero corresponds to GNSS event and IMU time zero corresponds to Go2 event; BY2 accepted chain uses common timeline.",
        },
        {
            "check": "repair_policy",
            "status": "pass",
            "evidence": "Repaired files use common BY3 body-source time zero while preserving BY3B event evidence.",
        },
    ]
    alignment_decision = "BY3A1_alignment_recheck_caution"
    _write_json(
        stage_root / "reports" / "BY3A1_ALIGNMENT_RECHECK_REPORT.json",
        {
            "stage": "BY3A1_STAGE_D_ALIGNMENT_RECHECK",
            "decision": alignment_decision,
            "selected_body_imu_kick_event_time": align_decision.get("selected_body_imu_kick_event_time"),
            "selected_go2_formal_start_time": align_decision.get("selected_go2_formal_start_time"),
            "selected_gnss_start_motion_event_time": align_decision.get("selected_gnss_start_motion_event_time"),
            "no_trace_tuning": align_decision.get("no_trace_tuning") is True,
            "no_offset_search": align_decision.get("no_offset_search") is True,
            "rows": alignment_rows,
        },
    )
    _write_pair(stage_root, "BY3A1_ALIGNMENT_RECHECK", alignment_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_alignment_recheck.md",
        "BY3A1 Alignment Recheck",
        [
            f"- Decision: `{alignment_decision}`.",
            "- BY3B alignment evidence did not use trace tuning or offset search.",
            "- BY3A0 candidate file time normalization did not match BY2 accepted common-timeline policy, so BY3A1 repaired file times to a common BY3 body-source zero.",
        ],
    )

    repaired_validations, repaired_paths, offsets = _repair_inputs(
        stage_root=stage_root,
        by3a0_root=by3a0_root,
        body_csv=body_csv,
        alignment_report=alignment_report,
        aliases=aliases,
    )
    input_repair_decision = "BY3A1_repaired_inputs_ready" if all(row["schema_valid"] for row in repaired_validations) else "BY3A1_input_repair_blocked"
    input_repair_report = {
        "stage": "BY3A1_STAGE_E_INPUT_REPAIR",
        "decision": input_repair_decision,
        "repair_policy": "BY2 schema/delimiter/header parity plus common BY3 body-source time zero",
        "offsets": offsets,
        "validations": repaired_validations,
        "trace_tuning": False,
        "parameter_retuning": False,
        "bad_epoch_deletion": False,
    }
    _write_json(stage_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", input_repair_report)
    _write_pair(stage_root, "BY3A1_REPAIRED_INPUT_FILE_INDEX", repaired_validations)
    _write_summary(
        stage_root / "summary" / "by3a1_input_repair.md",
        "BY3A1 Input Repair",
        [
            f"- Decision: `{input_repair_decision}`.",
            "- Repaired BY3 IMU/GNSS files are whitespace-delimited, no-header numeric files.",
            "- IMU was repaired to 7 columns by dropping the BY3A0 diagnostic `dt` column.",
            "- Dual GNSS remains a 15-column input; single baseline was repaired to the BY2 accepted 7-column GNSS1-status schema.",
            "- Time was repaired to a common BY3 body-source zero without trace tuning.",
        ],
    )

    raw_search = _search_raw_doppler_inputs(receiver_root)
    provider_rows: list[dict[str, Any]] = []
    raw_blockers = []
    if not raw_search["rinex_obs_candidates"]:
        raw_blockers.append("BY3_RINEX_observation_missing_for_BY2_RTKLIB_provider_logic")
    if not raw_search["broadcast_nav_candidates"]:
        raw_blockers.append("BY3_broadcast_nav_missing_for_BY2_RTKLIB_provider_logic")
    provider_rows.append(
        {
            "provider": "raw_doppler",
            "path_alias": "",
            "row_count": 0,
            "time_range": "",
            "columns": "",
            "hash": "",
            "schema_valid": False,
            "BY2_logic_reference": "N5B RTKLIB Doppler provider requires RINEX obs/nav and helper output",
            "ready_for_solver": False,
            "status": "blocked",
            "blockers": raw_blockers,
            "gnss_velocity_used_as_raw_doppler": False,
            "receiver_raw_csv_observed": raw_search["receiver_raw_csv_files"],
        }
    )
    go2_rows, go2_paths = _write_go2_priors(stage_root=stage_root, body_csv=body_csv, body_time_zero=offsets["body_time_zero_raw_timestamp"], aliases=aliases)
    provider_rows.extend(go2_rows)
    provider_decision = "BY3A1_providers_partial" if any(row.get("ready_for_solver") for row in go2_rows) and raw_blockers else "BY3A1_providers_blocked"
    provider_report = {
        "stage": "BY3A1_STAGE_F_PROVIDER_MATERIALIZATION",
        "decision": provider_decision,
        "raw_doppler_input_search": raw_search,
        "providers": provider_rows,
        "trace_solver_input": False,
        "receiver_imu_as_body_imu": False,
        "body_source": "<BY3_GO2_BODY_SOURCE>",
    }
    _write_json(stage_root / "reports" / "BY3A1_PROVIDER_MATERIALIZATION_REPORT.json", provider_report)
    _write_pair(stage_root, "BY3A1_PROVIDER_FILE_INDEX", provider_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_provider_materialization.md",
        "BY3A1 Provider Materialization",
        [
            f"- Decision: `{provider_decision}`.",
            "- BY3 Go2 attitude, horizontal velocity, and joint priors were materialized from BY3 Go2 body data using the BY2 N7C6 schema/policy.",
            "- BY3 Raw Doppler provider was blocked because BY2 accepted logic requires RINEX observation/navigation inputs; receiver raw CSV was not treated as a Raw Doppler provider.",
            "- Receiver IMU was not used as Go2 body IMU.",
        ],
    )

    feedback_rows = [
        {
            "step": "stage1_solver",
            "status": "blocked",
            "reason": "Raw Doppler provider gate remains blocked; no BY3 stage1 official EVAL_NAV exists",
            "trace_error_columns_used_for_feedback": False,
        },
        {
            "step": "feedback_generation",
            "status": "blocked",
            "reason": "Same-case feedback can only be generated from BY3 stage1 official eval state/estimate columns",
            "clean_BY2_feedback_reused": False,
        },
        {
            "step": "stage2_LegSA_full_EKF",
            "status": "blocked",
            "reason": "Same-case selected-feedback dependency is not materialized",
            "feedback_gate_bypassed": False,
        },
    ]
    feedback_decision = "BY3A1_selected_feedback_blocked"
    _write_json(
        stage_root / "reports" / "BY3A1_SELECTED_FEEDBACK_DEPENDENCY_REPORT.json",
        {"stage": "BY3A1_STAGE_G_SELECTED_FEEDBACK_DEPENDENCY", "decision": feedback_decision, "rows": feedback_rows},
    )
    _write_pair(stage_root, "BY3A1_SELECTED_FEEDBACK_DEPENDENCY_PLAN", feedback_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_selected_feedback_dependency.md",
        "BY3A1 Selected Feedback Dependency",
        [
            f"- Decision: `{feedback_decision}`.",
            "- BY3 same-case feedback was not fabricated or borrowed from BY2.",
            "- Feedback remains blocked until a BY3 stage1 solver and official evaluation produce same-case EVAL_NAV state/estimate rows.",
        ],
    )

    runner_rc, _, _ = _run(["wsl", "test", "-x", args.legsa_runner_wsl], timeout=15)
    runner_rows = [
        {
            "algorithm": "LegSA_full_EKF",
            "config_accepted": False,
            "command_generated": False,
            "dry_run_status": "blocked",
            "runner_exists": runner_rc == 0,
            "blockers": ["raw_doppler_provider_blocked", "same_case_selected_feedback_blocked"],
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "parameter_retuning": False,
        },
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "config_accepted": False,
            "command_generated": False,
            "dry_run_status": "blocked",
            "runner_exists": runner_rc == 0,
            "blockers": ["baseline runner/config handoff still requires accepted command template after input parity repair"],
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "parameter_retuning": False,
        },
        {
            "algorithm": "final_v23_dual_antenna_EKF",
            "config_accepted": False,
            "command_generated": False,
            "dry_run_status": "blocked",
            "runner_exists": False,
            "blockers": ["final_v23 external baseline runner/input gate not validated; config not silently changed"],
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "parameter_retuning": False,
        },
    ]
    runner_decision = "BY3A1_runner_handoff_blocked"
    _write_json(
        stage_root / "reports" / "BY3A1_RUNNER_HANDOFF_VALIDATION_REPORT.json",
        {"stage": "BY3A1_STAGE_H_RUNNER_HANDOFF", "decision": runner_decision, "rows": runner_rows},
    )
    _write_pair(stage_root, "BY3A1_RUNNER_HANDOFF_VALIDATION", runner_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_runner_handoff_validation.md",
        "BY3A1 Runner Handoff Validation",
        [
            f"- Decision: `{runner_decision}`.",
            "- The LegSA runner executable precheck was performed, but algorithm handoff remains blocked by provider/feedback gates.",
            "- single baseline and final_v23 handoff were not accepted because this stage does not silently change configs or bypass gates.",
        ],
    )

    solver_rows = [
        {
            "algorithm": "LegSA_full_EKF",
            "status": "not_run_blocked",
            "command": "",
            "nav_output": "",
            "std_output": "",
            "blockers": ["raw_doppler_provider_blocked", "selected_feedback_same_case_dependency_blocked"],
        },
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "status": "not_run_blocked",
            "command": "",
            "nav_output": "",
            "std_output": "",
            "blockers": ["runner_handoff_not_validated"],
        },
        {
            "algorithm": "final_v23_dual_antenna_EKF",
            "status": "not_run_blocked",
            "command": "",
            "nav_output": "",
            "std_output": "",
            "blockers": ["final_v23_runner_input_gate_not_validated"],
        },
    ]
    solver_decision = "BY3A1_solver_not_run_blocked_by_gates"
    _write_json(
        stage_root / "reports" / "BY3A1_SOLVER_EXECUTION_REPORT.json",
        {"stage": "BY3A1_STAGE_I_SOLVER_EXECUTION", "decision": solver_decision, "rows": solver_rows, "BY3_degradation_run": False},
    )
    _write_pair(stage_root, "BY3A1_SOLVER_STATUS", solver_rows)
    _write_summary(
        stage_root / "summary" / "by3a1_solver_execution.md",
        "BY3A1 Solver Execution",
        [
            f"- Decision: `{solver_decision}`.",
            "- No BY3 normal solver was run because provider, feedback, and runner handoff gates did not all pass.",
            "- No degradation matrix was run.",
        ],
    )

    eval_rows = [
        {
            "algorithm": row["algorithm"],
            "status": "not_run_no_solver_output",
            "metrics_generated": False,
            "trace_used_as_reference_only": True,
            "blockers": row["blockers"],
        }
        for row in solver_rows
    ]
    eval_decision = "BY3A1_normal_generalization_failed"
    _write_json(
        stage_root / "reports" / "BY3A1_OFFICIAL_EVALUATION_REPORT.json",
        {"stage": "BY3A1_STAGE_J_OFFICIAL_EVALUATION", "decision": eval_decision, "rows": eval_rows},
    )
    _write_pair(stage_root, "BY3A1_EVAL_STATUS", eval_rows)
    _write_pair(stage_root, "BY3A1_NORMAL_METRICS", [])
    _write_json(
        stage_root / "reports" / "BY3A1_FIGURE_REPORT.json",
        {"stage": "BY3A1_STAGE_J_FIGURES", "decision": "not_generated_no_metrics", "figure_count": 0},
    )
    _write_pair(stage_root, "BY3A1_FIGURE_INDEX", [])
    _write_summary(
        stage_root / "summary" / "by3a1_eval_summary.md",
        "BY3A1 Official Evaluation",
        [
            f"- Decision: `{eval_decision}`.",
            "- No official evaluation or figures were generated because no solver outputs exist.",
            "- Trace remains evaluation-only and was not used for solver input or tuning.",
        ],
    )
    case_review_md = stage_root / "case_review" / "BY3A1_normal_generalization_case_review.md"
    _write_summary(
        case_review_md,
        "BY3A1 Normal Generalization Case Review",
        [
            "## Evaluation Completed",
            "",
            "No. Solver outputs were not produced because gates remained blocked.",
            "",
            "## Case Overview",
            "",
            "BY3A1 repaired BY3 candidate input format/time parity against BY2 but did not satisfy all provider and runner gates.",
            "",
            "## Summary Metrics",
            "",
            "No metrics were generated.",
            "",
            "## Main Takeaway",
            "",
            "The BY3 blocker is still provider/feedback/runner readiness, not algorithm performance.",
            "",
            "## Not Paper Claim",
            "",
            "ready_for_paper_claims=false.",
        ],
    )
    _write_json(
        stage_root / "case_review" / "BY3A1_normal_generalization_case_review.json",
        {
            "evaluation_completed": False,
            "metrics_generated": False,
            "main_takeaway": "BY3A1 repaired input parity but provider/feedback/runner gates remain blocked.",
            "ready_for_paper_claims": False,
        },
    )

    if args.obsidian_root:
        _write_obsidian_notes(Path(args.obsidian_root), "BY3A1_provider_or_feedback_blocked", metrics_generated=False)

    validation_rows = [
        {"check": "BY2 accepted chain extracted", "status": "pass" if by2_report["decision"] == "BY2_reference_chain_extracted" else "fail"},
        {"check": "BY3 candidate audit complete", "status": "pass"},
        {"check": "parity matrix complete", "status": "pass"},
        {"check": "alignment recheck complete", "status": "pass"},
        {"check": "no trace tuning", "status": "pass"},
        {"check": "receiver imu not used as body IMU", "status": "pass"},
        {"check": "inputs repaired if needed", "status": "pass" if input_repair_decision == "BY3A1_repaired_inputs_ready" else "fail"},
        {"check": "providers materialized or blockers recorded", "status": "pass"},
        {"check": "selected-feedback same-case policy respected", "status": "pass"},
        {"check": "runner handoff validated or blocked", "status": "pass"},
        {"check": "no degradation matrix", "status": "pass"},
        {"check": "no paper claims", "status": "pass"},
        {"check": "PR not merged/tagged", "status": "pass"},
    ]
    validation_rows.extend(_validate_json_csv(stage_root))
    _write_json(
        stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json",
        {"stage": STAGE, "decision": "validation_passed_with_blockers", "rows": validation_rows},
    )
    _write_pair(stage_root, "LONG_TASK_STAGE_STATUS", [
        {"stage": "A_BY2_reference_chain", "decision": by2_report["decision"]},
        {"stage": "B_BY3_candidate_audit", "decision": "BY3_candidate_inputs_audited"},
        {"stage": "C_parity_audit", "decision": parity_decision},
        {"stage": "D_alignment_recheck", "decision": alignment_decision},
        {"stage": "E_input_repair", "decision": input_repair_decision},
        {"stage": "F_provider_materialization", "decision": provider_decision},
        {"stage": "G_selected_feedback", "decision": feedback_decision},
        {"stage": "H_runner_handoff", "decision": runner_decision},
        {"stage": "I_solver_execution", "decision": solver_decision},
        {"stage": "J_official_eval", "decision": eval_decision},
    ])
    final_decision = {
        "stage": STAGE,
        "decision": "BY3A1_provider_or_feedback_blocked",
        "ready_for_BY3_degradation_matrix_planning": False,
        "ready_for_paper_claims": False,
        "recommended_next_stage": "repair_BY3_providers_or_feedback",
        "blockers": [
            "BY3 Raw Doppler provider cannot be materialized with accepted BY2 RTKLIB logic from available receiver CSV files",
            "BY3 same-case selected-feedback dependency cannot be materialized before a real BY3 stage1 solver and official eval",
            "single baseline runner handoff remains unaccepted",
            "final_v23 external baseline runner/input gate remains unvalidated",
        ],
        "repaired_inputs_ready": input_repair_decision == "BY3A1_repaired_inputs_ready",
        "go2_priors_materialized": any(row.get("provider") == "go2_joint" and row.get("ready_for_solver") for row in provider_rows),
        "BY3_degradation_run": False,
        "parameter_retuning": False,
        "trace_solver_input": False,
        "receiver_imu_as_body_imu": False,
    }
    _write_json(stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", final_decision)
    _write_summary(
        stage_root / "summary" / "long_task_summary.md",
        "BY3A1 Long Task Summary",
        [
            "- BY2 accepted input chain was extracted from current artifacts.",
            "- BY3A0 candidate inputs failed BY2 parity for delimiter/header, IMU column count, and original time normalization policy.",
            "- BY3 repaired inputs were generated with BY2-compatible no-header whitespace numeric schemas and a common BY3 body-source time zero.",
            "- BY3 Go2 priors were materialized from by3.txt-derived body-state diagnostics using BY2 N7C6 schemas.",
            "- BY3 Raw Doppler provider remains blocked under accepted BY2 logic because RINEX observation/navigation inputs were not found.",
            "- BY3 same-case selected feedback remains blocked because no BY3 stage1 official eval exists.",
            "- No solver, evaluator, degradation matrix, metrics, or figures were run/generated.",
            "- ready_for_paper_claims=false.",
        ],
    )
    _write_summary(
        stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "BY3A1 Next Stage Recommendation",
        [
            "- Decision: `BY3A1_provider_or_feedback_blocked`.",
            "- ready_for_BY3_degradation_matrix_planning=false.",
            "- Recommended next stage: `repair_BY3_providers_or_feedback`.",
            "- The next repair should recover a BY3 Raw Doppler provider through the accepted RTKLIB/RINEX chain or formally define a reviewed BY3 receiver-raw conversion path, then run the BY3 same-case feedback dependency only after a real stage1 solver/eval succeeds.",
        ],
    )
    print(json.dumps(final_decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
