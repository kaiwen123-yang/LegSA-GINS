"""Evaluate sealed P-07 NAVs with the unchanged archive evaluator v2/v3."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import transform_nav, write_transformed_nav, body_frame_bias, _external_evaluate
from ..clean5_parity_p04.evaluation import metrics
from ..clean5_sequence.evaluation_process import evaluate
from ..manifest import sha256_file
from .common import FLAGS, pinned, resolve, read_csv, write_csv, write_json, verify_seal


def metric_row(error_root, nav, identity, window, reference_count):
    errors = canonical._read_error_series(error_root)
    row = metrics(errors, nav, identity, window, reference_count)
    bias = body_frame_bias(errors, nav)
    row.update({"body_" + key: value for key, value in bias.items()})
    return row


def one_evaluation(record, version, contract, reg, stage, code_commit):
    root = stage / "07_EVALUATION" / version / record["family"] / record["run_id"]
    root.mkdir(parents=True, exist_ok=False)
    row = {**FLAGS, **{k: record[k] for k in ("chain", "family", "run_id", "case_id", "method_id", "data_mode")},
           "controlled_degradation_applied": record["controlled_degradation_applied"],
           "code_commit": code_commit, "config_hash": record.get("config_hash"),
           "evaluator_version": version, "evaluator_contract": "evaluator_contract_" + version,
           "source_row": str(root / "EVALUATION_RESULT.json"), "evaluation_status": "UNAVAILABLE_FAILED_SOLVER",
           "provider_hashes": record["provider_hashes"], "raw_source_hashes": record["raw_source_hashes"],
           "native_run_manifest": str(Path(record["output_root"]) / "RUN_MANIFEST.json")}
    if record["terminal_status"] != "COMPLETED":
        write_json(root / "EVALUATION_RESULT.json", row)
        return row
    try:
        source = Path(record["output_root"]) / "KF_GINS_Navresult.nav"
        std = Path(record["output_root"]) / "KF_GINS_STD.txt"
        nav = canonical._read_numeric_table(source).to_numpy(float)
        window = contract["evaluation"]["window"]
        if np.any((nav[:, 1] < window[0]) | (nav[:, 1] > window[1])):
            raise ValueError("Native NAV outside frozen evaluation window")
        target = source
        if version == "v3":
            nav = transform_nav(nav, contract["evaluation"]["v3_baseline_median_m"])
            target = root / "EVAL_NAV_V3.nav"
            write_transformed_nav(source, target, nav)
        spec = contract["evaluation"]
        outcome = evaluate(evaluator=pinned(spec["evaluator"], reg), trace=resolve(spec["trace"]["path"], reg),
                           nav=target, std=std, outdir=root / "FROZEN_EVALUATOR", base_time=spec["base_time"],
                           window=window, trace_sha256=spec["trace"]["sha256"], code_root=reg.code_root,
                           raw_root=reg.raw_root, clean_root=reg.clean_root, instrument=True)
        row.update(evaluator_sha256=spec["evaluator"]["sha256"], native_nav_sha256=sha256_file(source),
                   eval_nav_sha256=sha256_file(target), std_sha256=sha256_file(std),
                   evaluator_audit=outcome["audit"], evaluator_runtime_seconds=outcome["runtime_seconds"],
                   v3_std_policy=spec["v3_std_policy"] if version == "v3" else "ORIGINAL_STD")
        row = metric_row(root / "FROZEN_EVALUATOR", nav, row, window, outcome['capture']['reference_epoch_count'])
    except Exception as error:
        row.update(evaluation_status="FAILED_EVALUATOR", failure_type=type(error).__name__, failure=str(error))
    write_json(root / "EVALUATION_RESULT.json", row)
    return row


def evaluate_all(records, contract, reg, stage, code_commit):
    verify_seal(stage / "04_SEAL/SOLVER_OUTPUT_SEAL.json", stage)
    if len(records) != contract["runtime"]["solver_limit"]:
        raise ValueError("All preregistered solver terminal records required before evaluation")
    results = []
    with ThreadPoolExecutor(max_workers=contract["runtime"]["jobs"]) as pool:
        futures = [pool.submit(one_evaluation, record, version, contract, reg, stage, code_commit)
                   for version in contract["evaluation"]["versions"] for record in records]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            print("EVALUATOR", len(results), "/", len(futures), row["evaluator_version"],
                  row["chain"], row["run_id"], row["evaluation_status"], flush=True)
    results.sort(key=lambda r: (r["evaluator_version"], r["chain"], r["run_id"]))
    write_json(stage / "07_EVALUATION" / "EVALUATION_RECORDS.json", results)
    write_csv(stage / "08_AGGREGATE" / "UNIQUE_EVALUATION_RESULTS.csv", results)
    write_csv(stage / "08_AGGREGATE" / "C00_FULL_ABLATION_ANCHORS.csv",
              [r for r in results if r["case_id"] == "C00_clean_normal"])
    return results


EXTERNAL_ROOT = "<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
EXTERNAL_NAVS = {
    "LC01_EXT05A": {"path": EXTERNAL_ROOT + "/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION/EXT05A_PAVLASEK_TWO_RECEIVER_IEKF/EXACT_EVALUATOR_INPUT.nav",
                    "sha256": "ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695", "status": "AVAILABLE", "hash_basis": "FROZEN_EXT05A_C00_TRACE_EVALUATION_FREEZE"},
    "EXT05C": {"path": EXTERNAL_ROOT + "/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION/EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF/EXACT_EVALUATOR_INPUT.nav",
               "sha256": "915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8", "status": "AVAILABLE_DIAGNOSTIC_DUAL_RX_INITIALIZATION", "hash_basis": "FROZEN_EXT05A_C00_TRACE_EVALUATION_FREEZE"},
    "LC02_GINAV": {"path": EXTERNAL_ROOT + "/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/coverage_aware_c00/GINAV_BY2_C00_STANDARD_NAV.csv",
                   "sha256": "85902928bac61f4d717c3832d407f94f6d919957ed0f70e89c8fe212c2a2e44f", "status": "AVAILABLE_LIMITED_COVERAGE", "hash_basis": "CURRENT_READONLY_RECORD_NO_HISTORICAL_SEAL_PIN_FOUND"}}
UNAVAILABLE_EXTERNALS = {
    "EXT01": "UNAVAILABLE_NO_IMU_POINT_NAV", "EXT02": "UNAVAILABLE_NO_IMU_POINT_NAV",
    "EXT03": "UNAVAILABLE_NO_IMU_POINT_NAV", "EXT04": "UNAVAILABLE_NO_IMU_POINT_NAV_ZERO_ACCEPTED_EPOCHS",
    "Hartley": "UNAVAILABLE_ABSOLUTE_METRICS_UNANCHORED_TRANSLATION_AND_YAW_GAUGE",
    "EXT05B": "UNAVAILABLE_NOT_IMPLEMENTED"}
EXT05B_SOURCE = {'path': EXTERNAL_ROOT + '/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05B_C00_MEKF_NOT_IMPLEMENTED.json',
                'sha256': '6f265c033154bf21e6941bb3f8647ee184936ddfbbfc94bd0994c2556fe7e82d'}
GINAV_COLUMNS = ("gps_week", "relative_time_s", "latitude_deg", "longitude_deg", "height_m",
                 "velocity_north_ned_mps", "velocity_east_ned_mps", "velocity_down_ned_mps",
                 "roll_frd_ned_deg", "pitch_frd_ned_deg", "yaw_frd_ned_deg")


def ginav_nav(frame, window):
    nav = frame.loc[:, list(GINAV_COLUMNS)].to_numpy(float)
    if nav.shape[1] != 11 or not np.isfinite(nav).all() or np.any(np.diff(nav[:, 1]) <= 0):
        raise ValueError("Invalid GINav standard NAV")
    return nav[(nav[:, 1] >= window[0]) & (nav[:, 1] <= window[1])]


def horizontal(contract, reg, stage, results, code_commit):
    """Only postprocessing: three LegSA anchors, every frozen external slot."""
    spec = contract["evaluation"]
    root = stage / "09_HORIZONTAL_V3"
    root.mkdir(parents=True, exist_ok=False)
    registry_path = pinned(contract["horizontal"]["frozen_registry"], reg)
    source_rows = read_csv(registry_path)
    write_json(root / "SOURCE_REGISTRY_ROWS.json", source_rows)
    rows = []
    for chain in ("V2S", "CAL"):
        found = [r for r in results if r["chain"] == chain and r["evaluator_version"] == "v3"
                 and r["method_id"] == "A04" and r["case_id"] == "C00_clean_normal"]
        if len(found) != 1:
            raise ValueError("Missing unique full ablation C00 A04 anchor")
        rows.append({**found[0], "horizontal_method": "LegSA_" + chain,
                     "availability": found[0]["evaluation_status"], "reevaluated_here": False})
    runs = read_csv(pinned(contract["sources"]["unique_run_registry"], reg))
    original = [r for r in runs if r["case_id"] == "C00_clean_normal" and r["method_id"] == "A04"]
    if len(original) != 1:
        raise ValueError("Missing frozen A04 anchor")
    frozen_nav = str(Path(original[0]["output_root"]) / "KF_GINS_Navresult.nav")
    entries = {"LegSA_frozen": {"path": frozen_nav,
               "sha256": "3463c03dbdebe3d21e7e7e8fb50e20a8c9e7eeb5b68a5f4f1c335ca024a33923",
               "status": "AVAILABLE", "hash_basis": "FROZEN_CANONICAL_C00"}, **EXTERNAL_NAVS}
    for name, source in entries.items():
        target_root = root / name
        target_root.mkdir()
        identity = {**FLAGS, "data_mode": "real_clean", "controlled_degradation_applied": False,
                    "horizontal_method": name, "availability": source["status"], "evaluator_version": "v3",
                    "evaluator_contract": "evaluator_contract_v3", "code_commit": code_commit,
                    "source_row": str(target_root / "EVALUATION_RESULT.json"), "source_nav": source["path"],
                    "source_nav_sha256": source["sha256"], "source_hash_basis": source["hash_basis"],
                    "source_registry": contract["horizontal"]["frozen_registry"], "reevaluated_here": True,
                    "solver_invocations": 0, "evaluation_status": "NOT_STARTED"}
        try:
            path = pinned(source, reg)
            if name == "LC02_GINAV":
                nav = ginav_nav(pd.read_csv(path), spec["window"])
                if len(nav) != 77:
                    raise ValueError("Frozen GINav fixed-window coverage changed")
                native = target_root / "GINAV_FIXED_WINDOW_NAV.nav"
                np.savetxt(native, nav, fmt="%.17g")
                nav = canonical._read_numeric_table(native).to_numpy(float)
                identity.update(configured_reference_epoch_count=275, configured_coverage_ratio=77 / 275,
                                coverage_policy="77 native rows / 275 configured 1Hz reference epochs; no extrapolation")
            else:
                native = path
                nav = canonical._read_numeric_table(path).to_numpy(float)
            if np.any((nav[:, 1] < spec["window"][0]) | (nav[:, 1] > spec["window"][1])):
                raise ValueError("Horizontal NAV outside fixed window")
            nav = transform_nav(nav, spec["v3_baseline_median_m"])
            transformed = target_root / "EVAL_NAV_V3.nav"
            write_transformed_nav(native, transformed, nav)
            evaluated = _external_evaluate(evaluator=pinned(spec["evaluator"], reg),
                trace=resolve(spec["trace"]["path"], reg), nav=transformed,
                outdir=target_root / "FROZEN_EVALUATOR", registry=reg,
                settings={"trace_sha256": spec["trace"]["sha256"], "base_time": spec["base_time"]})
            identity.update(evaluator_audit=evaluated["audit"], eval_nav_sha256=sha256_file(transformed))
            identity = metric_row(target_root / "FROZEN_EVALUATOR", nav, identity, spec["window"],
                                  evaluated['capture']['reference_epoch_count'])
        except Exception as error:
            identity.update(evaluation_status="FAILED_EVALUATOR", availability="UNAVAILABLE_EVALUATION_FAILED", failure=str(error))
        write_json(target_root / "EVALUATION_RESULT.json", identity)
        rows.append(identity)
        print("HORIZONTAL", name, identity["evaluation_status"], flush=True)
    for name, status in UNAVAILABLE_EXTERNALS.items():
        if name == 'EXT05B':
            source_path = pinned(EXT05B_SOURCE, reg)
            source_identity = {'source_row': str(source_path), 'source_sha256': EXT05B_SOURCE['sha256']}
        else:
            matches = [(i, r) for i, r in enumerate(source_rows, 2) if r['method_id'] == name]
            if len(matches) != 1:
                raise ValueError('Missing/duplicate final external source row: ' + name)
            source_identity = {'source_row': str(registry_path) + ':' + str(matches[0][0]),
                               'source_sha256': contract['horizontal']['frozen_registry']['sha256'],
                               'frozen_registry_row': matches[0][1]}
        rows.append({**FLAGS, "data_mode": "real_clean", "horizontal_method": name, "availability": status,
                     "evaluation_status": "UNAVAILABLE", "evaluator_version": "v3", "code_commit": code_commit,
                     **source_identity,
                     "source_registry": contract["horizontal"]["frozen_registry"], "solver_invocations": 0,
                     "reevaluated_here": False})
    order = ["LegSA_frozen", "LegSA_V2S", "LegSA_CAL"] + contract["horizontal"]["external_rows"]
    rows.sort(key=lambda r: order.index(r["horizontal_method"]))
    if len(rows) != 12:
        raise ValueError("Horizontal coverage must retain all 12 registered rows")
    write_csv(root / "HORIZONTAL_TABLE_V3.csv", rows)
    write_csv(stage / "08_AGGREGATE" / "HORIZONTAL_TABLE_V3.csv", rows)
    return rows
