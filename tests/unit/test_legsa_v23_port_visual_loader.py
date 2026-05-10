"""中文说明：测试 N4H4E visual loader 只读取评价输入并保持 solver 输入边界。"""

from scripts.audit_legsa_v23_port_visual_validation import (
    _rows,
    _write_csv_nav,
    _write_kfgins_nav,
    _write_kfgins_std,
    _write_r3c,
    _write_std,
)
from legsa_gins.visualization.legsa_v23_port_visual_loader import load_visual_inputs


def test_visual_loader_loads_toy_port_final_reference(tmp_path):
    r3 = tmp_path / "r3"
    r3a = tmp_path / "r3a"
    r3b = tmp_path / "r3b"
    r3c = tmp_path / "r3c"
    dual = tmp_path / "dual"
    trace = tmp_path / "trace.csv"
    out = tmp_path / "out"

    port_rows = _rows(offset_h=0.02, yaw_offset=0.03)
    final_rows = _rows()
    trace_rows = _rows(offset_h=-0.3, yaw_offset=-1.8)
    _write_csv_nav(r3a / "run" / "EVAL_NAV.csv", port_rows)
    _write_std(r3a / "run" / "LegSA_PORT_STD.csv", len(port_rows))
    _write_kfgins_nav(dual / "KF_GINS_Navresult.nav", final_rows)
    _write_kfgins_std(dual / "KF_GINS_STD.txt", len(final_rows))
    _write_csv_nav(trace, trace_rows)
    _write_r3c(r3c)
    r3.mkdir()
    r3b.mkdir()

    inputs = load_visual_inputs(
        r3_root=r3,
        r3a_root=r3a,
        r3b_root=r3b,
        r3c_root=r3c,
        dual_root=dual,
        output_dir=out,
        trace_path=trace,
    )

    assert inputs["manifest"]["port_nav_found"] is True
    assert inputs["manifest"]["port_std_found"] is True
    assert inputs["manifest"]["final_v23_nav_found"] is True
    assert inputs["manifest"]["final_v23_std_found"] is True
    assert inputs["manifest"]["trace_found"] is True
    assert inputs["manifest"]["trace_solver_input"] is False
    assert inputs["manifest"]["final_v23_output_solver_input"] is False
    assert inputs["manifest"]["paper_performance_claim"] is False
    assert (out / "VISUAL_INPUT_MANIFEST.json").exists()
