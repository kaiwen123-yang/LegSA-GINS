"""中文说明：测试 N4H4E1 STD 单位审计，避免 rad/deg 混画。"""

import math
from pathlib import Path

from legsa_gins.visualization.legsa_v23_port_std_unit_audit import (
    audit_std_writer_source,
    infer_attitude_std_unit,
    make_std_unit_audit_report,
)


ROOT = Path(__file__).resolve().parents[2]


def _rows(value: float):
    return [{"std_roll_deg": value, "std_pitch_deg": value, "std_yaw_deg": value}]


def test_detects_rad_vs_deg_attitude_std_confusion():
    port = infer_attitude_std_unit(_rows(math.radians(2.0)), "source_backed_port_core")
    final = infer_attitude_std_unit(_rows(2.0), "final_v23_reference_baseline")
    assert port["attitude_std_unit"] == "rad"
    assert port["yaw_std_rad_deg_confusion_suspect"] is True
    assert final["attitude_std_unit"] == "deg"


def test_detects_common_unit_ok_and_expected_kfgins_deg():
    source = audit_std_writer_source(ROOT)
    assert source["source_backed_writeSTD_expected_unit"] == "deg"
    assert source["port_writer_common_unit_ok"] is True


def test_evidence_missing_when_std_rows_absent():
    report = infer_attitude_std_unit([], "source_backed_port_core")
    assert report["attitude_std_unit"] == "evidence_missing"


def test_std_unit_report_marks_writer_fix_applied_for_legacy_rad_artifact():
    report = make_std_unit_audit_report(
        port_std_rows=_rows(math.radians(2.0)),
        finalv23_std_rows=_rows(2.0),
        repo_root=ROOT,
    )
    assert report["source_backed_writeSTD_expected_unit"] == "deg"
    assert report["port_attitude_std_unit"] == "rad"
    assert report["finalv23_attitude_std_unit"] == "deg"
    assert report["yaw_std_rad_deg_confusion_suspect"] is True
    assert report["fix_required"] is True
    assert report["fix_applied"] is True
    assert report["fix_type"] == "writer_fix"
    assert report["paper_performance_claim"] is False
