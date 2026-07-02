from pathlib import Path

from scripts.paper10q2r1_storage_slim import classify_inventory, has_raw_like


def test_raw_like_file_never_delete_allowed():
    assert has_raw_like(Path("trace_vrtk2.csv"))
    classification, _action, delete_allowed, _compress_allowed, _reason = classify_inventory(
        Path("trace_vrtk2.csv"),
        {"contains_raw_like_files": True, "contains_git_repo": False},
    )
    assert classification == "REVIEW_REQUIRED"
    assert delete_allowed is False
