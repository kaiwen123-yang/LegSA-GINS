from legsa_gins.da_repro.rtklib_independent_check import parse_rtklib_pos, summarize_rtklib_rows


def test_rtklib_pos_parser_and_summary(tmp_path):
    pos = tmp_path / "moving_base.pos"
    pos.write_text(
        "% header\n"
        "2026/03/06 08:01:14.000,       -0.7346,       -0.4193,        2.7214,  2,  6,  0.7206,  0.9599,  1.5551, -0.3775, -0.7474,  0.1569, -0.00,   2.1\n"
        "2026/03/06 08:01:14.200,       -0.7607,       -0.4782,        2.6395,  1,  7,  0.7206,  0.9599,  1.5551, -0.3775, -0.7474,  0.1568, -0.00,   3.6\n",
        encoding="utf-8",
    )
    rows = parse_rtklib_pos(pos, solution_id="test")
    summary = summarize_rtklib_rows(rows)
    assert len(rows) == 2
    assert summary["usable_epochs"] == 2
    assert summary["fix_count"] == 1
    assert summary["float_count"] == 1
    assert summary["median_baseline_length_m"] > 2.0
    assert summary["used_as_solver_input"] is False
