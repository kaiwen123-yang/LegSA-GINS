from pathlib import Path


def test_formal_runner_cannot_self_prepare():
    source = (Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/run_canonical541_full_algorithm.py").read_text(
        encoding="utf-8"
    )
    assert "prepare_execution_plan" not in source
    assert "load_base" not in source
    assert "load_execution_plan(" in source
    assert source.index("load_execution_plan(") < source.index("execute_unique_selection(")
    assert source.count("load_execution_plan(") == 4
    positions = []
    cursor = 0
    for _ in range(3):
        execute = source.index("execute_unique_selection(", cursor)
        reload_position = source.index("load_execution_plan(", execute)
        positions.append((execute, reload_position)); cursor = reload_position + 1
    assert all(execute < reload_position for execute, reload_position in positions)
