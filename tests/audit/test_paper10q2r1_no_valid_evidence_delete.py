from scripts.paper10q2r1_storage_slim import classify_inventory


def test_reports_stages_are_must_keep(tmp_path):
    stage = tmp_path / "reports" / "stages" / "PAPER10Q2"
    stage.mkdir(parents=True)
    classification, action, delete_allowed, _compress_allowed, _reason = classify_inventory(
        stage,
        {"contains_raw_like_files": False, "contains_git_repo": False},
    )
    assert classification == "MUST_KEEP"
    assert action == "keep_current_evidence_or_export"
    assert delete_allowed is False
