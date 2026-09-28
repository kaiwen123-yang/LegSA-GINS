"""Read-only frozen v2.1 NAV gap observations; no reference or fallback NAV."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from ..clean5_imu_parity.providers import frozen_token
from .sequence_paths import alias_path, load_sequence_paths

TABLE_REL = "stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/13_AGGREGATE_SEQUENCES/v3/UNIQUE_EVALUATION_RESULTS.csv"
TABLE_SHA256 = "e26dfcd830d6c711ffbb7debd68293fbf7b7ea28240e16bce582381b61ea6a0b"
RECOVERY_THRESHOLD_MPS = .1


def _sha(path):
    if Path(path).name.startswith("trace_"):
        raise ValueError("Reference hashing is forbidden")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _output_path(row, p):
    """Rebase a frozen metadata path through the current local CLEAN_ROOT."""
    text = row["output_root"]
    if text.startswith("<CLEAN_ROOT>/"):
        relative = Path(text[len("<CLEAN_ROOT>/"):])
    else:
        parts = Path(text).parts
        pair = ("stages", "CLEAN6_SENSOR_MODEL_V21")
        indices = [i for i in range(len(parts)-1) if tuple(parts[i:i+2]) == pair]
        if len(indices) != 1:
            raise ValueError("Frozen NAV output path lacks an unambiguous v2.1 root")
        relative = Path(*parts[indices[0]:])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unconfined frozen output path")
    return p.clean_root / relative


def in_window_gaps(probe, window):
    return [dict(gap) for gap in probe["P2"]["gaps_gt_0p1s"]
            if gap["start_relative_s"] < window[1] and gap["end_relative_s"] >= window[0]]


def diagnose_nav_gaps(nav, gaps, *, window, gravity_mps2):
    """Use actual NAV support only; no interpolation, resampling or synthetic state."""
    nav = np.asarray(nav, float)
    if nav.ndim != 2 or nav.shape[1] != 11 or not len(nav):
        raise ValueError("Frozen NAV must contain eleven columns")
    if not np.isfinite(nav).all() or np.any(np.diff(nav[:,1]) <= 0):
        raise ValueError("Frozen NAV is nonfinite or not strictly chronological")
    nav = nav[(nav[:,1] >= window[0]) & (nav[:,1] <= window[1])]
    result = []
    for index, gap in enumerate(gaps, 1):
        left, right = float(gap["start_relative_s"]), float(gap["end_relative_s"])
        left_token, right_token = float(frozen_token(left,6)), float(frozen_token(right,6))
        row = {"gap_index_in_window":index,"raw_gap_start_s":left,"raw_gap_end_s":right,
               "raw_gap_dt_s":float(gap["duration_s"]), "gravity_reference_mps2":gravity_mps2,
               "left_event_frozen_time_s":left_token,"right_event_frozen_time_s":right_token,
               "raw_gap_g_dt_mps":gravity_mps2*float(gap["duration_s"]),
               "status":"UNAVAILABLE","unavailable_reason":None}
        # Reproduce the documented .12g -> float -> .6f timestamp serialization
        # before exact bracketing; never fit an offset or search a tolerance.
        before = nav[nav[:,1] <= left_token]
        after = nav[nav[:,1] >= right_token]
        if not len(before) or not len(after):
            row["unavailable_reason"] = "NO_PRE_GAP_NAV_IN_WINDOW" if not len(before) else "NO_POST_GAP_NAV_IN_WINDOW"
            result.append(row)
            continue
        a, b = before[-1], after[0]
        retained_dt = float(b[1]-a[1])
        future = after[np.abs(after[:,7]-a[7]) < RECOVERY_THRESHOLD_MPS]
        recovered = future[0] if len(future) else None
        row.update(status="AVAILABLE",nav_before_time_s=float(a[1]),nav_after_time_s=float(b[1]),
                   retained_dt_s=retained_dt,retained_g_dt_mps=gravity_mps2*retained_dt,
                   vn_before_mps=float(a[5]),vn_after_mps=float(b[5]),delta_vn_mps=float(b[5]-a[5]),
                   ve_before_mps=float(a[6]),ve_after_mps=float(b[6]),delta_ve_mps=float(b[6]-a[6]),
                   vd_before_mps=float(a[7]),vd_after_mps=float(b[7]),delta_vd_mps=float(b[7]-a[7]),
                   height_before_m=float(a[4]),height_after_m=float(b[4]),delta_height_m=float(b[4]-a[4]),
                   recovery_status="OBSERVED" if recovered is not None else "NOT_OBSERVED_IN_REMAINING_WINDOW",
                   recovery_time_s=float(recovered[1]) if recovered is not None else None,
                   recovery_after_raw_gap_end_s=float(recovered[1]-right) if recovered is not None else None,
                   recovery_after_first_post_gap_nav_s=float(recovered[1]-b[1]) if recovered is not None else None,
                   recovery_threshold_mps=RECOVERY_THRESHOLD_MPS)
        result.append(row)
    return result


def _write_json(path, result):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write("\n")


def run_legsa_gap_diagnostic(*, stage_root, code_commit):
    """The four exact NAV files are required; absent files make whole items unavailable."""
    control = load_sequence_paths("BY2")
    output = Path(stage_root) / "09_LEGSA_GAP_DIAGNOSTIC"
    if any(path.is_symlink() for path in (output,*output.parents)):
        raise ValueError("Diagnostic output may not follow symlinks")
    output.mkdir(parents=True,exist_ok=False)
    table = control.clean_root / TABLE_REL
    model = control.code_root / "configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml"
    result = {"schema_version":"hext.legsa_gap_diagnostic.v1","data_mode":"frozen_v21_nav_read_only",
              "synthetic_data_used":False,"semisynthetic_data_used":False,"trace_used_online":False,
              "trace_open_count":0,"trace_hash_count":0,"solver_invocation_count":0,"evaluator_invocation_count":0,
              "code_commit":code_commit,"config_hash":_sha(model),"table_path":alias_path(table,control),
              "table_expected_sha256":TABLE_SHA256,"items":[],"fail_soft_errors":[],
              "recovery_definition":"first retained post-gap NAV with abs(VD-VD_before)<0.1 m/s within remaining frozen window",
              "event_time_mapping":"frozen_token(raw relative time,6): .12g -> float -> .6f; exact brackets without time search",
              "reference_only":"g*dt is a comparison scale, not a reconstructed propagation or causal estimate",
              "original_frozen_nav_modified":False,"interpolation_used":False,"fallback_nav_used":False}
    try:
        result["table_sha256"] = _sha(table)
        if result["table_sha256"] != TABLE_SHA256:
            raise ValueError("Frozen v2.1 sequence table hash mismatch")
        with table.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        gravity = float(yaml.safe_load(model.read_text())["g_local_mps2"])
        for sequence in ("BY2H","BY2O"):
            p = load_sequence_paths(sequence)
            probe_path = p.output_root / "01_PROBE" / sequence / "PROBE.json"
            probe = json.loads(probe_path.read_text())
            gaps = in_window_gaps(probe,p.window)
            for method in ("F04","A04"):
                item = {"sequence_id":sequence,"method_id":method,"status":"UNAVAILABLE",
                        "window":list(p.window),"gap_events_in_window":len(gaps),
                        "probe_path":alias_path(probe_path,p),"probe_sha256":_sha(probe_path),"gaps":[]}
                try:
                    matches = [r for r in rows if r["dataset_id"] == sequence and r["method_id"] == method]
                    if len(matches) != 1:
                        raise ValueError("Frozen v2.1 row identity is not unique")
                    source = matches[0]
                    directory = _output_path(source,p)
                    nav_path = directory / "KF_GINS_Navresult.nav"
                    decimated = directory / "NAV_10HZ.csv.gz"
                    item.update(nav_path=alias_path(nav_path,p),expected_native_nav_sha256=source["native_nav_sha256"],
                                run_id=source["run_id"],decimated_nav_path=alias_path(decimated,p),
                                decimated_nav_exists=decimated.is_file(),
                                decimated_nav_role="NOT_USED_DECIMATION_CANNOT_ESTABLISH_NATIVE_GAP_STEP_OR_RECOVERY")
                    if nav_path.is_symlink() or not nav_path.is_file():
                        raise FileNotFoundError("Exact frozen native NAV is absent or symlink; no substitute")
                    item["native_nav_sha256"] = _sha(nav_path)
                    if item["native_nav_sha256"] != source["native_nav_sha256"]:
                        raise ValueError("Frozen native NAV hash mismatch")
                    nav = np.loadtxt(nav_path)
                    item["gaps"] = diagnose_nav_gaps(nav,gaps,window=p.window,gravity_mps2=gravity)
                    item["status"] = "READ_ONLY_DIAGNOSTIC_COMPLETE"
                except (OSError,ValueError,KeyError) as error:
                    item["unavailable_reason"] = str(error)
                    item["gaps"] = [{"gap_index_in_window":i,"raw_gap_start_s":g["start_relative_s"],
                                     "raw_gap_end_s":g["end_relative_s"],"raw_gap_dt_s":g["duration_s"],
                                     "status":"UNAVAILABLE","unavailable_reason":"WHOLE_NATIVE_NAV_ITEM_UNAVAILABLE"}
                                    for i,g in enumerate(gaps,1)]
                result["items"].append(item)
    except (OSError,ValueError,KeyError) as error:
        result["fail_soft_errors"].append(str(error))
    result["status"] = "READ_ONLY_COMPLETE_WITH_EXPLICIT_UNAVAILABLE" if result["fail_soft_errors"] or any(
        i["status"] == "UNAVAILABLE" for i in result["items"]) else "READ_ONLY_DIAGNOSTIC_COMPLETE"
    flat = [{"sequence_id":item["sequence_id"],"method_id":item["method_id"],
             "item_status":item["status"],"nav_path":item.get("nav_path"),
             "native_nav_sha256":item.get("native_nav_sha256"),**gap}
            for item in result["items"] for gap in item["gaps"]]
    fields = list(dict.fromkeys(key for row in flat for key in row)) or ["status","unavailable_reason"]
    with (output / "LEGSA_GAP_DIAGNOSTIC.csv").open("x",newline="") as handle:
        writer = csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(flat)
    _write_json(output / "LEGSA_GAP_DIAGNOSTIC.json",result)
    lines = ["# Frozen v2.1 LegSA gap diagnostic","",result["status"],"",
             "Read-only native NAV observation; no solver/evaluator/reference-trace call, no interpolation or fallback NAV.","",
             "| Sequence | Method | Item status | In-window gaps | Exact native NAV | Reason |",
             "| --- | --- | --- | --- | --- | --- |"]
    for item in result["items"]:
        lines.append("| "+" | ".join(str(item.get(key,"")) for key in
                     ("sequence_id","method_id","status","gap_events_in_window","nav_path","unavailable_reason"))+" |")
    lines += ["",result["recovery_definition"]+".",result["reference_only"]+".",
              "Decimated NAV, where retained, is recorded as existing but is not suitable for native gap-step/recovery evidence."]
    (output / "LEGSA_GAP_DIAGNOSTIC.md").write_text("\n".join(lines)+"\n")
    return result
