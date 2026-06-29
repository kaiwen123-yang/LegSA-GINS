from pathlib import Path

from legsa_gins.degradation.a1_dual_diff_yaw_builder import build_source_lineage_yaw_series


def _write_status(path: Path, rel_e_offset: float) -> None:
    path.write_text(
        "\n".join(
            [
                "header.stamp.secs,header.stamp.nsecs,rel_pos_n,rel_pos_e,rel_pos_d,rel_acc_n,rel_acc_e,rel_acc_d,rel_valid,ant_valid,ant_state",
                f"100,0,1.0,{rel_e_offset},0.0,0.01,0.01,0.01,true,true,2",
                f"101,0,1.0,{rel_e_offset},0.0,0.01,0.01,0.01,true,true,2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_a1_dual_diff_builder_uses_gnss2_minus_gnss1(tmp_path: Path) -> None:
    g1 = tmp_path / "g1.csv"
    g2 = tmp_path / "g2.csv"
    _write_status(g1, 0.0)
    _write_status(g2, 1.0)
    series, audit = build_source_lineage_yaw_series(g1, g2, base_time=100.0)
    assert len(series) == 2
    assert audit["gnss_order"] == "GNSS2-GNSS1"
    assert audit["trace_used_for_generation"] is False

