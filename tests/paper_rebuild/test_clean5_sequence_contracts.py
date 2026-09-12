"""CLEAN5 contract checks; optional live checks read sealed reports/locks, never raw."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _occlusion_module():
    path = REPO_ROOT / "scripts/paper_rebuild/clean5_define_occlusion_window.py"
    spec = importlib.util.spec_from_file_location("clean5_occlusion_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _epochs(times, flagged=None):
    flags = set(times if flagged is None else flagged)
    return [{"relative_time_R1": time, "flagged": time in flags,
             "trigger_flags": ["gnss2_fix_type_not_8"] if time in flags else []} for time in times]


def test_occlusion_single_segment_includes_closed_window_endpoints():
    module = _occlusion_module()
    result = module.define_window(_epochs([5, 10, 11, 15]), 10, 15)
    main = result["main_window"]
    assert (main["t0"], main["t1"], main["duration_seconds"]) == (10, 15, 5)
    assert main["epoch_count"] == main["flagged_epoch_count"] == 3
    assert main["flags_counts"] == {"gnss2_fix_type_not_8": 3}
    assert result["excluded_outside_closed_window"] == 1
    assert result["secondary_runs"] == []


def test_occlusion_bridges_exactly_five_seconds_but_not_more():
    module = _occlusion_module()
    result = module.define_window(_epochs([10, 12, 15, 20.01, 21], flagged=[10, 15, 20.01, 21]), 0, 30)
    main = result["main_window"]
    assert (main["t0"], main["t1"]) == (10, 15)
    assert main["epoch_count"] == 3 and main["flagged_epoch_count"] == 2
    assert [(r["t0"], r["t1"]) for r in result["secondary_runs"]] == [(20.01, 21)]


def test_occlusion_longest_segment_selected_and_equal_duration_uses_earliest():
    module = _occlusion_module()
    result = module.define_window(_epochs([50, 51, 20, 24, 10, 14]), 0, 60)
    assert (result["main_window"]["t0"], result["main_window"]["t1"]) == (10, 14)
    assert [(r["t0"], r["t1"]) for r in result["secondary_runs"]] == [(20, 24), (50, 51)]


def test_occlusion_outside_flags_do_not_extend_or_select_a_window():
    module = _occlusion_module()
    result = module.define_window(_epochs([0, 5, 10, 15, 20], flagged=[0, 5, 20]), 10, 15)
    assert result["main_window"] is None and result["secondary_runs"] == []
    assert result["flagged_epoch_count"] == 0 and result["epoch_count"] == 2


def test_occlusion_empty_or_unflagged_input_has_null_main_window():
    module = _occlusion_module()
    for epochs in ([], _epochs([10, 11], flagged=[])):
        result = module.define_window(epochs, 0, 20)
        assert result["main_window"] is None and result["secondary_runs"] == []


@pytest.mark.parametrize("start,end", [(2, 1), (float("nan"), 1), (0, float("inf"))])
def test_occlusion_rejects_invalid_contract_window(start, end):
    with pytest.raises(ValueError):
        _occlusion_module().define_window([], start, end)


def _status(time, **fields):
    return {"sys_stamp.secs": str(int(time)), "sys_stamp.nsecs": str(round((time % 1)*1e9)),
            "header.stamp.secs": str(int(time)), "header.stamp.nsecs": str(round((time % 1)*1e9)),
            "fix_type": "8", "pos_valid": "true", "rel_valid": "true", "ant_valid": "true", "ant_state": "2", **fields}


def test_occlusion_flags_either_receiver_and_keeps_original_status_fields():
    module = _occlusion_module()
    one = [_status(10, fix_type="4"), _status(20), _status(30), _status(40, rel_valid="false"), _status(50)]
    two = [_status(10.2, fix_ok="false"), _status(20, fix_type="5"), _status(30, pos_valid="false"), _status(40), _status(50)]
    a1 = [{"timestamp": time} for time in (10, 20, 30, 50)]
    rows = module.flag_epochs(one, two, list(two[0]), a1, 0, .6)
    assert [row["flagged"] for row in rows] == [True, True, True, True, False]
    assert rows[0]["trigger_flags"] == ["gnss1_fix_type_not_8"]  # fix_ok is not an added trigger.
    assert rows[0]["gnss1_original_fields"] == one[0] and rows[0]["gnss2_original_fields"] == two[0]
    assert rows[0]["matched_gnss1_header_R1"] == rows[0]["matched_gnss1_sys_time_R1"] == 10
    assert rows[0]["gnss1_association_delta_seconds"] == pytest.approx(-.2)
    assert "a1_not_constructed_at_matched_gnss1_epoch" in rows[3]["trigger_flags"]
    assert "gnss1_rel_valid_invalid" in rows[3]["trigger_flags"]


def test_occlusion_missing_a1_or_gnss2_antenna_state_is_flagged():
    module = _occlusion_module()
    one = [_status(10), _status(20)]
    two = [_status(10), _status(20, ant_valid="false", ant_state="0")]
    rows = module.flag_epochs(one, two, list(two[0]), [{"timestamp": 20}], 0, .6)
    assert rows[0]["trigger_flags"] == ["a1_not_constructed_at_matched_gnss1_epoch"]
    assert rows[1]["trigger_flags"] == ["gnss2_ant_valid_invalid", "gnss2_ant_state_invalid"]


# Frozen contracts are compared to their declared sources, without importing a
# runtime runner or opening any raw source. Live tests use only C-01/C-02 reports.
import ast
import csv
import hashlib
import json
import math
import os
import re

import yaml

CONTRACT_DIR = REPO_ROOT / "configs/paper_rebuild/clean5"
PARITY_PATH = REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"
PROTOCOL_PATH = REPO_ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"
RUNTIME_PATH = REPO_ROOT / "src/legsa_gins/paper_rebuild/final_v23_clean_parity.py"
DATASETS = ("BY2H", "BY2O")


def _contract(dataset):
    return yaml.safe_load((CONTRACT_DIR / f"CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml").read_text())


def _runtime_tokens():
    function = next(n for n in ast.parse(RUNTIME_PATH.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == "active_runtime_config")
    values = next(n.value for n in function.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "values" for t in n.targets))
    tokens = {}
    for key, value in zip(values.keys, values.values):
        if isinstance(key, ast.Constant) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            parsed = yaml.safe_load(value.value)
            if type(parsed) in (int, float) or isinstance(parsed, list) and all(type(x) in (int, float) for x in parsed):
                tokens[key.value] = value.value
    return tokens


@pytest.mark.parametrize("dataset", DATASETS)
def test_contract_identity_roles_and_all_frozen_sections_load(dataset):
    contract = _contract(dataset)
    registry = yaml.safe_load((CONTRACT_DIR / "CLEAN5_SEQUENCE_REGISTRY.yaml").read_text())["sequences"][dataset]
    for key in ("dataset_id", "stage_id", "data_mode", "fix_prefix", "go2_body", "trace_name"):
        assert contract["identity"][key] == registry[key]
    assert contract["identity"]["sequence_lock_rows"] == len(contract["identity"]["raw_files_sha256"]) == 22
    assert contract["identity"]["control_dataset"] == "BY2"
    assert contract["contract_status"] == "FROZEN_BEFORE_PROVIDER_GENERATION"
    assert contract["yaw_physical_gate"]["status"] == "PREVIEW_ONLY"
    assert contract["method_set"]["execution_order"] == ["F01", "F02", "F03", "A04", "F04"]
    assert contract["method_set"]["decision_pair"] == {"comparison": "full_vs_no_SA", "candidate": "F04", "reference": "A04"}
    assert len(contract["method_set"]["report_pairs"]) == 5
    assert set(contract) >= {"frozen_parameter_sources", "time_contract", "window_contract", "initialization_contract",
                             "frozen_parameters", "method_set", "evaluator_contract", "aggregate_tables", "forbidden"}
    assert all(not Path(p).is_absolute() and ".." not in Path(p).parts for p in contract["identity"]["raw_files_sha256"])


@pytest.mark.parametrize("dataset", DATASETS)
@pytest.mark.parametrize("section", ["imu_preprocessing", "dual_yaw_contract", "receiver_velocity_contract", "filter_contract",
                                     "provider_generation", "solver_common"])
def test_frozen_parameter_blocks_deep_equal_their_by2_sources(dataset, section):
    source = PROTOCOL_PATH if section in {"provider_generation", "solver_common"} else PARITY_PATH
    expected = yaml.safe_load(source.read_text())[section]
    assert _contract(dataset)["frozen_parameters"][section] == expected
    # Literal complete blocks are retained too; this catches scalar spelling drift.
    original = source.read_text()
    begin = re.search(r"^"+section+r":\s*$", original, re.M).start()
    next_section = re.search(r"^[A-Za-z_][A-Za-z_0-9]*:", original[begin+len(section)+2:], re.M)
    end = begin+len(section)+2+next_section.start() if next_section else len(original)
    block = original[begin:end].rstrip()+"\n"
    indented = "".join("  "+line if line.strip() else line for line in block.splitlines(keepends=True))
    assert indented in (CONTRACT_DIR/f"CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml").read_text()


@pytest.mark.parametrize("dataset", DATASETS)
def test_clean_yaw_and_all_runtime_numbers_match_frozen_sources(dataset):
    contract = _contract(dataset)
    frozen = contract["frozen_parameters"]
    clean = yaml.safe_load(PARITY_PATH.read_text())["profiles"]["clean_real_final_v23"]
    fields = ("yaw_measurement_std_deg", "yaw_noise_injection_enabled", "yaw_noise_injection_std_deg", "yaw_noise_seed")
    assert frozen["yaw_measurement"] == {key: clean[key] for key in fields}
    assert frozen["yaw_measurement"]["yaw_measurement_std_deg"] == 1.5
    assert frozen["yaw_measurement"]["yaw_noise_injection_enabled"] is False
    tokens = _runtime_tokens()
    assert frozen["active_runtime_config_numeric_tokens"] == tokens
    assert frozen["active_runtime_config_numeric_fields"] == {key: yaml.safe_load(value) for key, value in tokens.items()}
    init = contract["initialization_contract"]
    for key, value in init["by2_initialization_value_tokens"].items():
        assert value.encode() == tokens[key].encode()
        assert init[key] == yaml.safe_load(value)
        assert f"  {key}: {value}\n" in (CONTRACT_DIR/f"CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml").read_text()
    assert init["initvel"] == [0, 0, 0] and init["initatt"][:2] == [0, 0]
    assert init["yaw_input_domain_check"]["wrap180_required_by_engine"] is False
    yaw = init["yaw_ned_deg_0_360"]
    assert 0 <= yaw < 360 and init["initatt"][2] == yaw
    assert init["yaw_wrap180_equivalent_deg"] == (yaw+180) % 360-180
    assert math.sin(math.radians(yaw)) == pytest.approx(math.sin(math.radians(init["yaw_wrap180_equivalent_deg"])))
    assert set(contract["runtime_sequence_overrides"]["allowed_keys"]) == {"starttime", "endtime", "initpos", "initatt"}


@pytest.mark.parametrize("dataset", DATASETS)
def test_tracked_source_hashes_and_evaluator_identity_are_frozen(dataset):
    contract = _contract(dataset)
    for source in contract["frozen_parameter_sources"]:
        path = source["path"]
        if path.startswith("<") or "#" in path or path.startswith("build/"):
            continue
        assert hashlib.sha256((REPO_ROOT/path).read_bytes()).hexdigest() == source["sha256"], path
    expected = yaml.safe_load(PARITY_PATH.read_text())["evaluator_contract"]
    assert contract["evaluator_contract"]["evaluator_sha256"] == expected["evaluator_sha256"]
    assert contract["evaluator_contract"]["exact_evaluator_semantics"] == expected
    assert contract["evaluator_contract"]["arguments"] == ["--base_time", str(contract["time_contract"]["base_time"]), "--yaw_truth_mode", "enu"]
    assert contract["method_set"]["decision_rule_sha256"] == hashlib.sha256((REPO_ROOT/contract["method_set"]["decision_rule_path"]).read_bytes()).hexdigest()


def _live_clean_root():
    value = os.environ.get("LEGSA_CLEAN5_ROOT")
    if not value:
        pytest.skip("LEGSA_CLEAN5_ROOT not set; live checks read only sealed C-01/C-02 reports and locks")
    return Path(value)


@pytest.mark.parametrize("dataset", DATASETS)
def test_contract_time_window_and_initialization_reproduce_c01b_report(dataset):
    root = _live_clean_root()
    contract = _contract(dataset)
    source = next(s for s in contract["frozen_parameter_sources"] if s.get("role") == "C-01b input-only sequence evidence")
    path = root / source["path"].removeprefix("<CLEAN_ROOT>/")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    report = json.loads(path.read_text())
    time = contract["time_contract"]
    assert time["base_time"] == math.floor(report["b_base_time"]["first_pos_valid_sys_stamp"]/3600)*3600
    assert time["base_time"] == report["b_base_time"]["R1"]
    assert time["auxiliary_rebase_offset_seconds"] == time["base_time"]-time["utc_day_midnight"]
    common = report["d_window_candidates"]["common_coverage"]
    window = contract["window_contract"]
    assert window["first_common_epoch"] == common["first"] and window["last_common_epoch"] == common["last"]
    if contract.get("contract_version", 1) == 2:
        from legsa_gins.paper_rebuild.clean5_sequence.contract_v2 import validate_amendment
        from legsa_gins.paper_rebuild.clean5_sequence.solver_runner import C02_COMMIT, _git_bytes
        relative = f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
        assert validate_amendment(_git_bytes(REPO_ROOT,C02_COMMIT,relative).decode(), (REPO_ROOT/relative).read_text())["passed"]
        event_path = root/"stages"/contract["identity"]["stage_id"]/window["event_report_relative_path"]
        assert hashlib.sha256(event_path.read_bytes()).hexdigest() == contract["event_window_report_sha256"]
        event = json.loads(event_path.read_text())
        assert event["ready_for_v2_contract"]
        assert window["t_start"] == event["v2_window"]["t_start"]
        init_v2 = contract["initialization_contract"]
        assert all(init_v2[key] == value for key,value in event["initialization_v2"].items())
        # The original C-01b initialization remains a provenance regression.
        contract = yaml.safe_load(_git_bytes(REPO_ROOT,C02_COMMIT,relative))
        window = contract["window_contract"]
    assert window["t_start"] == math.ceil(common["first"])+10
    assert window["t_end"] == math.floor(common["last"])-9
    init = contract["initialization_contract"]
    frozen = report["e_initialization"]
    assert init["initpos"] == frozen["position_llh"]
    assert init["position_epoch_R1"] == frozen["first_position_time_R1"] >= window["t_start"]
    assert init["yaw_epoch_R1"] == frozen["first_A1_time_R1"] >= window["t_start"]
    assert init["initatt"][2] == frozen["first_A1_NED_yaw_deg"]
    by2 = json.loads((root/"stages/CLEAN5_BY2_CONTROL_PROBES/PROBE_REPORT.json").read_text())
    assert by2["b_base_time"]["R1"] == 1772784000
    common2 = by2["d_window_candidates"]["common_coverage"]
    assert (math.ceil(common2["first"])+10, math.floor(common2["last"])-9) == (66, 340)


@pytest.mark.parametrize("dataset", DATASETS)
def test_contract_copies_exactly_22_locked_input_hashes_without_opening_raw(dataset):
    root = _live_clean_root()
    contract = _contract(dataset)
    path = root/"01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK_CLEAN5.csv"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == contract["identity"]["raw_lock_sha256"]
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 44
    expected = {r["relative_path"]: r["sha256"] for r in rows if r["dataset"] == dataset}
    assert contract["identity"]["raw_files_sha256"] == expected and len(expected) == 22


def test_registered_occlusion_matches_traced_report_and_controls():
    root = _live_clean_root()
    contract = _contract("BY2O")
    occlusion = contract["occlusion_window"]
    path = root/occlusion["report_path"].removeprefix("<CLEAN_ROOT>/")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == occlusion["report_sha256"]
    report = json.loads(path.read_text())
    assert occlusion["main_window"] == report["main_window"]
    assert occlusion["secondary_runs"] == report["secondary_runs"]
    assert report["strace_pass"] and report["status"] == "PASS_INPUT_DEFINED_OCCLUSION_WINDOW"
    assert report["trace_opens"] == report["bag_opens"] == report["fpl_opens"] == report["raw_forbidden_writes"] == 0
    assert sum(row["flagged"] for row in report["epochs"]) == report["flagged_epoch_count"] == 57
    assert report["flags_counts"] == {"gnss2_fix_type_not_8": 57}
    assert all(row["gnss2_original_fields"]["pos_valid"] == "True" for row in report["epochs"])
    recomputed = _occlusion_module().define_window(report["epochs"], **report["closed_sequence_window"])
    assert recomputed["main_window"] == report["main_window"] and recomputed["secondary_runs"] == report["secondary_runs"]
    for stage in ("CLEAN5_BY2_CONTROL_PROBES", "CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE"):
        control = json.loads((root/"stages"/stage/"OCCLUSION_WINDOW.json").read_text())
        assert control["main_window"] is None and control["secondary_runs"] == [] and control["flagged_epoch_count"] == 0
