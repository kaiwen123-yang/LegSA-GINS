from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_run_registry import (
    build_clean_run_registry,
    validate_execution_protocol,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "configs/paper_rebuild/clean2r2a_execution_protocol.yaml"


def test_clean2r2a_trace_is_offline_only_after_complete_seal() -> None:
    payload = validate_execution_protocol(PROTOCOL)
    assert payload["trace_policy"] == {
        "trace_used_online": False,
        "trace_open_before_all_outputs_sealed": False,
        "offline_evaluation_after_complete_seal": True,
    }
    assert all(row["trace_used_online"] is False for row in build_clean_run_registry())
