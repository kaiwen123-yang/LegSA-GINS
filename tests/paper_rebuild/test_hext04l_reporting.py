"""Synthetic scalar fixtures only; no native, evaluator or reference access."""
from legsa_gins.paper_rebuild.hext.aggregate import METRIC_FIELDS, H03_PRIMARY_STARTS
from legsa_gins.paper_rebuild.hext.readonly_reporting import amend_rows, scoreboards


def test_amendment_changes_only_row_roles_and_keeps_both_starts():
    rows = [dict(sequence_id=s, method_id=m, start_convention=start,
                 main_row=False, manuscript_row=False, yaw_rmse_deg="1.234567890123")
            for s in H03_PRIMARY_STARTS for m in ("LC01", "LC01-S", "F01", "F02", "F03", "A04", "F04")
            for start in (("FILE_START", "CONTRACT_START") if m.startswith("LC01") else ("FROZEN_V21",))]
    amended = amend_rows(rows)
    for old, new in zip(rows, amended):
        assert {k: v for k, v in old.items() if k not in ("main_row", "manuscript_row")} == {
            k: v for k, v in new.items() if k not in ("main_row", "manuscript_row")}
    assert sum(r["manuscript_row"] for r in amended) == 12
    assert all(not r["manuscript_row"] for r in amended if r["method_id"] in ("LC01-S", "F01", "F03"))


def test_favorable_envelope_uses_each_metric_at_fixed_start():
    rows = []
    for s, start in H03_PRIMARY_STARTS.items():
        for m, value in (("F04", 2), ("LC01", 3), ("LC01-S", 1)):
            rows.append(dict(sequence_id=s, method_id=m, start_convention=start,
                geometric_audit_status="FAIL" if s == "BY2H" else "PASS",
                **{metric: value for metric in METRIC_FIELDS}))
        rows[-1]["yaw_rmse_deg"] = 4
        # A better diagnostic start must never enter the manuscript scoreboard.
        rows.append(dict(rows[-1], start_convention="UNSELECTED_START", yaw_rmse_deg=0))
    lit, best = scoreboards(rows)
    assert len(lit) == len(best) == 21
    assert all(r["lower"] == "F04" for r in lit)
    assert all(r["comparator_method"] == ("LC01" if r["metric"] == "yaw_rmse_deg" else "LC01-S") for r in best)
    assert all(r["geometric_audit_status"] == "FAIL" for r in best if r["sequence_id"] == "BY2H")
