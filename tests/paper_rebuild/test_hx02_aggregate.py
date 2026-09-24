"""HX-02 aggregation dry run on a mock stage (sealed v3 tables are read, never written)."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.hext import (
    hx02_aggregate as agg,
    hx02_convention,
    hx02_coverage_evaluation,
    hx02_execution as ex,
    hx02_heading_evaluation as he,
)

REPO = Path(__file__).resolve().parents[2]
LOCAL = REPO / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
FORBIDDEN = re.compile(r"shared-source|同源|semisynthetic|semi-synthetic|pre-?registered|preregistered|hash-locked",
                       re.IGNORECASE)


def _clean_root():
    if not LOCAL.is_file():
        return None
    root = Path(yaml.safe_load(LOCAL.read_text(encoding="utf-8"))["paths"]["clean_root"])
    return root if (root / agg.MAIN_TABLE_REL).is_file() and (root / agg.FULL_ABLATION_REL).is_file() else None


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _heading_run(stage: Path, sequence: str, method: str, labels, base_time: float, window):
    run = stage / "RUNS" / ex.run_id(sequence, method)
    rel = np.round(np.arange(window[0] - 5.0, window[1] + 5.0, 0.2), 6)
    variants, conventions = {}, {}
    for offset, label in enumerate(labels):
        valid = (np.arange(rel.size) % (3 + offset)) != 0
        truth = (20.0 + 0.5 * rel) % 360.0
        yaw = (truth + 1.5 + offset) % 360.0
        table = {"epoch_index": np.arange(rel.size), "gps_week": np.full(rel.size, 2408),
                 "gps_tow_seconds": 100.0 + rel, "time_unix_s": base_time + rel, "valid": valid,
                 "body_yaw_deg": np.where(valid, yaw, np.nan)}
        if method == "EXT03":
            table["ratio_fixed"] = (np.arange(rel.size) % 5 == 0).astype(int)
        if method == "RTKLIB":
            table["rtklib_q"] = np.where(valid, 1, 2)
        metrics, _series = he.heading_metrics(table, truth, base_time=base_time, window=window, method_id=label)
        variants[label] = metrics
        rows = [{"valid": str(int(v)), "gps_tow_seconds": repr(t), "body_yaw_deg": repr(y)}
                for v, t, y in zip(valid, table["gps_tow_seconds"], yaw)]
        conventions[label] = hx02_convention.diagnose(rows, {int(round(t * 1000)): float(y - 1.0)
                                                             for t, y in zip(table["gps_tow_seconds"], yaw)})
    _write(run / "eval" / "HEADING" / "OUTPUT" / "HEADING_METRICS.json", {"variants": variants})
    _write(run / "eval" / "CONVENTION_DIAGNOSTIC.json", conventions)
    _write(run / "OUTPUT_HASHES.json", {"file_count": 0, "files": {}})
    _write(run / "COMMAND.json", {"code_commit": "f" * 40})
    _write(run / "DONE.json", {"status": "COMPLETED"})
    _write(run / "ARCHIVE_MANIFEST.json", {"files": []})


@pytest.fixture
def mock_stage(tmp_path):
    clean = _clean_root()
    if clean is None:
        pytest.skip("sealed v3 tables not available on this machine")
    stage = tmp_path / "HX02"
    windows = {"BY2": (1772784000.0, (66.0, 340.0)), "BY2H": (1772784000.0, (413.0, 683.0)),
               "BY2O": (1772780400.0, (3186.0, 3563.0))}
    for sequence, (base, window) in windows.items():
        for method, pairs in agg.HEADING_METHODS.items():
            if (sequence, method) == ("BY2O", "EXT02"):
                run = stage / "RUNS" / ex.run_id(sequence, method)
                _write(run / "FAILURE.json", {"failure_classification": "ABNORMAL_EXIT", "returncode": 2})
                _write(run / "DONE.json", {"status": "ABNORMAL_EXIT"})
                _write(run / "OUTPUT_HASHES.json", {"file_count": 0, "files": {}})
                _write(run / "COMMAND.json", {"code_commit": "f" * 40})
                continue
            _heading_run(stage, sequence, method, [label for label, _ in pairs], base, window)
        ginav = stage / "RUNS" / ex.run_id(sequence, "GINAV")
        coverage = hx02_coverage_evaluation.coverage([window[0] + 3.0 * k for k in range(20)], window)
        evaluation = {"coverage": coverage, "evaluation_status": "EVALUATED",
                      "v3": {"evaluation_status": "UNAVAILABLE_EVALUATION_FAILED", "reason": "D12 mock"},
                      "v2": {"evaluation_status": "COMPLETED", "horizontal_rmse_m": 3.0, "up_rmse_m": 1.0,
                             "yaw_rmse_deg": 7.0, "yaw_p95_absolute_deg": 9.0, "roll_rmse_deg": 1.0,
                             "pitch_rmse_deg": 1.0, "coverage_ratio": 1.0, "matched_epoch_count": 20,
                             "output_epoch_count": 20}}
        if sequence == "BY2O":
            evaluation = {"coverage": coverage, "evaluation_status": "NOT_RUN_ALGORITHM_FAILURE",
                          "bounded_gate": {"passed": False}}
        _write(ginav / "eval" / "GINAV_EVALUATION.json", evaluation)
        _write(ginav / "OUTPUT_HASHES.json", {"file_count": 0, "files": {}})
        _write(ginav / "DONE.json", {"status": "COMPLETED"})
        if sequence != "BY2H":
            branch = {"scored_epochs": 2741, "position_drift_m_per_100m": 1.25, "heading_drift_deg_per_min": 0.4,
                      "drift_definitions": {"position": "ols path", "heading": "ols time"},
                      "horizontal_rmse_m": 2.0, "up_rmse_m": 0.3, "yaw_rmse_deg": 3.0, "horizontal_max_m": 5.0,
                      "reference_path_length_m": 250.0,
                      "relative_pose_error_yaw_translation": {"10s": {"pair_count": 2641, "translation_rmse_m": 0.2,
                                                                      "yaw_rmse_deg": 0.5}}}
            s_run = stage / "RUNS" / ex.run_id(sequence, "HARTLEY_S")
            _write(s_run / "eval" / "RELATIVE_POSE" / "OUTPUT" / "RELATIVE_POSE_METRICS.json", {
                "grid_epochs": 2741, "alignment": {"window_seconds": [window[0], window[0] + 10.0], "epochs": 101,
                                                   "yaw_offset_deg": 12.0, "translation_enu_m": [1.0, 2.0, 0.0]},
                "branches": {"HARTLEY_S": branch, "HARTLEY_LIT": dict(branch, position_drift_m_per_100m=3.5)}})
            for method in ("HARTLEY_S", "HARTLEY_LIT"):
                run = stage / "RUNS" / ex.run_id(sequence, method)
                _write(run / "DONE.json", {"status": "COMPLETED", "evaluation": "EVALUATED"})
                _write(run / "OUTPUT_HASHES.json", {"file_count": 0, "files": {}})
        else:
            for method in ("HARTLEY_S", "HARTLEY_LIT"):
                run = stage / "RUNS" / ex.run_id(sequence, method)
                _write(run / "FAILURE.json", {"failure_classification": "ABNORMAL_EXIT", "returncode": 3})
                _write(run / "DONE.json", {"status": "ABNORMAL_EXIT"})
    (stage / "00_CONTROL").mkdir(parents=True)
    _write(stage / "00_CONTROL" / "STATE.json", {"counters": {"native_calls": 24, "evaluator_calls": 20,
                                                              "reference_free_evaluator_calls": 3,
                                                              "legsa_native_calls": 0, "legsa_evaluator_calls": 0}})
    roots = ex.Roots(code=REPO, clean=clean, raw=tmp_path / "raw", external=tmp_path / "ext", stage=stage,
                     scratch=tmp_path / "scratch", paths_config=LOCAL, contract={"sequences": {}})
    return roots, tmp_path


def test_aggregate_writes_every_category_sealed_rows_and_failures(mock_stage):
    roots, tmp_path = mock_stage
    result = agg.aggregate(roots, docs_copy=tmp_path / "docs", code_freeze="c" * 40)
    target = roots.stage / "90_AGGREGATE"
    with (target / "EXTERNAL_FIVE_CATEGORY_TABLE.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0].keys()) == agg.TABLE_COLUMNS and result["rows"] == len(rows)
    assert set(agg.CATEGORIES) <= {r["category"] for r in rows}
    assert not any(r["method_id"].startswith(("D01", "D02")) for r in rows)
    lookup = {(r["method_id"], r["sequence"], r["metric"], r["start_mode"]): r for r in rows}
    lc01 = lookup[("LC01", "BY2", "yaw_rmse_deg", "FILE_START")]
    assert lc01["value"] == "2.9948274600591076" and ":17 sha256=" in lc01["source"]
    assert lookup[("EXT05C", "BY2", "yaw_rmse_deg", "FILE_START")]["value"] == "12.048641737808111"
    assert lookup[("LegSA_F04", "BY2", "yaw_rmse_deg", "V3_PROTOCOL")]["value"] == "1.8862718548526467"
    assert lookup[("LegSA_F04", "BY2H", "yaw_rmse_deg", "V3_PROTOCOL")]["value"] == "1.93377013508875"
    assert lookup[("LegSA_F04", "BY2O", "yaw_rmse_deg", "V3_PROTOCOL")]["value"] == "2.433814932823714"
    diverged = lookup[("EXT05C-S", "BY2H", "run_status", "FILE_START")]
    assert diverged["failure_flag"].startswith("ALGORITHM_FAILURE") and "SUPPLEMENT" in diverged["notes"]
    no_impl = [r for r in rows if r["value"] == "NO_IMPLEMENTATION"]
    assert {r["method_id"] for r in no_impl} == set(agg.NO_IMPLEMENTATION)
    assert all(r["notes"].startswith("无实现：") for r in no_impl)
    assert lookup[("EXT02", "BY2O", "run_status", "FILE_START")]["value"] == "ABNORMAL_EXIT"
    assert lookup[("EXT04_PAR", "BY2", "availability", "FILE_START")]["denominator_or_valid_epochs"].endswith("/1371")
    assert lookup[("Hartley-S", "BY2H", "run_status", "CONTRACT_START")]["failure_flag"] == "ABNORMAL_EXIT"
    assert lookup[("Hartley-LIT", "BY2O", "position_drift_m_per_100m", "FILE_START")]["value"] == "3.5"
    assert lookup[("LC02_GINAV", "BY2", "frozen_evaluation_status", "FILE_START")]["failure_flag"] == \
        "UNAVAILABLE_EVALUATION_FAILED_D12"
    assert lookup[("LC02_GINAV", "BY2O", "frozen_evaluation_status", "FILE_START")]["failure_flag"] == \
        "ALGORITHM_FAILURE_DIVERGED"
    markdown = (target / "HX02_RESULTS.md").read_text(encoding="utf-8")
    for heading in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 每类结论", "## 复现检查", "## 约定诊断",
                    "## 失败清单", "## Outcome"):
        assert heading in markdown
    assert "无实现" in markdown and '"legsa_native_calls": 0' in markdown
    for name in ("EXTERNAL_FIVE_CATEGORY_TABLE.csv", "HX02_RESULTS.md"):
        text = (target / name).read_text(encoding="utf-8")
        assert (tmp_path / "docs" / name).read_text(encoding="utf-8") == text
        new_text = "\n".join(line for line in text.splitlines() if "无实现：" not in line)
        assert not FORBIDDEN.search(new_text), name
    with pytest.raises(ex.HardStop, match="never overwritten"):
        agg.aggregate(roots, docs_copy=None)
