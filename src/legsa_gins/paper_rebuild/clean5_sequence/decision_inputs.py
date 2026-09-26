"""Extract hash-locked C-05 decision inputs without evaluating or selecting a method."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Mapping

RULE_SHA256 = "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce"
RULE_PATH = "docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md"
DECISION_INPUTS_RELATIVE_PATH = "stages/CLEAN5_DECISION/A04_F04_DECISION_INPUTS.json"
_PROFILES = {"F01": "single_antenna_EKF", "F02": "basic_dual_yaw_EKF",
             "F03": "AB0000", "A04": "AB1011", "F04": "AB1111"}
_IDENTITY = ("dataset_id", "method_id", "effective_configuration_id", "segment_id", "metric_name")
_COLUMNS = (*_IDENTITY, "run_id", "case_id", "unit", "rmse", "p95_abs", "count",
            "degradation_window_start_s", "degradation_window_end_s")


class DecisionInputError(ValueError):
    """A frozen input cannot be used without guessing or changing its meaning."""


def _decimal(token: Any, label: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(token, bool) or token is None:
        raise DecisionInputError(f"invalid numeric value: {label}")
    try:
        value = Decimal(str(token))
    except (InvalidOperation, ValueError) as exc:
        raise DecisionInputError(f"invalid numeric value: {label}") from exc
    if not value.is_finite() or (nonnegative and value < 0):
        raise DecisionInputError(f"nonfinite or negative value: {label}")
    converted = float(value)
    if not math.isfinite(converted) or (converted == 0 and value != 0):
        raise DecisionInputError(f"value cannot be represented as finite JSON number: {label}")
    return value


def _source(path: Path, expected: str, alias: str, *, name: str) -> tuple[str, dict]:
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise DecisionInputError(f"missing/invalid frozen source hash: {name}")
    if path.name != name or not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise DecisionInputError(f"missing, unexpected or symlink source: {name}")
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        raise DecisionInputError(f"source SHA256 mismatch: {name}")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DecisionInputError(f"source is not UTF-8: {name}") from exc
    return text, {"file": alias, "sha256": digest, "size_bytes": len(payload)}


def _json(text: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DecisionInputError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise DecisionInputError(f"nonfinite JSON token: {value}")

    try:
        value = json.loads(text, parse_float=Decimal, parse_constant=constant, object_pairs_hook=pairs)
    except (json.JSONDecodeError, InvalidOperation) as exc:
        raise DecisionInputError("invalid frozen JSON") from exc
    if not isinstance(value, dict):
        raise DecisionInputError("frozen JSON must be an object")
    return value


def _json_span(text: str, keys: tuple[str, ...]) -> tuple[int, int]:
    """Locate a known object-member pointer in the original JSON, not a reserialization."""
    decoder, start, end = json.JSONDecoder(), 0, len(text)
    for wanted in keys:
        start += len(text[start:end]) - len(text[start:end].lstrip())
        if text[start] != "{":
            raise DecisionInputError("JSON pointer does not identify an object member")
        cursor = start + 1
        while True:
            cursor += len(text[cursor:end]) - len(text[cursor:end].lstrip())
            if text[cursor] == "}":
                raise DecisionInputError(f"missing JSON member: {wanted}")
            key, cursor = decoder.raw_decode(text, cursor)
            cursor += len(text[cursor:end]) - len(text[cursor:end].lstrip())
            if text[cursor] != ":":
                raise DecisionInputError("invalid JSON member delimiter")
            cursor += 1
            cursor += len(text[cursor:end]) - len(text[cursor:end].lstrip())
            value_start = cursor
            _, cursor = decoder.raw_decode(text, cursor)
            if key == wanted:
                start, end = value_start, cursor
                break
            cursor += len(text[cursor:end]) - len(text[cursor:end].lstrip())
            if text[cursor] == ",":
                cursor += 1
    return start, end


def _json_value(text: str, source: dict, keys: tuple[str, ...], value: Any) -> dict:
    start, end = _json_span(text, keys)
    return {"value": float(value) if isinstance(value, Decimal) else value,
            "source": {**source, "json_pointer": "/" + "/".join(keys),
                       "line": text.count("\n", 0, start) + 1,
                       "column": keys[-1], "raw_token": text[start:end]}}


def _table(text: str, source: dict, dataset: str) -> dict:
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise DecisionInputError("empty frozen CSV") from exc
    if len(set(header)) != len(header) or not set(_COLUMNS).issubset(header):
        raise DecisionInputError("duplicate/missing frozen CSV columns")
    rows = {}
    previous_end = reader.line_num
    for cells in reader:
        physical_row, previous_end = previous_end + 1, reader.line_num
        if not cells:
            continue
        if len(cells) != len(header):
            raise DecisionInputError(f"malformed CSV physical row {physical_row}")
        row = dict(zip(header, cells))
        method = row["method_id"]
        if (row["dataset_id"] != dataset or method not in _PROFILES
                or row["effective_configuration_id"] != _PROFILES[method]
                or row["run_id"] != f"{dataset}_{method}_{_PROFILES[method]}"
                or row["case_id"] != f"CLEAN5_{dataset}_NATURAL"):
            raise DecisionInputError(f"CSV identity mismatch at physical row {physical_row}")
        segments = {"full"} if dataset == "BY2H" else {"pre", "during", "post", "outside", "full"}
        if row["segment_id"] not in segments or row["metric_name"] not in {"horizontal", "position_3d", "up", "yaw"}:
            raise DecisionInputError(f"unexpected CSV segment/metric at physical row {physical_row}")
        key = tuple(row[k] for k in _IDENTITY)
        if key in rows:
            raise DecisionInputError(f"duplicate CSV identity at physical row {physical_row}")
        rows[key] = {"values": row, "source": {**source, "row": physical_row,
                    "row_end": reader.line_num, "row_number_convention": "physical line, 1-based including header"}}
    return rows


def _metric(rows: dict, dataset: str, method: str, segment: str, metric: str, column: str) -> dict:
    key = dataset, method, _PROFILES[method], segment, metric
    if key not in rows:
        raise DecisionInputError(f"missing frozen metric row: {key}")
    item = rows[key]
    row = item["values"]
    if row["unit"] != ("deg" if metric == "yaw" else "m"):
        raise DecisionInputError(f"metric unit mismatch: {key}")
    if re.fullmatch(r"[0-9]+", row["count"]) is None or int(row["count"]) <= 0:
        raise DecisionInputError(f"metric has no finite sample support: {key}")
    value = _decimal(row[column], str(key), nonnegative=True)
    return {"value": float(value), "unit": row["unit"],
            "source": {**item["source"], "column": column, "raw_token": row[column],
                       "identity": {k: row[k] for k in (*_IDENTITY, "run_id", "case_id")}}}


def _compare(left: Decimal, right: Decimal, *, formula: str, input_paths: list[str], rule: dict) -> dict:
    return {"formula": formula, "input_paths": input_paths, "rule_source": rule,
            "left_decimal": str(left), "right_decimal": str(right),
            "inclusive_comparison": left <= right, "threshold_equal": left == right,
            "strict_pass": left < right}


def extract_decision_inputs(*, by2h_table: str | Path, by2o_table: str | Path,
                            yaw_gate_path: str | Path, occlusion_window_path: str | Path,
                            rule_path: str | Path, expected_source_hashes: Mapping[str, str],
                            source_root: str | Path) -> dict:
    """Return strict-JSON inputs; the caller checks C-05 gates and writes exclusively.

    Required hash keys: by2h_table, by2o_table, yaw_gate, occlusion_window.
    Only frozen summary CSV/metadata are read. No error series or reference payload
    is opened, and no metric is recomputed. Invalid prerequisites raise.
    """
    root = Path(source_root).resolve(strict=True)
    paths = {"by2h_table": Path(by2h_table), "by2o_table": Path(by2o_table),
             "yaw_gate": Path(yaw_gate_path), "occlusion_window": Path(occlusion_window_path)}
    texts, sources = {}, {}
    for role, path in paths.items():
        try:
            relative = path.absolute().relative_to(root)
            path.resolve(strict=True).relative_to(root)
        except (ValueError, FileNotFoundError) as exc:
            raise DecisionInputError(f"source is missing or outside CLEAN_ROOT: {role}") from exc
        name = "WINDOW_SEGMENT_SUMMARY.csv" if role.endswith("table") else (
            "YAW_PHYSICAL_GATE.json" if role == "yaw_gate" else "OCCLUSION_WINDOW.json")
        texts[role], sources[role] = _source(path, expected_source_hashes.get(role),
                                            "<CLEAN_ROOT>/" + relative.as_posix(), name=name)
    rule_text, sources["rule"] = _source(Path(rule_path), RULE_SHA256, "<CODE_ROOT>/" + RULE_PATH,
                                          name="A04_F04_ROLE_DECISION_RULE.md")
    gate, window = _json(texts["yaw_gate"]), _json(texts["occlusion_window"])
    if (gate.get("dataset_id") != "BY2H" or gate.get("data_mode") != "real_by2h_raw"
            or type(gate.get("physical_pass")) is not bool or gate.get("trace_used") is not False):
        raise DecisionInputError("invalid BY2H physical-gate identity/status")
    if (window.get("dataset_id") != "BY2O" or window.get("status") != "PASS_INPUT_DEFINED_OCCLUSION_WINDOW"
            or window.get("strace_pass") is not True
            or any(type(window.get(k)) is not int or window[k] != 0
                   for k in ("trace_opens", "bag_opens", "fpl_opens", "raw_forbidden_writes"))):
        raise DecisionInputError("BY2O occlusion preconditions failed")
    try:
        t0, t1 = (_decimal(window["main_window"][k], "occlusion " + k) for k in ("t0", "t1"))
    except (KeyError, TypeError) as exc:
        raise DecisionInputError("missing preregistered occlusion main window") from exc
    if t0 >= t1:
        raise DecisionInputError("invalid preregistered occlusion interval")
    tables = {ds: _table(texts[role], sources[role], ds)
              for ds, role in (("BY2H", "by2h_table"), ("BY2O", "by2o_table"))}
    for item in tables["BY2O"].values():
        row = item["values"]
        if (_decimal(row["degradation_window_start_s"], "table t0") != t0
                or _decimal(row["degradation_window_end_s"], "table t1") != t1):
            raise DecisionInputError("CSV occlusion endpoints differ from preregistered metadata")
    inputs = {"BY2H": {}, "BY2O": {}}
    inputs["BY2H"]["yaw_physical_gate"] = {
        "status": "PASS" if gate["physical_pass"] else "FAIL",
        **_json_value(texts["yaw_gate"], sources["yaw_gate"], ("physical_pass",), gate["physical_pass"])}
    inputs["BY2O"]["occlusion_window"] = {
        k: _json_value(texts["occlusion_window"], sources["occlusion_window"], ("main_window", k), v)
        for k, v in (("t0", t0), ("t1", t1))}
    specs = {"horizontal_rmse_m": ("horizontal", "rmse"), "up_rmse_m": ("up", "rmse")}
    for ds, segments in (("BY2H", ("full",)), ("BY2O", ("full", "outside"))):
        for segment in segments:
            inputs[ds][segment] = {}
            for method in ("A04", "F04"):
                current = {**specs}
                if ds == "BY2H":
                    current.update(yaw_rmse_deg=("yaw", "rmse"), yaw_p95_deg=("yaw", "p95_abs"))
                inputs[ds][segment][method] = {
                    label: _metric(tables[ds], ds, method, segment, metric, column)
                    for label, (metric, column) in current.items()}

    def rule_reference(formula):
        return {**sources["rule"], "line": rule_text[:rule_text.index(formula)].count("\n") + 1,
                "column": "pre_registered_formula", "raw_token": formula}

    def metric_decimal(ds, segment, method, label):
        return Decimal(inputs[ds][segment][method][label]["source"]["raw_token"])

    values = [metric_decimal(ds, segment, method, label)
              for ds in inputs for segment in ("full", "outside") if segment in inputs[ds]
              for method in ("A04", "F04") for label in inputs[ds][segment][method]]
    # Preserve exact decimal boundary tests even for large/small finite CSV tokens.
    precision = max(64, sum(len(v.as_tuple().digits) + abs(v.adjusted()) for v in values) + 20)
    with localcontext() as context:
        context.prec = precision
        heading = {}
        for label, offset, scale, formula in (
            ("yaw_rmse_deg", Decimal("0.50"), Decimal(1), "yawRMSE(F04) <= yawRMSE(A04) - 0.50 deg"),
            ("yaw_p95_deg", Decimal(0), Decimal("0.5"), "yawP95(F04)  <= 0.5 * yawP95(A04)")):
            a, f = (metric_decimal("BY2H", "full", method, label) for method in ("A04", "F04"))
            heading[label] = _compare(f, scale * a - offset, formula=formula,
                input_paths=[f"/inputs/BY2H/full/{m}/{label}" for m in ("A04", "F04")],
                rule=rule_reference(formula))
        position = {}
        for ds, segment in (("BY2H", "full"), ("BY2O", "full"), ("BY2O", "outside")):
            checks = {}
            for label, formula in (("horizontal_rmse_m", "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)"),
                                   ("up_rmse_m", "upRMSE(F04)         <= 1.10 * upRMSE(A04)")):
                a, f = (metric_decimal(ds, segment, method, label) for method in ("A04", "F04"))
                checks[label] = _compare(f, Decimal("1.10") * a, formula=formula,
                    input_paths=[f"/inputs/{ds}/{segment}/{m}/{label}" for m in ("A04", "F04")],
                    rule=rule_reference(formula))
            position[f"{ds}_{segment}"] = checks
    heading_pass = gate["physical_pass"] and any(c["strict_pass"] for c in heading.values())
    position_pass = all(c["strict_pass"] for window_checks in position.values() for c in window_checks.values())
    result = {"schema_version": "clean5.c05.decision_inputs.v1", "extraction_status": "PASS",
              "data_mode": "real_clean5_frozen_evaluation", "synthetic_data_used": False,
              "semisynthetic_data_used": False, "sources": sources, "inputs": inputs,
              "comparison_policy": {"arithmetic": "exact decimal CSV tokens",
                  "equality": "inclusive formula recorded; strict_pass excludes exact threshold equality",
                  "heading": "OR of strictly passing branches, subject to BY2H physical gate",
                  "position": "AND of all six strictly passing comparisons",
                  "tolerance_or_rounding_applied": False},
              "tests": {"heading": {"status": "PASS" if heading_pass else "FAIL",
                  "executable": gate["physical_pass"], "branches": heading},
                  "position": {"status": "PASS" if position_pass else "FAIL", "windows": position}},
              "metric_recomputation_count": 0, "reference_payload_read_count": 0}
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result
