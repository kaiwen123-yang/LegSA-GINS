"""Synthetic-only tests for extracting frozen decision inputs, never method choice."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean5_sequence.decision_inputs import (
    DecisionInputError, RULE_PATH, RULE_SHA256, extract_decision_inputs,
)

REPO = Path(__file__).resolve().parents[2]
FIELDS = ["run_id", "method_id", "effective_configuration_id", "dataset_id", "case_id",
          "segment_id", "metric_name", "unit", "rmse", "p95_abs", "count",
          "degradation_window_start_s", "degradation_window_end_s", "note"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def inputs(tmp_path):
    paths, rows = {}, {}
    for dataset, role in (("BY2H", "by2h_table"), ("BY2O", "by2o_table")):
        directory = tmp_path / dataset
        directory.mkdir()
        paths[role] = directory / "WINDOW_SEGMENT_SUMMARY.csv"
        rows[role] = []
        for segment in (("full",) if dataset == "BY2H" else ("full", "outside")):
            for method, profile in (("A04", "AB1011"), ("F04", "AB1111")):
                for metric in (("horizontal", "up", "yaw") if dataset == "BY2H" else ("horizontal", "up")):
                    rows[role].append({"dataset_id": dataset, "method_id": method,
                        "effective_configuration_id": profile, "run_id": f"{dataset}_{method}_{profile}",
                        "case_id": f"CLEAN5_{dataset}_NATURAL", "segment_id": segment,
                        "metric_name": metric, "unit": "deg" if metric == "yaw" else "m",
                        "rmse": ("2" if method == "A04" else "1.4") if metric == "yaw" else (
                            "1" if method == "A04" else "1.05"),
                        "p95_abs": "4" if method == "A04" else "1.5", "count": "100",
                        "degradation_window_start_s": "10" if dataset == "BY2O" else "",
                        "degradation_window_end_s": "20" if dataset == "BY2O" else "", "note": ""})
        write_rows(paths[role], rows[role])
    paths["yaw_gate"] = tmp_path / "BY2H" / "YAW_PHYSICAL_GATE.json"
    paths["yaw_gate"].write_text(json.dumps({"dataset_id": "BY2H", "data_mode": "real_by2h_raw",
                                            "physical_pass": True, "trace_used": False}, indent=2))
    paths["occlusion_window"] = tmp_path / "BY2O" / "OCCLUSION_WINDOW.json"
    paths["occlusion_window"].write_text(json.dumps({"dataset_id": "BY2O",
        "status": "PASS_INPUT_DEFINED_OCCLUSION_WINDOW", "strace_pass": True,
        "trace_opens": 0, "bag_opens": 0, "fpl_opens": 0, "raw_forbidden_writes": 0,
        "main_window": {"t0": 10.0, "t1": 20.0}, "secondary_runs": [{"t0": 25.0, "t1": 26.0}]}, indent=2))
    return {"paths": paths, "rows": rows, "root": tmp_path,
            "hashes": {k: digest(p) for k, p in paths.items()}}


def extract(fixture, **kwargs):
    paths = fixture["paths"]
    args = {"by2h_table": paths["by2h_table"], "by2o_table": paths["by2o_table"],
            "yaw_gate_path": paths["yaw_gate"], "occlusion_window_path": paths["occlusion_window"],
            "rule_path": REPO / RULE_PATH, "expected_source_hashes": fixture["hashes"],
            "source_root": fixture["root"]}
    return extract_decision_inputs(**(args | kwargs))


def change_metric(fixture, dataset, segment, method, metric, column, value):
    role = "by2h_table" if dataset == "BY2H" else "by2o_table"
    row = next(row for row in fixture["rows"][role]
               if (row["segment_id"], row["method_id"], row["metric_name"]) == (segment, method, metric))
    row[column] = value
    write_rows(fixture["paths"][role], fixture["rows"][role])
    fixture["hashes"][role] = digest(fixture["paths"][role])


def test_extracts_only_frozen_inputs_and_no_method_decision(inputs):
    result = extract(inputs)
    encoded = json.dumps(result, allow_nan=False)
    assert result["extraction_status"] == "PASS"
    assert result["tests"]["heading"]["status"] == result["tests"]["position"]["status"] == "PASS"
    assert result["metric_recomputation_count"] == result["reference_payload_read_count"] == 0
    assert result["inputs"]["BY2H"]["full"]["A04"]["yaw_rmse_deg"]["value"] == 2.0
    assert result["inputs"]["BY2O"]["outside"]["F04"]["up_rmse_m"]["value"] == 1.05
    assert "outcome" not in encoded.lower() and "proposed" not in encoded.lower()
    assert str(inputs["root"]) not in encoded
    assert digest(REPO / RULE_PATH) == RULE_SHA256


def test_heading_exact_boundaries_fail_both_strict_branches(inputs):
    change_metric(inputs, "BY2H", "full", "F04", "yaw", "rmse", "1.50")
    change_metric(inputs, "BY2H", "full", "F04", "yaw", "p95_abs", "2.0")
    heading = extract(inputs)["tests"]["heading"]
    assert heading["status"] == "FAIL"
    for branch in heading["branches"].values():
        assert branch["inclusive_comparison"] and branch["threshold_equal"]
        assert not branch["strict_pass"]


@pytest.mark.parametrize("strict_column,equal_column,equal_value,strict_value", [
    ("rmse", "p95_abs", "2", "1.49999999999999999999999999"),
    ("p95_abs", "rmse", "1.50", "1.99999999999999999999999999"),
])
def test_heading_or_allows_other_strict_branch(inputs, strict_column, equal_column, equal_value, strict_value):
    change_metric(inputs, "BY2H", "full", "F04", "yaw", equal_column, equal_value)
    change_metric(inputs, "BY2H", "full", "F04", "yaw", strict_column, strict_value)
    heading = extract(inputs)["tests"]["heading"]
    assert heading["status"] == "PASS"
    assert sum(b["strict_pass"] for b in heading["branches"].values()) == 1
    assert sum(b["threshold_equal"] for b in heading["branches"].values()) == 1


@pytest.mark.parametrize("dataset,segment", [("BY2H", "full"), ("BY2O", "full"), ("BY2O", "outside")])
@pytest.mark.parametrize("metric", ["horizontal", "up"])
def test_each_position_boundary_is_inclusive_but_fails_strict_gate(inputs, dataset, segment, metric):
    change_metric(inputs, dataset, segment, "A04", metric, "rmse", "0.1")
    change_metric(inputs, dataset, segment, "F04", metric, "rmse", "0.11")
    result = extract(inputs)["tests"]["position"]
    branch = result["windows"][f"{dataset}_{segment}"][metric + "_rmse_m"]
    assert result["status"] == "FAIL"
    assert branch["inclusive_comparison"] and branch["threshold_equal"] and not branch["strict_pass"]


def test_position_above_boundary_is_not_inclusive(inputs):
    change_metric(inputs, "BY2O", "outside", "F04", "up", "rmse", "1.10000000000000000000001")
    branch = extract(inputs)["tests"]["position"]["windows"]["BY2O_outside"]["up_rmse_m"]
    assert not branch["inclusive_comparison"] and not branch["threshold_equal"] and not branch["strict_pass"]


def test_csv_source_has_physical_line_after_multiline_record_and_exact_column(inputs):
    role = "by2h_table"
    inputs["rows"][role][0]["note"] = "first line\nsecond line"
    write_rows(inputs["paths"][role], inputs["rows"][role])
    inputs["hashes"][role] = digest(inputs["paths"][role])
    result = extract(inputs)
    value = result["inputs"]["BY2H"]["full"]["A04"]["yaw_p95_deg"]
    assert value["source"]["row"] == 5  # Header=1; horizontal spans 2..3; up=4; yaw=5.
    assert value["source"]["column"] == "p95_abs" and value["source"]["raw_token"] == "4"
    assert value["source"]["sha256"] == inputs["hashes"][role]
    assert value["source"]["file"] == "<CLEAN_ROOT>/BY2H/WINDOW_SEGMENT_SUMMARY.csv"


def test_json_pointer_line_selects_main_not_secondary_window(inputs):
    result = extract(inputs)
    window = result["inputs"]["BY2O"]["occlusion_window"]
    assert window["t0"]["value"] == 10 and window["t1"]["value"] == 20
    for key in ("t0", "t1"):
        src = window[key]["source"]
        assert src["json_pointer"] == "/main_window/" + key and src["column"] == key
        line = inputs["paths"]["occlusion_window"].read_text().splitlines()[src["line"] - 1]
        assert '"' + key + '":' in line and src["raw_token"] in line
    gate = result["inputs"]["BY2H"]["yaw_physical_gate"]
    assert gate["source"]["json_pointer"] == "/physical_pass"


def test_physical_gate_failure_makes_heading_nonexecutable(inputs):
    path = inputs["paths"]["yaw_gate"]
    payload = json.loads(path.read_text())
    payload["physical_pass"] = False
    path.write_text(json.dumps(payload))
    inputs["hashes"]["yaw_gate"] = digest(path)
    result = extract(inputs)
    assert result["inputs"]["BY2H"]["yaw_physical_gate"]["status"] == "FAIL"
    assert result["tests"]["heading"]["status"] == "FAIL"
    assert result["tests"]["heading"]["executable"] is False


@pytest.mark.parametrize("token", ["", "NaN", "Infinity", "-0.1", "1e999", "1e-999"])
def test_invalid_metric_is_rejected_without_substitution(inputs, token):
    change_metric(inputs, "BY2H", "full", "A04", "yaw", "rmse", token)
    with pytest.raises(DecisionInputError):
        extract(inputs)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "wrong_profile", "wrong_dataset", "wrong_unit", "zero_count"])
def test_bad_table_identity_or_support_fails_closed(inputs, defect):
    role = "by2h_table"
    rows = inputs["rows"][role]
    if defect == "missing":
        rows.pop()
    elif defect == "duplicate":
        rows.append(dict(rows[0]))
    else:
        field, value = {"wrong_profile": ("effective_configuration_id", "AB0000"),
                        "wrong_dataset": ("dataset_id", "BY2"), "wrong_unit": ("unit", "rad"),
                        "zero_count": ("count", "0")}[defect]
        rows[0][field] = value
    write_rows(inputs["paths"][role], rows)
    inputs["hashes"][role] = digest(inputs["paths"][role])
    with pytest.raises(DecisionInputError):
        extract(inputs)


@pytest.mark.parametrize("role", ["by2h_table", "by2o_table", "yaw_gate", "occlusion_window"])
def test_source_hash_mismatch_is_rejected(inputs, role):
    inputs["hashes"][role] = "0" * 64
    with pytest.raises(DecisionInputError, match="SHA256 mismatch"):
        extract(inputs)


def test_rule_hash_is_frozen_and_not_replaced_by_caller(inputs, tmp_path):
    path = tmp_path / "A04_F04_ROLE_DECISION_RULE.md"
    path.write_bytes((REPO / RULE_PATH).read_bytes() + b"\n")
    with pytest.raises(DecisionInputError, match="SHA256 mismatch"):
        extract(inputs, rule_path=path)


def test_duplicate_json_keys_and_failed_occlusion_preconditions_reject(inputs):
    path = inputs["paths"]["occlusion_window"]
    payload = path.read_text()
    path.write_text(payload.replace('"t0": 10.0', '"t0": 10.0, "t0": 11.0'))
    inputs["hashes"]["occlusion_window"] = digest(path)
    with pytest.raises(DecisionInputError, match="duplicate JSON"):
        extract(inputs)
    path.write_text(payload.replace('"strace_pass": true', '"strace_pass": false'))
    inputs["hashes"]["occlusion_window"] = digest(path)
    with pytest.raises(DecisionInputError, match="occlusion preconditions"):
        extract(inputs)


def test_table_occlusion_endpoint_mismatch_rejects(inputs):
    change_metric(inputs, "BY2O", "outside", "A04", "up", "degradation_window_end_s", "21")
    with pytest.raises(DecisionInputError, match="occlusion endpoints"):
        extract(inputs)


def test_missing_hash_and_symlink_source_reject(inputs):
    original = inputs["hashes"].pop("by2h_table")
    with pytest.raises(DecisionInputError, match="source hash"):
        extract(inputs)
    inputs["hashes"]["by2h_table"] = original
    path = inputs["paths"]["by2h_table"]
    target = path.with_name("payload.csv")
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(DecisionInputError, match="symlink"):
        extract(inputs)
