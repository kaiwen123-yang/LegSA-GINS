"""Read-only compact handoff from terminal protocol-v2 artifacts.

Structure and metric whitelist follow c541_pack_v2. No metric recomputation,
provider/solver/evaluator calls, raw opens, overwrites or cleanup occur here.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

import pandas as pd

from ..manifest import sha256_file
from .aggregate import AGGREGATE_FILES

IDENT = {"run_id", "run_order", "execution_key", "case_id", "method_id", "matrix",
    "effective_configuration_id", "role", "case_family", "degradation_id", "seed_id",
    "output_root", "evaluation_status", "technical_failure", "algorithm_failure",
    "finite_output", "reference_identity", "protocol_id", "evaluator_version", "evaluator_contract",
    "solver_terminal_status", "dataset_id", "data_mode", "synthetic_data_used", "semisynthetic_data_used",
    "trace_used_online", "controlled_degradation_applied", "uncertainty_status", "v3_std_policy",
    "code_commit", "config_hash", "native_nav_sha256", "eval_nav_sha256", "std_sha256"}
KEEP_COL = re.compile(
    r"^(east|north|up|horizontal|position_3d|attitude_norm|roll|pitch|yaw)_"
    r"(rmse|mae|bias|signed_mean|signed_median|standard_deviation|median|"
    r"median_absolute_error|p50_absolute|p90_absolute|p95_absolute|p99_absolute|"
    r"max_absolute|p50|p90|p95|p99|max|final|final_signed_error|final_absolute_error)"
    r"(_m|_deg|_mps)?$|^(fault_window|post_window|pre_window|during_window)_|^recovery|^time_to"
    r"|coverage|finite|output_epoch|duration|_dt_sec|max_gap|sigma|z_rmse|calibration"
    r"|normalized_squared|_count$|touch_rate|residual_p95|runtime_seconds")
KEEP_BIG = re.compile(
    r"^(east|north|up|horizontal|position_3d|attitude_norm|roll|pitch|yaw)_"
    r"(rmse|bias|signed_mean|standard_deviation|median|p95|p95_absolute|max|max_absolute)"
    r"(_m|_deg|_mps)?$|^(fault_window|post_window|pre_window)_.*(rmse|p95|max)"
    r"|coverage_[123]sigma|calibration_ratio|z_rmse|coverage_ratio|finite_ratio")
REP_TYPES = {"D04", "D12", "D27", "D58", "D60"}
CONFIGS = {"single_antenna_EKF", "basic_dual_yaw_EKF", "AB0000", "AB1011", "AB1111"}
SERIES_COLS = ["time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m",
               "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg"]


def _safe_file(path, root):
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
        raise ValueError("Handoff source must be a regular file inside this stage: " + str(path))
    if any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
        raise ValueError("Symlink source ancestor")
    return path


def _json(path, payload):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _gz_frame(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                frame.to_csv(text, index=False)


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError("Archive duplicate member or CRC failure")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise ValueError("Unsafe archive member")
        manifest = json.loads(archive.read("PACKAGE_MANIFEST.json"))
        if set(names) != set(manifest["members"]) | {"PACKAGE_MANIFEST.json"}:
            raise ValueError("Archive member coverage changed")
        for name, identity in manifest["members"].items():
            content = archive.read(name)
            if len(content) != identity["size_bytes"] or hashlib.sha256(content).hexdigest() != identity["sha256"]:
                raise ValueError("Archive member identity mismatch: " + name)
        probe = json.loads(archive.read("IDENTITY_PROBE.json"))
        if probe.get("passed") is not True:
            raise ValueError("Archive identity probe failed")
        return {"passed": True, "member_count": len(names), "size_bytes": Path(path).stat().st_size,
                "sha256": sha256_file(path), "identity_probe": probe}


def pack(stage, output_zip, *, package_dir=None):
    stage, output_zip = Path(stage).resolve(), Path(output_zip).expanduser().absolute()
    if output_zip.exists() or output_zip.is_symlink():
        raise FileExistsError("Refuse existing handoff ZIP: " + str(output_zip))
    target = Path(package_dir).expanduser().absolute() if package_dir else output_zip.with_suffix("")
    if target.exists() or target.is_symlink() or target == stage or stage in target.parents:
        raise FileExistsError("Handoff workspace must be fresh and outside stage")
    target.mkdir(parents=True, exist_ok=False)
    headers, probes, source_rows, subset_manifest = {}, {}, [], []
    for version in ("v3", "v2"):
        aggregate_root = stage / "13_AGGREGATE" / version
        evaluation_root = stage / "12_OFFLINE_EVALUATION" / version
        terminal = json.loads(_safe_file(aggregate_root / "FINAL_EVALUATION_SUMMARY.json", stage).read_text())
        if terminal.get("aggregate_completed") is not True or terminal.get("unique_evaluated") != 5951 or terminal.get("logical_evaluated") != 7033:
            raise ValueError("Complete matrix aggregate required before handoff")
        if any(not (aggregate_root / name).is_file() for name in AGGREGATE_FILES):
            raise ValueError("Required Canonical aggregate table absent")
        for source in sorted(aggregate_root.iterdir()):
            if source.suffix not in (".csv", ".json"):
                continue
            _safe_file(source, stage)
            rel = Path("13_AGGREGATE") / version / source.name
            if source.suffix == ".csv":
                frame = pd.read_csv(source, dtype=str, keep_default_na=False, low_memory=False)
                before = len(frame)
                if "metric_name" in frame.columns and before > 20000:
                    frame = frame[frame.metric_name.str.contains(KEEP_BIG, regex=True, na=False)]
                headers[rel.as_posix()] = list(frame.columns)
                _gz_frame(frame, target / (rel.as_posix()+".gz"))
                source_rows.append({"source": source.relative_to(stage).as_posix(), "sha256": sha256_file(source),
                                    "rows_full": before, "rows_kept": len(frame), "column_filter": "c541_pack_v2 KEEP_BIG only above 20000 rows"})
            else:
                (target / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target / rel)
        full = {}
        for name in ("UNIQUE_EVALUATION_RESULTS.csv", "LOGICAL_EVALUATION_RESULTS.csv"):
            source = _safe_file(evaluation_root / name, stage)
            frame = pd.read_csv(source, dtype=str, keep_default_na=False, low_memory=False)
            full[name] = frame
            rel = Path("12_OFFLINE_EVALUATION") / version / name
            headers["FULL_"+rel.as_posix()] = list(frame.columns)
            kept = frame[[c for c in frame.columns if c in IDENT or KEEP_COL.search(c)]]
            _gz_frame(kept, target / (rel.as_posix()+".gz"))
            source_rows.append({"source": source.relative_to(stage).as_posix(), "sha256": sha256_file(source),
                                "rows_full": len(frame), "rows_kept": len(kept), "columns_full": len(frame.columns), "columns_kept": len(kept.columns)})
        unique, logical = full["UNIQUE_EVALUATION_RESULTS.csv"], full["LOGICAL_EVALUATION_RESULTS.csv"]
        clean = unique.case_id == "C00_clean_normal"
        case_count = unique.case_id.nunique()
        if len(unique) != 5951 or len(logical) != 7033 or case_count != 541:
            raise ValueError("Handoff table identity counts differ")
        if unique.duplicated(["case_id", "effective_configuration_id"]).any() or unique.effective_configuration_id.nunique() != 11:
            raise ValueError("Handoff duplicate or missing configuration")
        if len(unique[clean]) != 11 or (unique[clean].evaluation_status != "COMPLETED").any():
            raise ValueError("Eleven completed C00 anchors required")
        selected = unique[unique.effective_configuration_id.isin(CONFIGS) & (unique.degradation_id.isin(REP_TYPES) | clean)]
        for row in selected.to_dict("records"):
            item = {"evaluator_version": version, **{k: row[k] for k in ("run_id", "case_id", "degradation_id", "seed_id", "method_id", "effective_configuration_id")}}
            if row["evaluation_status"] != "COMPLETED":
                subset_manifest.append({**item, "status": row["evaluation_status"], "rows_full": 0, "rows_kept": 0})
                continue
            source = _safe_file(row["error_series_source"], stage)
            frame = pd.read_csv(source, usecols=SERIES_COLS)
            # Exact retained samples, no interpolation or metric recomputation.
            decimated = frame.iloc[::20]
            rel = Path("error_series_subset") / version / (row["run_id"]+".csv.gz")
            _gz_frame(decimated, target / rel)
            subset_manifest.append({**item, "status": "OK", "rows_full": len(frame), "rows_kept": len(decimated),
                                    "source_sha256": sha256_file(source), "sample_policy": "every 20th existing row; no interpolation"})
        nav_names = []
        # Both versions share the native NAV; include all eleven C00 configs.
        if version == "v3":
            for row in unique[clean].to_dict("records"):
                source = _safe_file(Path(row["output_root"]) / "NAV_10HZ.csv.gz", stage)
                rel = "C00_NAV_"+row["effective_configuration_id"]+".csv.gz"
                shutil.copyfile(source, target / rel)
                nav_names.append(rel)
        probes[version] = {"unique_rows": len(unique), "logical_rows": len(logical), "cases": int(case_count),
            "configs": sorted(unique.effective_configuration_id.unique().tolist()),
            "degradation_ids": int(unique.degradation_id.nunique()),
            "seeds": sorted(unique.seed_id.unique().tolist()), "families": sorted(unique.case_family.unique().tolist()),
            "eval_status": unique.evaluation_status.value_counts().to_dict(),
            "C00_yaw_rmse_by_config": dict(zip(unique[clean].effective_configuration_id, unique[clean].yaw_rmse_deg)),
            "C00_case_ids": sorted(unique[clean].case_id.unique().tolist()), "nav_files": nav_names}
        for name in ("EVALUATION_STATUS.json", "EVALUATION_FAILURES.csv", "FIELD_DEFINITIONS.md"):
            source = _safe_file(evaluation_root / name, stage)
            destination = target / "12_OFFLINE_EVALUATION" / version / name
            shutil.copyfile(source, destination)
    # Bounded identity/gate and registry copies; no traversal into providers/runs.
    for directory in (stage, stage / "00_PREREGISTRATION", stage / "01_REGISTRY", stage / "07_FULL_ALGORITHM_REGISTRY"):
        if not directory.is_dir():
            continue
        for source in sorted(directory.iterdir()):
            if not source.is_file() or source.suffix not in (".json", ".jsonl", ".csv", ".yaml") or source.stat().st_size > 20_000_000:
                continue
            _safe_file(source, stage)
            rel = Path("found") / "__".join(source.relative_to(stage).parts)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target / rel)
    subset_path = target / "error_series_subset" / "SUBSET_MANIFEST.csv"
    pd.DataFrame(subset_manifest).to_csv(subset_path, index=False)
    _json(target / "HEADERS.json", headers)
    _json(target / "SOURCE_TABLE_ROWS.json", source_rows)
    _json(target / "IDENTITY_PROBE.json", {"passed": True, "versions": probes,
        "series_ok": sum(r["status"] == "OK" for r in subset_manifest),
        "series_algorithm_or_technical_unavailable": sum(r["status"] != "OK" for r in subset_manifest),
        "C00_native_NAV_10Hz_count": 11, "metric_recomputation_performed": False,
        "raw_reference_open_count": 0, "main_manuscript_evaluator": "v3", "parallel_evaluator": "v2"})
    members = {p.relative_to(target).as_posix(): {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
               for p in sorted(target.rglob("*")) if p.is_file()}
    _json(target / "PACKAGE_MANIFEST.json", {"schema_version": "canonical541_handoff_v3", "members": members,
        "aggregation_source": "protocol v2 CAL full matrix", "raw_payload_included": False, "metric_recomputation_performed": False})
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sorted(target.rglob("*")):
            if source.is_file():
                archive.write(source, source.relative_to(target).as_posix())
    result = validate_archive(output_zip)
    _json(output_zip.with_suffix(".validation.json"), result)
    return {**result, "archive": str(output_zip), "package_dir": str(target)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--output", default=str(Path.home() / "c541_v2_handoff.zip"))
    parser.add_argument("--package-dir")
    args = parser.parse_args(argv)
    result = pack(args.stage_root, args.output, package_dir=args.package_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0
