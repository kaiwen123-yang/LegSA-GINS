from pathlib import Path

from legsa_gins.source_aware.source_aware_definition_probe import probe_source_aware_definitions


def test_definition_probe_adopts_auditable_definition():
    # 中文说明：历史 roadmap/boundary 提及不算已有 LSIM/OIM 可执行定义。
    report = probe_source_aware_definitions(Path(__file__).resolve().parents[2])
    assert report["found_existing_definition"] is False
    assert report["adopted_auditable_definition"] is True
    assert "LSIM" in report["adopted_definition"]
    assert report["trace_solver_input"] is False
