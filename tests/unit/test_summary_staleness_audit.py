"""中文说明：summary staleness audit 单元测试只使用 toy files。"""

import json
import os
import time

from legsa_gins.evaluation.summary_staleness_audit import audit_summary_staleness


def test_summary_older_than_nav_is_stale(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    nav = tmp_path / "KF_GINS_Navresult.nav"
    report = tmp_path / "report.json"
    summary.write_text(json.dumps({"yaw_rmse_deg": 93.0, "count": 2}), encoding="utf-8")
    nav.write_text("0 0 40 116 10 0 0 0 0 0 0\n0 1 40 116 10 0 0 0 0 0 0\n", encoding="utf-8")
    report.write_text(json.dumps({"reference_role": "trace_evaluation_only"}), encoding="utf-8")
    now = time.time()
    os.utime(summary, (now - 10, now - 10))
    os.utime(nav, (now, now))
    audit = audit_summary_staleness(summary, nav, [report])
    assert audit["summary_older_than_nav_or_report"] is True
    assert audit["summary_references_different_reference_source"] is True
    assert audit["trace_solver_input"] is False
