import importlib.util
import json
import sys
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.audit_xbpg.run_validation import (
    permits_full_after_smoke, terminal_status, validate_output,
)

HEADER = "% GPST,e-baseline(m),n-baseline(m),u-baseline(m),Q\n"
ROW = "2400,132001.2,6,2,-13,2,4,1,2,3,-.1,-.2,-.3,0,2.3\n"


def test_header_only_is_zero_solution_not_success(tmp_path):
    (tmp_path / "solution.pos").write_text(HEADER)
    value = validate_output(tmp_path, "rtk")
    assert terminal_status({"returncode": 0}, value) == "NO_SOLUTION"
    assert permits_full_after_smoke("NO_SOLUTION")


@pytest.mark.parametrize("content,error", [
    ("", "BAD_HEADER"), (HEADER + ROW.replace(",6,", ",nan,"), "NONFINITE"),
    (HEADER + "2400,132001.2,6\n", "COLUMN_COUNT"),
    (HEADER + ROW + ROW, "DUPLICATE_OR_NONMONOTONIC"),
])
def test_bad_outputs_block_affected_full_path(tmp_path, content, error):
    (tmp_path / "solution.pos").write_text(content)
    value = validate_output(tmp_path, "rtk")
    assert any(error in s for s in value["errors"])
    status = terminal_status({"returncode": 0}, value)
    assert status == "INVALID_OUTPUT" and not permits_full_after_smoke(status)


def test_quality_index_and_week_tow(tmp_path):
    (tmp_path / "solution.pos").write_text(HEADER + ROW)
    value = validate_output(tmp_path, "rtk")
    assert value["quality_counts"] == {"2": 1}
    assert value["times"] == [2400 * 604800 + 132001.2]


def test_no_rd_solution_and_navigation_failure_remain_distinct(tmp_path):
    (tmp_path / "doppler_ecef.csv").write_text("time,vecef_x,vecef_y,vecef_z,std_vx,std_vy,std_vz,sat_count,doppler_obs_count,provider_status,source_epoch_time,quality_flag\n")
    value = validate_output(tmp_path, "rd")
    assert terminal_status({"returncode": 6}, value) == "NO_USABLE_DOPPLER_SOLUTION"
    assert terminal_status({"returncode": 4}, value) == "INPUT_NAV_READ_FAILED"


@pytest.mark.parametrize("status,quality,source", [("unavailable","1","123.0"),("available","nan","123.0"),
                                                  ("available","bad","123.0"),("available","1","124.0")])
def test_rd_status_quality_and_source_time(tmp_path, status, quality, source):
    header = "time,vecef_x,vecef_y,vecef_z,std_vx,std_vy,std_vz,sat_count,doppler_obs_count,provider_status,source_epoch_time,quality_flag\n"
    (tmp_path / "doppler_ecef.csv").write_text(header + f"123.0,1,2,3,.1,.1,.1,8,8,{status},{source},{quality}\n")
    value = validate_output(tmp_path,"rd")
    assert value["finite_rows"] == 0 and terminal_status({"returncode":0},value) == "INVALID_OUTPUT"


def driver():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("audit_run_gnss", root / "scripts/paper_rebuild/audit_xbpg/run_gnss.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launch_error_has_terminal_receipt(tmp_path, monkeypatch):
    module = driver()
    def missing(*args, **kwargs):
        raise FileNotFoundError("test missing strace")
    monkeypatch.setattr(module.subprocess, "Popen", missing)
    value = module.invoke(["unused"], tmp_path / "launch", "TEST_LAUNCH", 1, data_mode="synthetic_test")
    saved = json.loads((tmp_path / "launch/COMMAND.json").read_text())
    assert saved["status"] == value["status"] == "LAUNCH_ERROR"
    assert saved["exception"] == "FileNotFoundError" and saved["synthetic_data_used"]


def test_timeout_kills_process_group_and_records_terminal_state(tmp_path):
    module = driver()
    value = module.invoke([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "timeout", "TEST_TIMEOUT", .15, data_mode="synthetic_test")
    assert value["status"] == "TIMEOUT" and value["process_group_killed"]
    assert value["wall_seconds_including_strace"] < 5


def test_reproduction_directory_cannot_overwrite(tmp_path):
    module = driver()
    with pytest.raises(FileExistsError):
        module.invoke(["unused"], tmp_path, "TEST_NO_OVERWRITE", 1, data_mode="synthetic_test")
