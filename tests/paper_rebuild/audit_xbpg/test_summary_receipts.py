import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).resolve().parents[3] / "scripts/paper_rebuild/audit_xbpg/summarize_gnss.py"
    spec = importlib.util.spec_from_file_location("audit_summary",path)
    m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def test_skipped_is_not_executed_and_keeps_reason(tmp_path):
    (tmp_path/"SKIPPED.json").write_text(json.dumps(dict(status="BLOCKED_BY_SMOKE_TECHNICAL_FAILURE",native_invocations=0,reason="TIMEOUT")))
    receipt, validation = module().verify_retained(tmp_path)
    assert receipt["native_invocations"]==0 and receipt["reason"]=="TIMEOUT"
    assert validation["validation"]["finite_rows"]==0


def test_tampered_output_rejected_before_analysis(tmp_path):
    m=module();(tmp_path/"solution.pos").write_text("original")
    (tmp_path/"COMMAND.json").write_text(json.dumps(dict(artifacts={"solution.pos":m.sha(tmp_path/"solution.pos")})))
    (tmp_path/"OUTPUT_VALIDATION.json").write_text(json.dumps(dict(original_receipt_sha256=m.sha(tmp_path/"COMMAND.json"),recorded_output_hashes_match=True)))
    (tmp_path/"solution.pos").write_text("changed")
    with pytest.raises(RuntimeError,match="Changed output"):m.verify_retained(tmp_path)


def test_support_never_reuses_epoch():
    with pytest.raises(ValueError,match="reuses"):
        module().time_support(np.array([0,1]),np.array([0,200_000_000]))
