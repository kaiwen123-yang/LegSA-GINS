from pathlib import Path

from legsa_gins.external_dual_methods.by2_dual_provider_factory import (
    audit_go2_body,
    audit_receiver_root,
    provider_contract_closed,
)


def test_missing_provider_contract_blocks_with_missing_inputs(tmp_path: Path):
    receiver_rows = audit_receiver_root(tmp_path / "missing_receiver")
    go2 = audit_go2_body(tmp_path / "by2.txt")
    closed, missing = provider_contract_closed(receiver_rows, go2["exists"] == "true")
    assert not closed
    assert "gnss1-status.csv" in missing
    assert "gnss2-raw.csv" in missing
    assert "by2.txt" in missing


def test_go2_body_audit_never_treats_go2_as_truth(tmp_path: Path):
    audit = audit_go2_body(tmp_path / "by2.txt")
    assert audit["receiver_imu_as_body_imu"] == "false"
    assert audit["go2_truth_claim_allowed"] == "false"
