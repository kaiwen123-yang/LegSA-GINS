"""中文说明：PAPER10M0 smoke output contract validator tests。"""

import json
from pathlib import Path

from scripts.paper10m0_output_contract_validator import validate_smoke_output


def _write_minimal_runtime(root: Path, *, forbidden_trace: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "LegSA_PORT_NAV.nav").write_text("time lat lon h\n", encoding="utf-8")
    (root / "LegSA_PORT_STD.csv").write_text("time,pos\n", encoding="utf-8")
    (root / "EVAL_NAV.csv").write_text("metric,value\n", encoding="utf-8")
    (root / "RUN_MANIFEST.json").write_text(
        json.dumps({"trace_solver_input": forbidden_trace, "final_v23_output_solver_input": False}),
        encoding="utf-8",
    )
    (root / "FEATURE_FLAGS.json").write_text("{}", encoding="utf-8")
    (root / "DATASET_ROLE_DUMP.json").write_text("{}", encoding="utf-8")


def test_paper10m0_output_contract_passes_minimal_runtime(tmp_path):
    _write_minimal_runtime(tmp_path)
    result = validate_smoke_output(tmp_path, source_trace_required=False, qm_trace_required=False)
    assert result["status"] == "pass"
    assert result["trace_used_online"] is False
    assert result["final_v23_output_used_as_input"] is False


def test_paper10m0_output_contract_blocks_trace_online(tmp_path):
    _write_minimal_runtime(tmp_path, forbidden_trace=True)
    result = validate_smoke_output(tmp_path, source_trace_required=False, qm_trace_required=False)
    assert result["status"] == "fail"
    assert "trace_used_online" in result["blocker"]


def test_paper10m0_output_contract_requires_source_and_qm_when_enabled(tmp_path):
    _write_minimal_runtime(tmp_path)
    result = validate_smoke_output(tmp_path, source_trace_required=True, qm_trace_required=True)
    assert result["status"] == "fail"
    assert "source_trace_exists_or_not_required" in result["blocker"]
    assert "qm_trace_exists_or_not_required" in result["blocker"]
