from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_clean2_dual_yaw_route_uses_attempts_while_clean1_keeps_accepted_gate() -> None:
    runtime = (
        ROOT / "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp"
    ).read_text(encoding="utf-8")

    assert "const bool yaw_active = options.dual_yaw_update_count > 0;" in runtime
    assert "const bool yaw_attempted = options.yaw_update_count > 0;" in runtime
    clean2_branch = runtime.split("if (options.clean2_formal_mode) {", 1)[1].split(
        '} else if (options.algorithm_id == "single_antenna_EKF")', 1
    )[0]
    assert "yaw_attempted == expected_yaw" in clean2_branch
    assert "yaw_active == expected_yaw" not in clean2_branch

    # CLEAN1 四方法仍以 accepted dual-yaw update 证明模块激活，不改旧证据语义。
    clean1_branch = runtime.split(
        '} else if (options.algorithm_id == "single_antenna_EKF")', 1
    )[1].split("counters_match = counters_match && options.selected_fgo", 1)[0]
    assert "!yaw_active" in clean1_branch
    assert "yaw_active" in clean1_branch
    assert "yaw_attempted" not in clean1_branch
