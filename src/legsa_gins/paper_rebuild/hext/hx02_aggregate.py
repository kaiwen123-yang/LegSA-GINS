"""HX-02 aggregation (read-only): five-category long table, results document and checks.

Reads the archived HX-02 runs ($HX02/RUNS), the HX-02 control ledger, the sealed v3
tables (row by row, each cited with its file path, 1-based line number and file
SHA-256), the HX inventory (categories and no-implementation reasons) and the CLEAN4
BY2 records used by the reproduction check. It never opens a reference trajectory and
never starts a solver or an evaluator; LegSA rows are copied from the sealed tables.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import hx02_execution as execution
from . import hx02_heading_tables
from ..horizontal_literature.ginav2021.outputs import read_official_solution, write_standard_nav

CATEGORIES = ("dual_antenna_ambiguity_heading", "loosely_coupled_gnss_ins", "single_antenna_gnss_ins",
              "legged_state_estimation", "other")
TABLE_COLUMNS = ("category", "method_id", "config", "sequence", "start_mode", "output_type", "metric", "value",
                 "denominator_or_valid_epochs", "failure_flag", "source", "notes")
INVENTORY = Path("docs/paper_rebuild/hext/HX_INVENTORY.csv")
V3_REL = "stages/CLEAN8_PROTOCOL_V3"
MAIN_TABLE_REL = V3_REL + "/07_AGGREGATE/MAIN_TABLE_V3.csv"
FULL_ABLATION_REL = V3_REL + "/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv"
START_MODE = {"BY2": "FILE_START", "BY2H": "CONTRACT_START", "BY2O": "FILE_START"}
# MAIN_TABLE_V3.csv line -> (method, sequence, start convention, role); BY2H manuscript rows use CONTRACT_START.
SEALED_EXTERNAL = {
    17: ("LC01", "BY2", "FILE_START", "MANUSCRIPT"), 43: ("LC01", "BY2H", "CONTRACT_START", "MANUSCRIPT"),
    50: ("LC01", "BY2O", "FILE_START", "MANUSCRIPT"),
    40: ("LC01-S", "BY2", "FILE_START", "MANUSCRIPT"), 47: ("LC01-S", "BY2H", "CONTRACT_START", "MANUSCRIPT"),
    52: ("LC01-S", "BY2O", "FILE_START", "MANUSCRIPT"),
    18: ("EXT05C", "BY2", "FILE_START", "MANUSCRIPT"), 45: ("EXT05C", "BY2H", "CONTRACT_START", "MANUSCRIPT"),
    51: ("EXT05C", "BY2O", "FILE_START", "MANUSCRIPT"),
    41: ("EXT05C-S", "BY2", "FILE_START", "MANUSCRIPT"), 49: ("EXT05C-S", "BY2H", "CONTRACT_START", "MANUSCRIPT"),
    53: ("EXT05C-S", "BY2O", "FILE_START", "MANUSCRIPT"),
    42: ("LC01", "BY2H", "FILE_START", "SUPPLEMENT"), 44: ("EXT05C", "BY2H", "FILE_START", "SUPPLEMENT"),
    46: ("LC01-S", "BY2H", "FILE_START", "SUPPLEMENT"), 48: ("EXT05C-S", "BY2H", "FILE_START", "SUPPLEMENT"),
}
SEALED_CATEGORY = {"LC01": "loosely_coupled_gnss_ins", "LC01-S": "loosely_coupled_gnss_ins",
                   "EXT05C": "single_antenna_gnss_ins", "EXT05C-S": "single_antenna_gnss_ins"}
SEALED_CONFIG = {"LC01": "LIT", "LC01-S": "S", "EXT05C": "LIT", "EXT05C-S": "S"}
# FULL_ABLATION_TABLE_V3.csv line -> (LegSA configuration, sequence)
LEGSA_LINES = {27: ("F04", "BY2"), 12: ("F04", "BY2H"), 23: ("F04", "BY2O"),
               25: ("F02", "BY2"), 10: ("F02", "BY2H"), 21: ("F02", "BY2O"),
               24: ("F01", "BY2"), 9: ("F01", "BY2H"), 20: ("F01", "BY2O")}
NO_IMPLEMENTATION = ("EXT05B", "LC01-M", "LC01-S-M", "LC01-2D", "LC02_YIN2023_RAEKF", "LC02_CHANG2021_FSTCKF",
                     "LC02A_JIANG2021_ADAPTIVE_FADING_CKF", "LC02B_TAGHIZADEH2023_AHINF_CKF",
                     "EXT06_HAO2018_TWO_ANTENNA_LC_EKF", "EXT06")
EXCLUDED = ("D01_DIRECT_GEOMETRIC_BASELINE", "D02_SINGLE_RECEIVER_IEKF")
HEADING_METHODS = {  # controller method -> [(heading variant label, table method id)]
    "EXT01": [("EXT01", "EXT01")], "EXT02": [("EXT02", "EXT02")], "EXT03": [("EXT03", "EXT03")],
    "EXT04": [("EXT04_FAR", "EXT04_FAR"), ("EXT04_PAR", "EXT04_PAR")],
    "RTKLIB": [("RTKLIB", "RTKLIB_UNMODIFIED_MOVING_BASE")],
}
TABLE_CONFIG = {"EXT01": "LIT", "EXT02": "LIT", "EXT03": "LIT", "EXT04": "LIT", "RTKLIB": "-", "GINAV": "-",
                "HARTLEY_S": "S", "HARTLEY_LIT": "LIT"}
HARTLEY_ID = {"HARTLEY_S": "Hartley-S", "HARTLEY_LIT": "Hartley-LIT"}
CLEAN4_REL = "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
CLEAN4_FREEZE = {  # method -> (freeze path under CLEAN4, registered freeze SHA-256, hash-map key)
    "EXT01": (execution.NATIVE_FREEZE["EXT01"], "6da2b5a05b9f784d35e288b64398182e77c235605d9aa90375bac9b166106493", "native_hashes"),
    "EXT02": (execution.NATIVE_FREEZE["EXT02"], "c1d8260df693ed213c004ae90f3446e546e88f599b662ec40879711b8b3f060d", "native_output_hashes"),
    "EXT03": (execution.NATIVE_FREEZE["EXT03"], "e172100ad64a2c20ee6772f9b7cb1e212cfb940fde8c3ac94c970b101671b3f0", "native_hashes"),
    "EXT04": (execution.NATIVE_FREEZE["EXT04"], "5f74a0928939c7e630bf8540d1259aeb51c86cf3fc07440fa43503ffc2d2bd46", "native_hashes"),
}
CLEAN4_HARTLEY_NAV = {
    "HARTLEY_S": ("07_LSE01_HARTLEY_CONTACT_INEKF/08_BY2_NATIVE/01_PRIMARY_GO2_ALLAN_EQ61_FK10MM/NAV.csv",
                  "dc4d95a1e634ea7f7c3aecfcb3cdd50ded8ebf4378dfcd46917ed4875338a600", "REGISTERED_CHECK"),
    "HARTLEY_LIT": ("07_LSE01_HARTLEY_CONTACT_INEKF/08_BY2_NATIVE/04_PAPER_PROCESS_REGRESSION/NAV.csv",
                    None, "INFORMATION_ONLY"),
}
GINAV_POS_SHA256 = "39453826453515689416d3d32a8d39290b0fbb35b71525283b692f8fccb788b2"
GINAV_R4C_NAV_SHA256 = "99f3b09ea4f3964df815cfc64b88cdfe7a3460a1fe305cca52e4acd63e666e06"
GINAV_COVERAGE_AWARE_REL = "11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/coverage_aware_c00/GINAV_BY2_C00_STANDARD_NAV.csv"
GINAV_COVERAGE_AWARE_SHA256 = "85902928bac61f4d717c3832d407f94f6d919957ed0f70e89c8fe212c2a2e44f"
GINAV_V3_WINDOW_NAV_SHA256 = "f0fa3e71270cce08ce6174376a694a00a92f725116f8cec86eed4d8062529012"
RTKLIB_CLEAN4_DIAGNOSTIC = "04_EXT03_YANG2024/C00/POST_NATIVE/EXT03_C00_RTKLIB_DIAGNOSTIC.json"
BRIDGE_KNOWN_REASON = ("rtklib_bridge .so rebuilt after the CLEAN4 EXT01 R2 run (current liblegsa_rtklib_bridge.so "
                       "6df66600...); GPU/driver and library versions are not pinned by CLEAN4")


def sha256_file(path: Path) -> str:
    return execution.sha256_file(Path(path))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fmt(value: Any) -> str:
    if value is None:
        return "UNAVAILABLE"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else "NONFINITE"
    return str(value)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _csv_lines(path: Path) -> list[list[str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def _row(**values: Any) -> dict[str, str]:
    missing = [key for key in TABLE_COLUMNS if key not in values]
    if missing:
        raise ValueError(f"table row lacks {missing}")
    return {key: fmt(values[key]) if key == "value" else str(values[key]) for key in TABLE_COLUMNS}


# --------------------------------------------------------------------------- sealed rows
def sealed_rows(clean_root: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """External and LegSA rows copied from the sealed v3 tables (no computation)."""
    rows, citations = [], []
    main = Path(clean_root) / MAIN_TABLE_REL
    main_sha = sha256_file(main)
    lines = _csv_lines(main)
    header = lines[0]
    for line, (method, sequence, start, role) in sorted(SEALED_EXTERNAL.items()):
        record = dict(zip(header, lines[line - 1]))
        if (record["method_id"], record["sequence_id"], record["start_convention"]) != (method, sequence, start):
            raise ValueError(f"sealed MAIN_TABLE_V3 line {line} is not {method}/{sequence}/{start}")
        source = f"<CLEAN_ROOT>/{MAIN_TABLE_REL}:{line} sha256={main_sha}"
        citations.append({"table": MAIN_TABLE_REL, "line": line, "sha256": main_sha, "method_id": method,
                          "sequence": sequence, "start_mode": start, "role": role})
        failure = record["failure_classification"]
        flag = "NONE" if failure == "NONE" else failure
        notes = (f"sealed v3 row; role={role}; evaluation_status={record['evaluation_status']}; "
                 f"geometric_audit_status={record['geometric_audit_status']}")
        common = dict(category=SEALED_CATEGORY[method], method_id=method, config=SEALED_CONFIG[method],
                      sequence=sequence, start_mode=start, output_type="imu_point_nav", failure_flag=flag,
                      source=source, notes=notes)
        if failure != "NONE":
            rows.append(_row(**common, metric="run_status", value=failure,
                             denominator_or_valid_epochs="UNAVAILABLE"))
            continue
        denominator = f"matched={record['matched_epoch_count']}/output={record['output_epoch_count']}"
        for metric, column in (("horizontal_rmse_m", "h_rmse_m"), ("up_rmse_m", "up_rmse_m"),
                               ("yaw_rmse_deg", "yaw_rmse_deg"), ("yaw_p95_absolute_deg", "yaw_p95_absolute_deg"),
                               ("roll_rmse_deg", "roll_rmse_deg"), ("pitch_rmse_deg", "pitch_rmse_deg"),
                               ("coverage_ratio", "coverage_ratio")):
            rows.append(_row(**common, metric=metric, value=float(record[column]),
                             denominator_or_valid_epochs=denominator))
    ablation = Path(clean_root) / FULL_ABLATION_REL
    ablation_sha = sha256_file(ablation)
    lines = _csv_lines(ablation)
    header = lines[0]
    for line, (configuration, sequence) in sorted(LEGSA_LINES.items()):
        record = dict(zip(header, lines[line - 1]))
        if (record["method_id"], record["sequence_id"]) != (configuration, sequence):
            raise ValueError(f"sealed FULL_ABLATION_TABLE_V3 line {line} is not {configuration}/{sequence}")
        source = f"<CLEAN_ROOT>/{FULL_ABLATION_REL}:{line} sha256={ablation_sha}"
        citations.append({"table": FULL_ABLATION_REL, "line": line, "sha256": ablation_sha,
                          "method_id": configuration, "sequence": sequence, "role": "LEGSA_REFERENCE"})
        denominator = f"matched={record['matched_epoch_count']}/output={record['output_epoch_count']}"
        for metric in ("horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "yaw_p95_absolute_deg", "roll_rmse_deg",
                       "pitch_rmse_deg", "coverage_ratio"):
            rows.append(_row(category="legsa_reference_v3_sealed", method_id=f"LegSA_{configuration}", config="-",
                             sequence=sequence, start_mode="V3_PROTOCOL", output_type="imu_point_nav",
                             metric=metric, value=float(record[metric]), denominator_or_valid_epochs=denominator,
                             failure_flag=record["failure_classification"] or "NONE", source=source,
                             notes=f"sealed v3 LegSA row run_id={record['run_id']}; read only, never solved or evaluated"))
    return rows, citations


def inventory_rows() -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with INVENTORY.open(newline="", encoding="utf-8") as handle:
        inventory = {row["method_id"]: row for row in csv.DictReader(handle)}
    rows = []
    for method in NO_IMPLEMENTATION:
        record = inventory[method]
        rows.append(_row(category=record["category"], method_id=method, config="-", sequence="-", start_mode="-",
                         output_type=record["output_type"], metric="status", value="NO_IMPLEMENTATION",
                         denominator_or_valid_epochs="-", failure_flag="NO_IMPLEMENTATION",
                         source=f"{INVENTORY.as_posix()} method_id={method}",
                         notes="无实现：" + record["unavailable_reason_verbatim"]))
    listed = {record["category"] for record in inventory.values()}
    if "other" not in listed:
        rows.append(_row(category="other", method_id="-", config="-", sequence="-", start_mode="-", output_type="-",
                         metric="status", value="NO_METHOD_IN_CATEGORY", denominator_or_valid_epochs="-",
                         failure_flag="NO_IMPLEMENTATION", source=f"{INVENTORY.with_suffix('.md').as_posix()} §2",
                         notes="该类无实现：盘点中没有归入 other 的外部方法（HX_INVENTORY.md §2 与 §3.24）"))
    return rows, inventory


# --------------------------------------------------------------------------- HX-02 runs
def _run(stage: Path, sequence: str, method: str) -> Path:
    return Path(stage) / "RUNS" / execution.run_id(sequence, method)


def _run_state(run: Path) -> dict[str, Any]:
    state: dict[str, Any] = {"archived": (run / "ARCHIVE_MANIFEST.json").is_file(), "run_id": run.name}
    for name in ("DONE.json", "FAILURE.json", "COMMAND.json", "OUTPUT_HASHES.json"):
        if (run / name).is_file():
            state[name] = _json(run / name)
    state["output_hashes_sha256"] = sha256_file(run / "OUTPUT_HASHES.json") if (run / "OUTPUT_HASHES.json").is_file() else None
    return state


def _run_source(run: Path, state: Mapping[str, Any], metrics_path: Path | None) -> str:
    parts = [f"$HX02/RUNS/{run.name}", f"OUTPUT_HASHES.json sha256={state.get('output_hashes_sha256')}"]
    if metrics_path is not None and metrics_path.is_file():
        parts.append(f"{metrics_path.relative_to(run.parent.parent).as_posix()} sha256={sha256_file(metrics_path)}")
    return "; ".join(parts)


def _failure_flag(state: Mapping[str, Any]) -> str | None:
    if "FAILURE.json" in state:
        return str(state["FAILURE.json"].get("failure_classification"))
    if "DONE.json" in state and state["DONE.json"].get("status") not in ("COMPLETED", None):
        return str(state["DONE.json"]["status"])
    return None


def runner_exit_row(category, method_id, config, sequence, output_type, run, state) -> dict[str, str] | None:
    """A complete native output with a non-zero runner exit keeps its metrics plus this flagged row."""
    done = state.get("DONE.json", {})
    if done.get("native_classification") != "COMPLETED_ABNORMAL_EXIT":
        return None
    return _row(category=category, method_id=method_id, config=config, sequence=sequence,
                start_mode=START_MODE[sequence], output_type=output_type, metric="runner_exit_status",
                value=f"exit={done.get('runner_exit_code')}; terminal={done.get('runner_terminal_status')}",
                denominator_or_valid_epochs="-", failure_flag="ABNORMAL_EXIT_WITH_COMPLETE_NATIVE_OUTPUT",
                source=_run_source(run, state, None),
                notes="native output complete and evaluated; the runner exited non-zero (its own validation verdict)")


def _not_run_row(category, method_id, config, sequence, output_type, run, state, stage_state):
    flag = _failure_flag(state)
    if flag is None:
        flag = "NOT_EXECUTED" if not state.get("COMMAND.json") else "INCOMPLETE"
        flag = f"{flag}_{stage_state}" if stage_state else flag
    failure = state.get("FAILURE.json", {})
    notes = "native failure recorded; full stderr in native/NATIVE_stderr.log" if failure else "no archived result"
    if failure.get("gate"):
        notes = "divergence gate " + json.dumps(failure["gate"].get("maxima"), sort_keys=True)
    return _row(category=category, method_id=method_id, config=config, sequence=sequence,
                start_mode=START_MODE[sequence], output_type=output_type, metric="run_status", value=flag,
                denominator_or_valid_epochs="UNAVAILABLE", failure_flag=flag,
                source=_run_source(run, state, None) if run.exists() else f"$HX02/RUNS/{run.name} (absent)",
                notes=notes)


def heading_rows(stage: Path, sequence: str, method: str, stage_state: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    run = _run(stage, sequence, method)
    state = _run_state(run) if run.exists() else {}
    metrics_path = run / "eval" / "HEADING" / "OUTPUT" / "HEADING_METRICS.json"
    rows, info = [], {"run_id": run.name, "state": state}
    config = TABLE_CONFIG[method]
    if not metrics_path.is_file():
        for _label, method_id in HEADING_METHODS[method]:
            rows.append(_not_run_row("dual_antenna_ambiguity_heading", method_id, config, sequence, "heading_only",
                                     run, state, stage_state))
        return rows, info
    metrics = _json(metrics_path)
    diagnostic = _json(run / "eval" / "CONVENTION_DIAGNOSTIC.json")
    info["metrics"] = metrics
    info["convention"] = diagnostic
    source = _run_source(run, state, metrics_path)
    for label, method_id in HEADING_METHODS[method]:
        m = metrics["variants"][label]
        denominator = int(m["denominator_native_paired_epochs_in_window"])
        valid = int(m["valid_epochs_in_window"])
        common = dict(category="dual_antenna_ambiguity_heading", method_id=method_id, config=config,
                      sequence=sequence, start_mode=START_MODE[sequence], output_type="heading_only",
                      failure_flag="NONE", source=source)
        hold = m["hold_last_valid"]
        scored = f"scored={m['valid']['count']}/valid={valid}/denominator={denominator}"
        held = (f"scored={hold['count']}/held={hold['held_epochs_in_window']}/denominator={denominator}")
        items = [
            ("availability", m["availability"], f"{valid}/{denominator}", "method-native valid epochs / native paired epochs in window"),
            ("valid_rmse_deg", m["valid"]["rmse_deg"], scored, "wrap-safe error on valid epochs"),
            ("valid_max_abs_deg", m["valid"]["max_absolute_deg"], scored, ""),
            ("valid_p95_abs_deg", m["valid"]["p95_absolute_deg"], scored, ""),
            ("valid_circular_bias_deg", m["valid"]["circular_bias_deg"], scored, "circular mean of the wrap-safe error"),
            ("hold_rmse_deg", hold["rmse_deg"], held,
             f"hold last valid over the window; no_heading_epochs_before_first_valid={hold['no_heading_epochs_before_first_valid']} (not scored as zero)"),
            ("hold_max_abs_deg", hold["max_absolute_deg"], held, ""),
            ("hold_p95_abs_deg", hold["p95_absolute_deg"], held, ""),
            ("no_heading_epochs_before_first_valid", hold["no_heading_epochs_before_first_valid"], f"of {denominator}", ""),
            ("valid_segment_count", m["valid_segments"]["segment_count"], f"valid={valid}", m["valid_segments"]["definition"]),
            ("valid_max_gap_s", m["valid_segments"]["maximum_gap_seconds"], f"valid={valid}", ""),
        ]
        if "ratio_fixed" in m:
            items += [("ratio_fixed_rate", m["ratio_fixed"]["rate"], f"{m['ratio_fixed']['count']}/{denominator}", "paper ratio test passed"),
                      ("ratio_fixed_rmse_deg", m["ratio_fixed"]["errors"]["rmse_deg"], f"scored={m['ratio_fixed']['errors']['count']}", "")]
        if "q1_fixed" in m:
            items += [("q1_fixed_rate", m["q1_fixed"]["rate"], f"{m['q1_fixed']['count']}/{denominator}", "RTKLIB Q=1 (counted as valid)"),
                      ("q2_float_rate", m["q2_float"]["rate"], f"{m['q2_float']['count']}/{denominator}", "RTKLIB Q=2 reported separately, not valid"),
                      ("q2_float_rmse_deg", m["q2_float"]["errors"]["rmse_deg"], f"scored={m['q2_float']['errors']['count']}", "")]
        convention = diagnostic.get(label, {})
        items.append(("convention_median_deg", convention.get("median_deg"), f"compared={convention.get('compared_epochs')}",
                      "method body yaw minus dual-fixed HPPOSECEF baseline body yaw; fractions="
                      + json.dumps(convention.get("fractions"), sort_keys=True) + f"; status={convention.get('status')}"))
        for metric, value, denominator_text, notes in items:
            rows.append(_row(**common, metric=metric, value=value, denominator_or_valid_epochs=denominator_text,
                             notes=notes))
        flagged = runner_exit_row("dual_antenna_ambiguity_heading", method_id, config, sequence, "heading_only", run, state)
        if flagged:
            rows.append(flagged)
    return rows, info


def ginav_rows(stage: Path, sequence: str, stage_state: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    run = _run(stage, sequence, "GINAV")
    state = _run_state(run) if run.exists() else {}
    path = run / "eval" / "GINAV_EVALUATION.json"
    info: dict[str, Any] = {"run_id": run.name, "state": state}
    if not path.is_file():
        return [_not_run_row("loosely_coupled_gnss_ins", "LC02_GINAV", "-", sequence, "imu_point_nav", run, state,
                             stage_state)], info
    evaluation = _json(path)
    info["evaluation"] = evaluation
    source = _run_source(run, state, path)
    common = dict(category="loosely_coupled_gnss_ins", method_id="LC02_GINAV", config="-", sequence=sequence,
                  start_mode=START_MODE[sequence], output_type="imu_point_nav", source=source)
    rows = []
    coverage = evaluation.get("coverage", {})
    expected = coverage.get("expected_integer_epochs")
    for metric, value, denominator, notes in (
            ("row_coverage", coverage.get("row_coverage_fraction"), f"{coverage.get('valid_rows_in_window')}/{expected}",
             "native output rows inside the window / integer seconds of the closed window"),
            ("temporal_coverage", coverage.get("temporal_coverage_fraction"), f"span={coverage.get('output_span_s')} s",
             "(last - first valid row) / window length"),
            ("max_gap_s", coverage.get("max_gap_s"), f"rows={coverage.get('valid_rows_in_window')}", ""),
            ("segment_count", coverage.get("segment_count"), f"split>{coverage.get('segment_split_s')} s", ""),
            ("first_valid_rel_s", coverage.get("first_valid_rel_s"), f"window_start={(coverage.get('window_seconds') or ['?'])[0]}", "")):
        rows.append(_row(**common, metric=metric, value=value, denominator_or_valid_epochs=denominator,
                         failure_flag="NONE", notes=notes))
    flagged = runner_exit_row("loosely_coupled_gnss_ins", "LC02_GINAV", "-", sequence, "imu_point_nav", run, state)
    if flagged:
        rows.append(flagged)
    status = evaluation.get("evaluation_status")
    if status != "EVALUATED":
        flag = {"NO_OUTPUT_IN_WINDOW": "NO_OUTPUT", "NO_OUTPUT_OFFICIAL_SOLUTION_UNUSABLE": "NO_OUTPUT",
                "NOT_RUN_ALGORITHM_FAILURE": "ALGORITHM_FAILURE_DIVERGED"}.get(status, status)
        detail = evaluation.get("bounded_gate") or {"conversion_error": evaluation.get("conversion_error")}
        rows.append(_row(**common, metric="frozen_evaluation_status", value=status, denominator_or_valid_epochs="UNAVAILABLE",
                         failure_flag=flag, notes=json.dumps(detail, sort_keys=True, default=str)[:600]))
        return rows, info
    for version in ("v3", "v2"):
        row = evaluation.get(version, {})
        prefix = "" if version == "v3" else "v2_"
        if row.get("evaluation_status") != "COMPLETED":
            rows.append(_row(**common, metric=prefix + "frozen_evaluation_status", value=row.get("evaluation_status"),
                             denominator_or_valid_epochs="UNAVAILABLE", failure_flag="UNAVAILABLE_EVALUATION_FAILED_D12",
                             notes=f"evaluator_contract_{version}; D12: {row.get('reason')}; coverage-aware metrics above"))
            continue
        denominator = f"matched={row.get('matched_epoch_count')}/output={row.get('output_epoch_count')}"
        for metric in ("horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "yaw_p95_absolute_deg", "roll_rmse_deg",
                       "pitch_rmse_deg", "coverage_ratio"):
            rows.append(_row(**common, metric=prefix + metric, value=row.get(metric), denominator_or_valid_epochs=denominator,
                             failure_flag="NONE", notes=f"frozen evaluator aa049248, evaluator_contract_{version}"
                             + ("" if version == "v3" else " (IMU point, parallel)")))
    return rows, info


def hartley_rows(stage: Path, sequence: str, stage_state: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    runs = {method: _run(stage, sequence, method) for method in ("HARTLEY_S", "HARTLEY_LIT")}
    states = {method: _run_state(run) if run.exists() else {} for method, run in runs.items()}
    metrics_path = runs["HARTLEY_S"] / "eval" / "RELATIVE_POSE" / "OUTPUT" / "RELATIVE_POSE_METRICS.json"
    metrics = _json(metrics_path) if metrics_path.is_file() else None
    info = {"runs": {m: str(r.name) for m, r in runs.items()}, "metrics": metrics, "states": states}
    rows = []
    for method, run in runs.items():
        state = states[method]
        flag = _failure_flag(state)
        branch = (metrics or {}).get("branches", {}).get(method)
        common = dict(category="legged_state_estimation", method_id=HARTLEY_ID[method], config=TABLE_CONFIG[method],
                      sequence=sequence, start_mode=START_MODE[sequence], output_type="relative_pose")
        if flag or branch is None:
            if flag is None:
                done = state.get("DONE.json", {})
                flag = done.get("evaluation") or ("NOT_EXECUTED" if not state else "UNAVAILABLE")
            gate = run / "eval" / "DIVERGENCE_GATE.json"
            notes = json.dumps(_json(gate).get("maxima"), sort_keys=True) if gate.is_file() else ""
            rows.append(_row(**common, metric="run_status", value=flag, denominator_or_valid_epochs="UNAVAILABLE",
                             failure_flag=flag, source=_run_source(run, state, None) if run.exists() else f"$HX02/RUNS/{run.name} (absent)",
                             notes=("divergence maxima " + notes) if notes else "no relative-pose metrics for this branch"))
            continue
        source = _run_source(runs["HARTLEY_S"], states["HARTLEY_S"], metrics_path) + f"; branch run $HX02/RUNS/{run.name}"
        denominator = f"scored={branch['scored_epochs']}/grid={metrics['grid_epochs']}"
        alignment = metrics["alignment"]
        align_note = (f"one 4-DOF alignment from Hartley-S on [{alignment['window_seconds'][0]}, {alignment['window_seconds'][1]}] s "
                      f"({alignment['epochs']} epochs): yaw {alignment['yaw_offset_deg']:.6f} deg, translation "
                      f"{[round(v, 4) for v in alignment['translation_enu_m']]} m; applied unchanged")
        rpe = branch["relative_pose_error_yaw_translation"]["10s"]
        for metric, value, notes in (
                ("position_drift_m_per_100m", branch["position_drift_m_per_100m"], branch["drift_definitions"]["position"]),
                ("heading_drift_deg_per_min", branch["heading_drift_deg_per_min"], branch["drift_definitions"]["heading"]),
                ("aligned_horizontal_rmse_m", branch["horizontal_rmse_m"], align_note),
                ("aligned_up_rmse_m", branch["up_rmse_m"], ""),
                ("aligned_yaw_rmse_deg", branch["yaw_rmse_deg"], ""),
                ("aligned_horizontal_max_m", branch["horizontal_max_m"], ""),
                ("reference_path_length_m", branch["reference_path_length_m"], "window reference horizontal path"),
                ("rpe_10s_translation_rmse_m", rpe["translation_rmse_m"], f"pairs={rpe['pair_count']}"),
                ("rpe_10s_yaw_rmse_deg", rpe["yaw_rmse_deg"], f"pairs={rpe['pair_count']}")):
            rows.append(_row(**common, metric=metric, value=value, denominator_or_valid_epochs=denominator,
                             failure_flag="NONE", source=source, notes=notes))
    return rows, info


# --------------------------------------------------------------------------- checks
def _freeze_maps(freeze: Mapping[str, Any], key: str) -> dict[str, str]:
    value = freeze.get(key) or freeze.get("provenance", {}).get(key) or {}
    return {k: str(v) for k, v in value.items()}


def reproduction_checks(stage: Path, clean_root: Path, leap_seconds: int = 18) -> list[dict[str, Any]]:
    """BY2 C00: HX-02 native outputs against the registered CLEAN4 identities (record only)."""
    clean4 = Path(clean_root) / CLEAN4_REL
    checks = []
    for method, (freeze_rel, registered, key) in CLEAN4_FREEZE.items():
        run = _run(stage, "BY2", method)
        freeze_path = run / "native" / "ARTIFACT" / freeze_rel
        entry: dict[str, Any] = {"method": method, "registered_clean4_native_freeze_sha256": registered}
        if not freeze_path.is_file():
            entry.update(status="NOT_AVAILABLE_NO_HX02_NATIVE_FREEZE")
            checks.append(entry)
            continue
        observed = sha256_file(freeze_path)
        clean4_freeze = _json(clean4 / freeze_rel)
        ours = _freeze_maps(_json(freeze_path), key)
        theirs = _freeze_maps(clean4_freeze, key)
        files = []
        for name in sorted(set(ours) | set(theirs)):
            files.append({"file_role": name, "clean4_sha256": theirs.get(name), "hx02_sha256": ours.get(name),
                          "identical": ours.get(name) == theirs.get(name)})
        heading_csv = execution.NATIVE_HEADING_CSV[method]
        scope = {}
        for label, rows in hx02_heading_tables.ADAPTERS[method](clean4 / heading_csv, leap_seconds).items():
            with tempfile.TemporaryDirectory() as tmp:
                digest = hx02_heading_tables.write_table(rows, Path(tmp) / "t.csv")
            ours_table = run / "native" / "HX02_HEADING_TABLES" / f"HX02_HEADING_TABLE_{label}.csv"
            scope[label] = {"clean4_declared_scope_table_sha256": digest,
                            "hx02_table_sha256": sha256_file(ours_table) if ours_table.is_file() else None}
            scope[label]["identical"] = scope[label]["clean4_declared_scope_table_sha256"] == scope[label]["hx02_table_sha256"]
        reasons = ["the freeze JSON embeds run paths, the HX-02 sequence spec and the execution commit"]
        if method in ("EXT03", "EXT04"):
            reasons.append("HX-02 runs only the declared scope (EXT03 primary variant; EXT04 GPS_BDS_DUAL_FREQUENCY FAR + "
                           "primary PAR), so whole-file outputs cover fewer rows than CLEAN4")
        if method in ("EXT01", "EXT04"):
            reasons.append(BRIDGE_KNOWN_REASON)
        reasons.append("runtime files record wall-clock timings")
        entry.update(status="REPRODUCED" if observed == registered else "NOT_REPRODUCED",
                     hx02_native_freeze_sha256=observed, per_file=files,
                     declared_scope_heading_tables=scope,
                     method_output_identical_on_declared_scope=all(v["identical"] for v in scope.values()),
                     known_reasons=reasons if observed != registered else [])
        checks.append(entry)
    for method, (rel, registered, role) in CLEAN4_HARTLEY_NAV.items():
        nav = _run(stage, "BY2", method) / "native" / "run" / "NAV.csv"
        reference = registered or (sha256_file(clean4 / rel) if (clean4 / rel).is_file() else None)
        observed = sha256_file(nav) if nav.is_file() else None
        checks.append({"method": method, "role": role, "registered_clean4_nav_sha256": reference,
                       "hx02_nav_sha256": observed,
                       "status": ("NOT_AVAILABLE_NO_HX02_NAV" if observed is None else
                                  "REPRODUCED" if observed == reference else "NOT_REPRODUCED"),
                       "known_reasons": [] if observed == reference else [
                           "runner rebuilt from unchanged sources (the CLEAN4 binary 6cc27e04... no longer exists); "
                           "compiler/library versions are not pinned by CLEAN4"]})
    ginav = _run(stage, "BY2", "GINAV")
    record = ginav / "native" / "GINAV_RUN.json"
    entry = {"method": "GINAV", "registered": {"pos": GINAV_POS_SHA256, "r4c_standard_nav": GINAV_R4C_NAV_SHA256,
                                               "coverage_aware_standard_nav": GINAV_COVERAGE_AWARE_SHA256,
                                               "v3_attempt_window_nav": GINAV_V3_WINDOW_NAV_SHA256}}
    pos = ginav / "native" / "GINAV_RUN" / Path(_json(record)["native_pos"]).name if record.is_file() and _json(record).get("native_pos") else None
    if pos is None or not pos.is_file():
        entry["status"] = "NOT_AVAILABLE_NO_HX02_POS"
    else:
        with tempfile.TemporaryDirectory() as tmp:
            standard = write_standard_nav(Path(tmp) / "std.csv", read_official_solution(pos))
            r4c = sha256_file(standard)
        window = ginav / "native" / "NAV" / "GINAV_WINDOW_NAV11.nav"
        coverage_aware = clean4 / GINAV_COVERAGE_AWARE_REL
        ours_standard = ginav / "native" / "NAV" / "GINAV_STANDARD_NAV.csv"
        value_identical = None
        if coverage_aware.is_file() and ours_standard.is_file():
            with coverage_aware.open(newline="") as a, ours_standard.open(newline="") as b:
                theirs, ours = list(csv.DictReader(a)), list(csv.DictReader(b))
            common = [c for c in (ours[0].keys() if ours else []) if theirs and c in theirs[0]]
            value_identical = len(theirs) == len(ours) and all(
                t[c] == o[c] for t, o in zip(theirs, ours) for c in common)
        observed = {"pos": sha256_file(pos), "r4c_standard_nav": r4c,
                    "v3_attempt_window_nav": sha256_file(window) if window.is_file() else None}
        entry.update(observed=observed,
                     identical={k: observed[k] == entry["registered"][k] for k in observed},
                     coverage_aware_value_identical_on_common_columns=value_identical,
                     note="the coverage-aware file carries an extra status_name column, so it is compared value by value")
        entry["status"] = "REPRODUCED" if all(entry["identical"].values()) and value_identical else "NOT_REPRODUCED"
        if entry["status"] != "REPRODUCED":
            entry["known_reasons"] = ["MATLAB release/driver state on this host may differ from the CLEAN4 r4c run"]
    checks.append(entry)
    rtk = _run(stage, "BY2", "RTKLIB") / "native" / "RTKLIB_UNMODIFIED_MOVING_BASE.pos"
    diagnostic = clean4 / RTKLIB_CLEAN4_DIAGNOSTIC
    if diagnostic.is_file():
        registered = _json(diagnostic).get("output_sha256")
        observed = sha256_file(rtk) if rtk.is_file() else None
        checks.append({"method": "RTKLIB", "role": "INFORMATION_ONLY", "clean4_diagnostic_output_sha256": registered,
                       "hx02_pos_sha256": observed,
                       "status": "NOT_AVAILABLE" if observed is None else "IDENTICAL" if observed == registered else "DIFFERENT",
                       "note": "the CLEAN4 file was produced by the EXT03 post-native diagnostic with the same configuration"})
    return checks


# --------------------------------------------------------------------------- documents
def _manuscript(rows: Iterable[Mapping[str, str]]) -> list[Mapping[str, str]]:
    """Wide tables and conclusions use manuscript rows; BY2H FILE_START sealed rows stay in the long table."""
    return [r for r in rows if "role=SUPPLEMENT" not in r["notes"]]


def _cell(rows: Sequence[Mapping[str, str]], method_id: str, sequence: str, metrics: Sequence[tuple[str, str, int]]) -> str:
    rows = _manuscript(rows)
    selected = {r["metric"]: r for r in rows if r["method_id"] == method_id and r["sequence"] == sequence}
    if not selected:
        if any(r["method_id"] == method_id and r["value"] == "NO_IMPLEMENTATION" for r in rows):
            return "无实现"
        return "—"
    if "run_status" in selected:
        return f"FAILED: {selected['run_status']['value']}"
    if "status" in selected:
        return selected["status"]["value"]
    parts = []
    for metric, label, digits in metrics:
        row = selected.get(metric)
        if row is None:
            continue
        value = row["value"]
        try:
            number = float(value)
            text = f"{100 * number:.1f}% ({row['denominator_or_valid_epochs']})" if metric == "availability" else f"{number:.{digits}f}"
        except ValueError:
            text = value
        parts.append(f"{label} {text}")
    for metric in ("frozen_evaluation_status", "v2_frozen_evaluation_status"):
        if metric in selected:
            parts.append(f"{metric.replace('_', ' ')}: {selected[metric]['value']}")
    return "; ".join(parts) if parts else "—"


def wide_table(rows, methods: Sequence[tuple[str, str]], metrics) -> list[str]:
    lines = ["| method | config | BY2 (C00) | BY2H (CONTRACT_START [413,683]) | BY2O (FILE_START [3186,3563]) |",
             "|---|---|---|---|---|"]
    for method_id, config in methods:
        cells = [_cell(rows, method_id, sequence, metrics) for sequence in ("BY2", "BY2H", "BY2O")]
        lines.append(f"| {method_id} | {config} | " + " | ".join(cells) + " |")
    return lines


def _values(rows, method_id, metric):
    out = {}
    for r in _manuscript(rows):
        if r["method_id"] == method_id and r["metric"] == metric:
            try:
                out[r["sequence"]] = float(r["value"])
            except ValueError:
                pass
    return out


def conclusions(rows: Sequence[Mapping[str, str]]) -> dict[str, str]:
    text = {}
    heading_ids = ["EXT01", "EXT02", "EXT03", "EXT04_FAR", "EXT04_PAR", "RTKLIB_UNMODIFIED_MOVING_BASE"]
    availability = [(v, m, s) for m in heading_ids for s, v in _values(rows, m, "availability").items()]
    rmse = [(v, m, s) for m in heading_ids for s, v in _values(rows, m, "valid_rmse_deg").items()]
    if availability:
        best, worst = max(availability), min(availability)
        sentence = (f"方法自身有效率在 {100 * worst[0]:.1f}%（{worst[1]}，{worst[2]}）到 {100 * best[0]:.1f}%"
                    f"（{best[1]}，{best[2]}）之间")
        if rmse:
            low, high = min(rmse), max(rmse)
            sentence += (f"；有效历元 wrap-safe 航向 RMSE 在 {low[0]:.2f}°（{low[1]}，{low[2]}）到 {high[0]:.2f}°"
                         f"（{high[1]}，{high[2]}）之间")
        text["dual_antenna_ambiguity_heading"] = sentence + "（出处：EXTERNAL_FIVE_CATEGORY_TABLE.csv 对应行的 source 列）。"
    lc = []
    for method in ("LC01", "LC01-S"):
        values = _values(rows, method, "yaw_rmse_deg")
        lc.append(f"{method} yaw RMSE " + "/".join(f"{values[s]:.3f}" for s in ("BY2", "BY2H", "BY2O") if s in values) + "°")
    ginav = [r for r in rows if r["method_id"] == "LC02_GINAV" and r["metric"] in (
        "row_coverage", "yaw_rmse_deg", "horizontal_rmse_m", "run_status", "frozen_evaluation_status")]
    def short(value: str) -> str:
        try:
            return f"{float(value):.4g}"
        except ValueError:
            return value
    ginav_text = "；".join(f"{r['sequence']} {r['metric']}={short(r['value'])}" for r in ginav)
    text["loosely_coupled_gnss_ins"] = ("封存 v3 行（BY2/BY2H CONTRACT_START/BY2O）：" + "，".join(lc)
                                        + f"；GINav 本任务：{ginav_text}（出处：MAIN_TABLE_V3.csv 第 17/43/50、40/47/52 行与本任务运行目录）。")
    single = []
    for method in ("EXT05C", "EXT05C-S"):
        values = _values(rows, method, "yaw_rmse_deg")
        single.append(f"{method} yaw RMSE " + "/".join(f"{values[s]:.3f}" for s in ("BY2", "BY2H", "BY2O") if s in values) + "°")
    text["single_antenna_gnss_ins"] = ("封存 v3 行：" + "，".join(single)
                                       + "；BY2H FILE_START 的 EXT05C-S（第 48 行）为 ALGORITHM_FAILURE_DIVERGED；EXT06 无实现（出处：MAIN_TABLE_V3.csv 第 18/45/51、41/49/53、48 行）。")
    legged = []
    for method in ("Hartley-S", "Hartley-LIT"):
        drift = _values(rows, method, "position_drift_m_per_100m")
        heading = _values(rows, method, "heading_drift_deg_per_min")
        status = {r["sequence"]: r["value"] for r in rows if r["method_id"] == method and r["metric"] == "run_status"}
        parts = []
        for s in ("BY2", "BY2H", "BY2O"):
            if s in drift:
                parts.append(f"{s} {drift[s]:.3f} m/100 m、{heading.get(s, float('nan')):.3f}°/min")
            elif s in status:
                parts.append(f"{s} {status[s]}")
        legged.append(f"{method}：" + "，".join(parts))
    text["legged_state_estimation"] = "；".join(legged) + "（相对位姿口径，出处：本任务 Hartley-S 运行目录 RELATIVE_POSE_METRICS.json）。"
    text["other"] = "该类无外部方法（HX_INVENTORY.md §2）。"
    return text


def results_markdown(rows, checks, info, identity, pins, counters, failures, commits) -> str:
    heading_metrics = [("availability", "avail", 1), ("valid_rmse_deg", "valid RMSE°", 3),
                       ("hold_rmse_deg", "hold RMSE°", 3), ("valid_max_abs_deg", "valid max°", 2)]
    lines = ["# HX-02 五类外部方法三序列结果", "",
             "决策规则：无数值门槛，全部结果如实报告。LegSA 行只从 v3 封存表读取；本任务对 LegSA 的解算/评估调用为 "
             f"{counters.get('legsa_native_calls', 0)}/{counters.get('legsa_evaluator_calls', 0)}。", "",
             f"代码冻结提交：`{commits.get('code_freeze')}`；运行记录的执行提交：`{commits.get('execution_heads')}`。", ""]
    lines += ["## 1. 双天线模糊度航向（heading_only；分母 = 方法原生配对历元在窗内的数目：BY2 1370 / BY2H 1350 / BY2O 1885）", ""]
    lines += wide_table(rows, [("EXT01", "LIT"), ("EXT02", "LIT"), ("EXT03", "LIT"), ("EXT04_FAR", "LIT"),
                               ("EXT04_PAR", "LIT"), ("RTKLIB_UNMODIFIED_MOVING_BASE", "-")], heading_metrics)
    lines += ["", "EXT03 ratio-fixed 率与 RTKLIB Q=2 比例见长表（metric = ratio_fixed_rate / q2_float_rate）。", ""]
    lines += ["## 2. 松组合 GNSS/INS（imu_point_nav）", ""]
    lc_metrics = [("horizontal_rmse_m", "h RMSE m", 4), ("yaw_rmse_deg", "yaw RMSE°", 3),
                  ("v2_horizontal_rmse_m", "v2 h RMSE m", 4), ("v2_yaw_rmse_deg", "v2 yaw RMSE°", 3),
                  ("row_coverage", "row cov", 3), ("temporal_coverage", "span cov", 3), ("max_gap_s", "max gap s", 1)]
    lines += wide_table(rows, [("LC01", "LIT"), ("LC01-S", "S"), ("LC02_GINAV", "-")] +
                        [(m, "-") for m in NO_IMPLEMENTATION if m not in ("EXT06",)], lc_metrics)
    lines += ["", "LC01/LC01-S 为 v3 封存行（BY2H 取 CONTRACT_START；FILE_START 行见长表 notes=SUPPLEMENT）。", ""]
    lines += ["## 3. 单天线 GNSS/INS（imu_point_nav）", ""]
    lines += wide_table(rows, [("EXT05C", "LIT"), ("EXT05C-S", "S"), ("EXT06", "-")], lc_metrics[:2])
    lines += ["", "## 4. 足式状态估计（relative_pose；10 s 窗一次 yaw+平移对齐，Hartley-S 导出、两分支共用）", ""]
    lines += wide_table(rows, [("Hartley-S", "S"), ("Hartley-LIT", "LIT")],
                        [("position_drift_m_per_100m", "drift m/100m", 3), ("heading_drift_deg_per_min", "°/min", 3),
                         ("aligned_horizontal_rmse_m", "h RMSE m", 3), ("aligned_yaw_rmse_deg", "yaw RMSE°", 2)])
    lines += ["", "## 5. 其他", "", "| method | config | BY2 | BY2H | BY2O |", "|---|---|---|---|---|",
              "| — | — | 该类无实现 | 该类无实现 | 该类无实现 |", ""]
    lines += ["## LegSA 参照（v3 封存 FULL_ABLATION_TABLE_V3.csv，只读）", ""]
    lines += wide_table(rows, [("LegSA_F04", "-"), ("LegSA_F02", "-"), ("LegSA_F01", "-")],
                        [("horizontal_rmse_m", "h RMSE m", 4), ("yaw_rmse_deg", "yaw RMSE°", 3)])
    lines += ["", "## 每类结论", ""]
    for category, sentence in conclusions(rows).items():
        lines.append(f"- {category}：{sentence}")
    lines += ["", "## 复现检查（BY2 C00，只记录、不硬停）", "", "| method | status | detail |", "|---|---|---|"]
    for check in checks:
        detail = {k: v for k, v in check.items() if k not in ("method", "status", "per_file")}
        lines.append(f"| {check['method']} | {check.get('status')} | `{json.dumps(detail, sort_keys=True)[:700]}` |")
    lines += ["", "## 约定诊断（方法 body yaw − 双 fixed HPPOSECEF 基线 body yaw）", "",
              "| sequence | variant | compared | median° | within ±20° of 0 / ±90 / 180 | status |", "|---|---|---|---|---|---|"]
    for key, value in sorted(info.get("convention", {}).items()):
        for label, d in value.items():
            fractions = d.get("fractions") or {}
            lines.append(f"| {key} | {label} | {d.get('compared_epochs')} | {fmt(d.get('median_deg'))} | "
                         f"{fmt(fractions.get('within_20_of_0'))} / {fmt(fractions.get('within_20_of_plus_minus_90'))} / "
                         f"{fmt(fractions.get('within_20_of_180'))} | {d.get('status')} |")
    lines += ["", "## 失败清单（带分母）", "", "| run | classification | denominator | note |", "|---|---|---|---|"]
    for item in failures or [{"run": "—", "classification": "无", "denominator": "—", "note": "—"}]:
        lines.append(f"| {item['run']} | {item['classification']} | {item['denominator']} | {item['note']} |")
    lines += ["", "## Outcome", "", "```", json.dumps({
        "native_runs_registered": 24, "native_calls": counters.get("native_calls"),
        "evaluator_calls_reference": counters.get("evaluator_calls"),
        "evaluator_calls_reference_free": counters.get("reference_free_evaluator_calls"),
        "legsa_native_calls": counters.get("legsa_native_calls", 0),
        "legsa_evaluator_calls": counters.get("legsa_evaluator_calls", 0),
        "identity_gate": identity, "method_body_pins": pins,
        "failures": len(failures), "decision_rule": "none; all results reported"}, indent=2, sort_keys=True,
        ensure_ascii=False), "```", ""]
    return "\n".join(lines)


def _stage_state(stage: Path) -> str:
    return "AFTER_HARD_STOP" if (Path(stage) / "99_HARD_STOP").is_dir() else ""


def aggregate(roots: execution.Roots, *, docs_copy: Path | None = Path("docs/paper_rebuild/hext/HX02"),
              code_freeze: str | None = None) -> dict[str, Any]:
    stage = roots.stage
    target = stage / "90_AGGREGATE"
    if target.exists():
        raise execution.HardStop("90_AGGREGATE already exists; never overwritten")
    stage_state = _stage_state(stage)
    rows: list[dict[str, str]] = []
    info: dict[str, Any] = {"heading": {}, "ginav": {}, "hartley": {}, "convention": {}}
    for sequence in execution.SEQUENCES:
        for method in HEADING_METHODS:
            produced, detail = heading_rows(stage, sequence, method, stage_state)
            rows += produced
            info["heading"][f"{sequence}/{method}"] = {k: v for k, v in detail.items() if k != "metrics"}
            if "convention" in detail:
                info["convention"][f"{sequence}/{method}"] = detail["convention"]
    for sequence in execution.SEQUENCES:
        produced, detail = ginav_rows(stage, sequence, stage_state)
        rows += produced
        info["ginav"][sequence] = {k: v for k, v in detail.items() if k != "evaluation"}
    for sequence in execution.SEQUENCES:
        produced, detail = hartley_rows(stage, sequence, stage_state)
        rows += produced
        info["hartley"][sequence] = {k: v for k, v in detail.items() if k != "metrics"}
    sealed, citations = sealed_rows(roots.clean)
    rows += sealed
    missing_rows, _inventory = inventory_rows()
    rows += missing_rows
    categories = {row["category"] for row in rows}
    if not set(CATEGORIES) <= categories:
        raise execution.HardStop(f"categories without rows: {sorted(set(CATEGORIES) - categories)}")
    if any(row["method_id"] in EXCLUDED for row in rows):
        raise execution.HardStop("D01/D02 must not enter the table")
    checks = reproduction_checks(stage, roots.clean)
    state = _json(roots.control / "STATE.json") if (roots.control / "STATE.json").is_file() else {"counters": {}}
    counters = state.get("counters", {})
    failures = []
    for row in rows:
        if row["metric"] in ("run_status", "runner_exit_status", "frozen_evaluation_status",
                             "v2_frozen_evaluation_status") and row["failure_flag"] not in ("NONE",):
            failures.append({"run": f"{row['sequence']}/{row['method_id']}", "classification": row["failure_flag"],
                             "denominator": row["denominator_or_valid_epochs"], "note": row["notes"][:200]})
    for row in rows:
        if row["metric"] == "availability" and row["value"] == "0.0":
            failures.append({"run": f"{row['sequence']}/{row['method_id']}", "classification": "NO_METHOD_VALID_EPOCH",
                             "denominator": row["denominator_or_valid_epochs"], "note": "method-native availability 0"})
    identity = {name: (_json(roots.control / name).get("status") if (roots.control / name).is_file() else "ABSENT")
                for name in ("IDENTITY_GATE_START.json", "IDENTITY_GATE_BEFORE_RESULTS.json")}
    pins = {name: (_json(roots.control / name).get("status") if (roots.control / name).is_file() else "ABSENT")
            for name in ("METHOD_BODY_SHA256_BEFORE.json", "METHOD_BODY_SHA256_AFTER.json")}
    heads = sorted({_json(p).get("code_commit") for p in (stage / "RUNS").glob("*/COMMAND.json")}) if (stage / "RUNS").is_dir() else []
    commits = {"code_freeze": code_freeze, "execution_heads": heads}
    markdown = results_markdown(rows, checks, info, identity, pins, counters, failures, commits)
    target.mkdir(parents=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=TABLE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    outputs = {
        "EXTERNAL_FIVE_CATEGORY_TABLE.csv": buffer.getvalue(),
        "HX02_RESULTS.md": markdown,
        "REPRODUCTION_CHECKS.json": json.dumps(checks, indent=2, sort_keys=True) + "\n",
        "CONVENTION_DIAGNOSTICS.json": json.dumps(info["convention"], indent=2, sort_keys=True) + "\n",
        "SEALED_ROW_CITATIONS.json": json.dumps(citations, indent=2, sort_keys=True) + "\n",
        "FAILURES.json": json.dumps(failures, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        "COUNTERS.json": json.dumps({"counters": counters, "commits": commits, "identity_gate": identity,
                                     "method_body_pins": pins}, indent=2, sort_keys=True) + "\n",
    }
    hashes = {}
    for name, text in outputs.items():
        with (target / name).open("x", encoding="utf-8") as handle:
            handle.write(text)
        hashes[name] = sha256_file(target / name)
    execution.write_json(target / "AGGREGATE_MANIFEST.json", {
        "utc": execution.utc(), "files_sha256": hashes, "row_count": len(rows),
        "data_mode": {"BY2": "real_by2_raw", "BY2H": "real_by2h_raw", "BY2O": "real_by2o_raw"},
        "synthetic_data_used": False, "semisynthetic_data_used": False, "reference_opened": False,
        "solver_or_evaluator_started": False})
    if docs_copy is not None:
        docs_copy = Path(docs_copy)
        docs_copy.mkdir(parents=True, exist_ok=True)
        for name in ("EXTERNAL_FIVE_CATEGORY_TABLE.csv", "HX02_RESULTS.md", "REPRODUCTION_CHECKS.json",
                     "CONVENTION_DIAGNOSTICS.json", "SEALED_ROW_CITATIONS.json", "FAILURES.json", "COUNTERS.json"):
            shutil.copyfile(target / name, docs_copy / name)
            if sha256_file(docs_copy / name) != hashes[name]:
                raise execution.HardStop(f"docs copy differs: {name}")
    return {"rows": len(rows), "files": hashes, "failures": failures, "checks": [
        {k: c.get(k) for k in ("method", "status")} for c in checks]}
