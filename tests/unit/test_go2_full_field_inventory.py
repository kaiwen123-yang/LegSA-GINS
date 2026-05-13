"""中文说明：单元测试覆盖 N7C5 Go2 全字段盘点和 not-truth 边界。"""

from legsa_gins.go2_prior.go2_full_field_inventory import FIELD_GROUPS, build_go2_full_field_inventory


def _complete_row():
    row = {"time": 0.0, "aligned_time": 0.0}
    for columns in FIELD_GROUPS.values():
        for column in columns:
            row[column] = 1.0
    return row


def test_full_field_inventory_finds_all_groups_and_not_truth():
    report = build_go2_full_field_inventory([_complete_row(), _complete_row()])
    assert report["all_required_groups_available"] is True
    assert report["not_truth"] is True
    assert report["go2_position_truth_claim"] is False
    assert report["go2_velocity_truth_claim"] is False
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_solver_input"] is False
    assert report["fields"]["foot_speed_body"]["available"] is True
