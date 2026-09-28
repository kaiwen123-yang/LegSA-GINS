import csv
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/audit_canonical541.py"
SPEC = importlib.util.spec_from_file_location("audit_canonical541_test_module", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def test_attempt_registry_requires_and_binds_both_roots(tmp_path):
    stage = tmp_path / audit.STAGE_ID
    output = stage / "08_FULL_ALGORITHM_RUNS/RUN_00001"; output.mkdir(parents=True)
    attempt = output.parent / ".attempts/RUN_00001/attempt_01"  # promoted: intentionally absent
    registry = stage / "11_OUTPUT_SEAL/RUN_ATTEMPTS.csv"
    _write_csv(registry, [{
        "run_id": "RUN_00001", "attempt": 1, "formal": True,
        "terminal_status": "COMPLETED_EVALUABLE", "technical_retry": False,
        "retry_authorized": False, "metric_driven_rerun": False,
        "attempt_root": str(attempt), "output_root": str(output),
    }])
    report, roots = audit._verify_attempts(registry, {"RUN_00001"}, stage)
    assert report["attempt_rows"] == 1 and output.resolve() in roots

    rows = audit._read_csv(registry); rows[0]["attempt_root"] = ""
    registry.unlink(); _write_csv(registry, rows)
    with pytest.raises(audit.TerminalAuditError, match="attempt_root and output_root"):
        audit._verify_attempts(registry, {"RUN_00001"}, stage)


def test_retry_attempt_requires_technical_authorization(tmp_path):
    stage = tmp_path / audit.STAGE_ID
    output = stage / "10_INTERNAL_ABLATION_RUNS/RUN_00002"; output.mkdir(parents=True)
    base = output.parent / ".attempts/RUN_00002"
    attempt1 = base / "attempt_01"; attempt1.mkdir(parents=True)
    rows = [
        {"run_id":"RUN_00002","attempt":1,"terminal_status":"TECHNICAL_FAILURE_RETRYABLE",
         "retry_authorized":True,"technical_retry":False,"metric_driven_rerun":False,
         "attempt_root":str(attempt1),"output_root":str(output)},
        {"run_id":"RUN_00002","attempt":2,"terminal_status":"COMPLETED_EVALUABLE",
         "retry_authorized":False,"technical_retry":True,"metric_driven_rerun":False,
         "attempt_root":str(base/"attempt_02"),"output_root":str(output)},
    ]
    registry = stage / "11_OUTPUT_SEAL/RUN_ATTEMPTS.csv"; _write_csv(registry, rows)
    report, roots = audit._verify_attempts(registry, {"RUN_00002"}, stage)
    assert report["technical_retry_count"] == 1 and attempt1.resolve() in roots

    rows[0]["retry_authorized"] = False; registry.unlink(); _write_csv(registry, rows)
    with pytest.raises(audit.TerminalAuditError, match="technical authorization"):
        audit._verify_attempts(registry, {"RUN_00002"}, stage)


def test_code_freeze_requires_counts_and_explicit_before_freeze_booleans(tmp_path):
    stage = tmp_path / audit.STAGE_ID; root = stage / "01_GIT_FREEZE"; root.mkdir(parents=True)
    commit = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=audit.REPO_ROOT, text=True).strip()
    payload = {
        "stage_id": audit.STAGE_ID, "code_freeze_commit": commit,
        "executable_sha256": "a"*64, "provider_generation_count_at_freeze": 0,
        "formal_solver_run_count_at_freeze": 0, "trace_open_count_at_freeze": 0,
        "worktree_clean": True,
        "degraded_provider_generation_started_before_freeze": False,
        "formal_solver_run_started_before_freeze": False, "passed": True,
    }
    gate = root / "CANONICAL541_CODE_FREEZE.json"
    gate.write_text(json.dumps(payload), encoding="utf-8")
    assert audit._verify_code_freeze(stage)["code_freeze_commit"] == commit
    del payload["degraded_provider_generation_started_before_freeze"]
    gate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(audit.TerminalAuditError, match="gate mismatch"):
        audit._verify_code_freeze(stage)


def test_degradation_type_summaries_are_required_audit_and_evidence_payloads():
    expected = {
        "FULL_ALGORITHM_DEGRADATION_TYPE_SUMMARY.csv",
        "INTERNAL_ABLATION_DEGRADATION_TYPE_SUMMARY.csv",
    }
    assert set(audit.DEGRADATION_TYPE_SUMMARY_FILES) == expected
    assert expected.issubset(set(audit.REQUIRED_ANALYSIS_SUPPORT))
    assert set(audit.CURATED_DEGRADATION_TYPE_SUMMARY_PATHS) == {
        f"13_RESULT_ANALYSIS/{name}" for name in expected
    }
