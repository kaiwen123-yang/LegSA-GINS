"""No real render/run: identity guards, row selection and native-gap arithmetic."""
import hashlib
import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext.figures import (
    _metric, caption, frozen_v21_snapshot, select_plot_rows,
)
from legsa_gins.paper_rebuild.hext.legsa_gap_diagnostic import (
    diagnose_nav_gaps, in_window_gaps,
)


def _rows(config="S"):
    external = "LC01-S" if config == "S" else "LC01"
    return [{"sequence_id":s,"method_id":m,"config":config,"main_row":"true",
             "evaluator_contract":"evaluator_contract_v3"}
            for s in ("BY2","BY2H","BY2O") for m in (external,"F02","A04","F04")]


def test_fig02s_global_selection_rejects_per_sequence_version_substitution():
    selection = {"selected_config":"S","selected_method_id":"LC01-S"}
    rows = _rows()
    methods, selected = select_plot_rows(rows,selection)
    assert methods == ("LC01-S","F02","A04","F04")
    assert len(selected) == 12
    rows[4]["config"] = "LIT"
    with pytest.raises(ValueError,match="substitution"):
        select_plot_rows(rows,selection)


def test_fig02s_no_diagnostic_replacement_and_no_duplicate_rows():
    selection = {"selected_config":"S","selected_method_id":"LC01-S"}
    rows = _rows()
    rows[4]["main_row"] = False
    with pytest.raises(ValueError,match="Missing"):
        select_plot_rows(rows,selection)
    rows = _rows()
    rows.append(dict(rows[0]))
    with pytest.raises(ValueError,match="duplicate"):
        select_plot_rows(rows,selection)


def test_caption_discloses_selection_gaps_start_float_and_denominator():
    text = caption({"selected_config":"S"},[])
    for required in ("S version","every LIT row","FILE_START","CONTRACT_START",
                     "57 GNSS2","matched_epoch_count/output_epoch_count",
                     "commercial low-cost dual-antenna","never reads it"):
        assert required in text


def test_geometry_audit_failure_retains_available_metric():
    for status in ("COMPLETED","AVAILABLE","AVAILABLE_GEOMETRIC_AUDIT_FAIL"):
        assert _metric({"evaluation_status":status,"yaw_rmse_deg":"12.3"},"yaw_rmse_deg") == 12.3
    assert _metric({"evaluation_status":"UNAVAILABLE","yaw_rmse_deg":"0"},"yaw_rmse_deg") is None


def test_snapshot_excludes_only_the_new_extension(tmp_path):
    payload = b'{"frozen":true}\n'
    (tmp_path/"RENDER_MANIFEST.json").write_bytes(payload)
    for name in ("FIG01","FIG02"):
        directory = tmp_path/name;directory.mkdir();(directory/(name+".png")).write_bytes(b"original")
    kwargs = {"expected_render_sha256":hashlib.sha256(payload).hexdigest(),"expected_figure_count":2}
    before = frozen_v21_snapshot(tmp_path,**kwargs)
    (tmp_path/"FIG02S").mkdir();(tmp_path/"FIG02S/FIG02S.png").write_bytes(b"new")
    (tmp_path/"HEXT_RENDER_MANIFEST.json").write_text('{}')
    assert frozen_v21_snapshot(tmp_path,**kwargs) == before
    (tmp_path/"FIG02/FIG02.png").write_bytes(b"changed")
    assert frozen_v21_snapshot(tmp_path,**kwargs) != before
    (tmp_path/"RENDER_MANIFEST.json").write_text('{}')
    with pytest.raises(ValueError,match="identity"):
        frozen_v21_snapshot(tmp_path,**kwargs)


def _nav(times, vd):
    nav = np.zeros((len(times),11))
    nav[:,1] = times;nav[:,4] = np.arange(len(times))+40
    nav[:,5] = np.arange(len(times));nav[:,6] = -np.arange(len(times));nav[:,7] = vd
    return nav


def test_native_gap_no_interpolation_recovery_and_gdt_reference():
    nav = _nav([1.,1.204,1.3,1.8],[.2,2.1,.5,.25])
    gap = {"start_relative_s":1.,"end_relative_s":1.2,"duration_s":.2}
    row = diagnose_nav_gaps(nav,[gap],window=(0,2),gravity_mps2=9.8)[0]
    assert row["status"] == "AVAILABLE"
    assert row["nav_after_time_s"] == 1.204
    assert row["retained_dt_s"] == pytest.approx(.204)
    assert row["delta_vd_mps"] == pytest.approx(1.9)
    assert row["delta_height_m"] == 1
    assert row["retained_g_dt_mps"] == pytest.approx(9.8*.204)
    assert row["recovery_time_s"] == 1.8
    assert row["recovery_after_raw_gap_end_s"] == pytest.approx(.6)


def test_gap_timestamp_frozen_serialization_preserves_left_row():
    nav = _nav([3240.747,3240.749053,3241.021063],[0,.2,2])
    gap = {"start_relative_s":3240.7490525245667,"end_relative_s":3241.0170600414276,
           "duration_s":.2680075168609619}
    row = diagnose_nav_gaps(nav,[gap],window=(3200,3300),gravity_mps2=9.8)[0]
    assert row["nav_before_time_s"] == 3240.749053
    assert row["recovery_status"] == "NOT_OBSERVED_IN_REMAINING_WINDOW"
    assert row["recovery_time_s"] is None


def test_window_overlap_and_no_left_nav_are_explicit():
    gaps = [{"start_relative_s":407.,"end_relative_s":411.,"duration_s":4.},
            {"start_relative_s":412.5,"end_relative_s":413.04,"duration_s":.54},
            {"start_relative_s":414.9,"end_relative_s":415.08,"duration_s":.18}]
    selected = in_window_gaps({"P2":{"gaps_gt_0p1s":gaps}},(413,683))
    assert len(selected) == 2
    rows = diagnose_nav_gaps(_nav([413.047,414.9,415.082],[0,1,2]),selected,
                            window=(413,683),gravity_mps2=9.8)
    assert rows[0]["unavailable_reason"] == "NO_PRE_GAP_NAV_IN_WINDOW"
    assert "delta_vd_mps" not in rows[0]
    assert rows[1]["status"] == "AVAILABLE"


def test_gap_rejects_nonmonotone_or_wrong_shape_nav():
    with pytest.raises(ValueError,match="chronological"):
        diagnose_nav_gaps(_nav([1,1],[0,0]),[],window=(0,2),gravity_mps2=9.8)
    with pytest.raises(ValueError,match="eleven"):
        diagnose_nav_gaps(np.zeros((2,10)),[],window=(0,2),gravity_mps2=9.8)
