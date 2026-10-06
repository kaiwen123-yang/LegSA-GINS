"""Four predeclared synthetic checks. No files from any real experiment."""
import importlib.util
from pathlib import Path
import numpy as np

path = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/carrier_phase/compare_full_window_navigation.py"
spec = importlib.util.spec_from_file_location("full_nav_comparison", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def errors(times, yaw, horizontal=None, up=None):
    return m.errors_from_rows([{"time": t, "yaw_err_deg": y,
        "horizontal_err_m": h, "err_u_m": u} for t,y,h,u in
        zip(times,yaw, horizontal if horizontal is not None else [0]*len(times),
            up if up is not None else [0]*len(times))])


def test_01_exact_common_keys_no_interpolation_and_missing():
    left = errors([0., .2, .4], [0., 1., 2.])
    right = errors([0., .20000000001, .4], [2., 90., 4.])
    a, b = m.common_errors(left, right)
    assert a["time"].tolist() == b["time"].tolist() == [0., .4]
    assert b["yaw_err_deg"].tolist() == [2., 4.]
    grid = np.union1d(left["time"], right["time"])
    r = m.event_summary(grid, right, "yaw", [0., .6])
    assert r["missing_slot_count"] == 1
    assert r["missing_runs"][0]["first_missing_key_s"] == .2
    assert m.metrics(m.empty_errors())["yaw_rmse_deg"] is None


def test_02_confirmation_at_end_missing_break_and_censor():
    grid = np.arange(0., 2.61, .2)
    # Exceed at zero; missing .6 prevents confirmation at 1.2.
    present = np.delete(grid, 3)
    e = errors(present, [3.] + [0.]*(len(present)-1))
    r = m.event_summary(grid, e, "yaw", [0., 2.8])
    assert r["event_count"] == 1
    assert r["events"][0]["confirmation_s"] == grid[9]  # .8 + 1.0, not .2 + 1.0
    assert not r["events"][0]["right_censored"]
    short = errors([0., .2, .4], [3., 0., 0.])
    r = m.event_summary([0., .2, .4], short, "yaw", [0., .6])
    assert r["right_censored_count"] == 1
    assert r["events"][0]["confirmation_s"] is None


def test_03_wrap_safe_errors_and_strict_threshold():
    e = errors([0., .2, .4], [180., -180., 2.], [2., 2., 2.], [3., -3., 3.])
    assert m.metrics(e)["yaw_max_absolute_deg"] == 180.
    assert m.event_summary(e["time"], e, "horizontal", [0., .6])["event_count"] == 0
    assert m.event_summary(e["time"], e, "up", [0., .6])["event_count"] == 0
    r = m.event_summary(e["time"], e, "yaw", [0., .6])
    assert r["event_count"] == 1 and r["events"][0]["exceedance_samples"] == 2


def test_04_sequence_gates_no_pooled_rescue_and_missing_B():
    base = {k: 1. for k in m.METRICS + m.MAXIMA}
    rows = []
    for i, seq in enumerate(m.SEQUENCES):
        new = dict(base)
        new["yaw_rmse_deg"] = .9 if i < 2 else 1.
        rows.append(m.comparison_row(seq, "CARRIER_FALLBACK", "FULL_AVAILABLE_FROZEN", new, base))
    coverage = dict.fromkeys(m.SEQUENCES, True)
    gate = m.contract_gate(rows, coverage)
    assert gate["A"] is True and gate["B"] is None
    assert gate["false_fix_probability"] is None
    # Huge improvements elsewhere cannot offset one sequence H violation.
    bad = dict(base); bad["horizontal_rmse_m"] = 1.011
    rows[2] = m.comparison_row("BY2O", "CARRIER_FALLBACK", "FULL_AVAILABLE_FROZEN", bad, base)
    assert m.contract_gate(rows, coverage)["A"] is False
    unknown = m.comparison_row("BY2O", "CARRIER_FALLBACK", "FULL_AVAILABLE_FROZEN", {}, base)
    rows[2] = unknown
    assert m.contract_gate(rows, coverage)["A"] is None
